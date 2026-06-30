from __future__ import annotations

import difflib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from inscription.compiler import compile_file, compile_source
from inscription.diagnostics import InscriptionError
from inscription.runner import LOWERING_PASSES, OPTIMIZATION_PRESETS, ToolchainError, resolve_toolchain, run_file, run_source, verify_mlir

FIXTURES = ROOT / "tests" / "fixtures" / "positive"
GOLDENS = ROOT / "tests" / "goldens"


class CompilerTests(unittest.TestCase):
    def fixture(self, name: str) -> str:
        return (FIXTURES / name).read_text()

    def test_goldens_match_exact_mlir(self):
        for source_path in sorted(GOLDENS.glob("*.ins")):
            with self.subTest(golden=source_path.name):
                expected_path = source_path.with_suffix(".mlir")
                expected = expected_path.read_text()
                actual = compile_source(source_path.read_text(), source_path=source_path, module_root=GOLDENS)
                diff = "".join(
                    difflib.unified_diff(
                        expected.splitlines(True),
                        actual.splitlines(True),
                        fromfile=str(expected_path),
                        tofile="actual",
                    )
                )
                self.assertEqual(actual, expected, diff)

    def test_checked_goldens_match_exact_mlir(self):
        checked = ROOT / "tests" / "goldens_checked"
        for source_path in sorted(checked.glob("*.ins")):
            with self.subTest(golden=source_path.name):
                expected_path = source_path.with_suffix(".mlir")
                expected = expected_path.read_text()
                actual = compile_source(
                    source_path.read_text(),
                    source_path=source_path,
                    module_root=checked,
                    runtime_checks=True,
                )
                diff = "".join(
                    difflib.unified_diff(
                        expected.splitlines(True),
                        actual.splitlines(True),
                        fromfile=str(expected_path),
                        tofile="actual",
                    )
                )
                self.assertEqual(actual, expected, diff)

    def test_known_fixtures_execute_with_expected_exit_statuses(self):
        expected = json.loads((FIXTURES / "manifest.json").read_text())
        self.assertTrue(all(0 <= status <= 255 for status in expected.values()))
        for filename, status in expected.items():
            with self.subTest(filename=filename):
                try:
                    result = run_file(FIXTURES / filename, module_root=FIXTURES)
                except ToolchainError as exc:
                    self.skipTest(str(exc))
                self.assertEqual(result.exit_status, status)

    def test_cli_run_uses_process_exit_status_channel(self):
        try:
            resolve_toolchain()
        except ToolchainError as exc:
            self.skipTest(str(exc))
        proc = subprocess.run(
            [sys.executable, "-m", "inscription", "run", str(FIXTURES / "add.ins")],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(SRC)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 5)
        self.assertEqual(proc.stdout, "")

    def test_cli_runtime_checks_flag_runs_checked_fixture(self):
        try:
            resolve_toolchain()
        except ToolchainError as exc:
            self.skipTest(str(exc))
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "run",
                str(FIXTURES / "checked_dynamic_buffer_index.ins"),
                "--runtime-checks",
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(SRC)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_v016_cli_artifact_emission_and_save_temps(self):
        try:
            toolchain = resolve_toolchain()
        except ToolchainError as exc:
            self.skipTest(str(exc))

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        source = FIXTURES / "phrase_max.ins"
        expected_mlir = (GOLDENS / "04_main_calls_max.mlir").read_text()

        mlir_proc = subprocess.run(
            [sys.executable, "-m", "inscription", "compile", str(source), "--emit", "mlir", "--verify"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(mlir_proc.returncode, 0, mlir_proc.stderr)
        self.assertEqual(mlir_proc.stdout, expected_mlir)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            lowered_path = tmp_path / "phrase_max.lowered.mlir"
            llvm_path = tmp_path / "phrase_max.ll"
            object_path = tmp_path / "export_scalar_gives.o"
            temps = tmp_path / "temps"
            run_temps = tmp_path / "run-temps"

            lowered_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "lowered-mlir",
                    "--verify",
                    "-o",
                    str(lowered_path),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(lowered_proc.returncode, 0, lowered_proc.stderr)
            self.assertEqual(lowered_proc.stdout, "")
            lowered = lowered_path.read_text()
            self.assertIn("llvm.func @main", lowered)

            llvm_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_path),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(llvm_proc.returncode, 0, llvm_proc.stderr)
            self.assertEqual(llvm_proc.stdout, "")
            llvm_ir = llvm_path.read_text()
            self.assertIn("define i32 @main", llvm_ir)

            no_output_object = subprocess.run(
                [sys.executable, "-m", "inscription", "compile", str(source), "--emit", "object"],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(no_output_object.returncode, 2)
            self.assertIn("object emission requires -o OUTPUT", no_output_object.stderr)

            invalid_emit = subprocess.run(
                [sys.executable, "-m", "inscription", "compile", str(source), "--emit", "nonsense"],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(invalid_emit.returncode, 2)
            self.assertIn("invalid emit mode nonsense", invalid_emit.stderr)

            if toolchain.llc is not None:
                object_proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "compile",
                        str(FIXTURES / "export_scalar_gives.ins"),
                        "--emit",
                        "object",
                        "--verify",
                        "-o",
                        str(object_path),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(object_proc.returncode, 0, object_proc.stderr)
                self.assertEqual(object_proc.stdout, "")
                self.assertGreater(object_path.stat().st_size, 0)

            save_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "llvm-ir",
                    "--save-temps",
                    str(temps),
                    "-o",
                    str(tmp_path / "saved.ll"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(save_proc.returncode, 0, save_proc.stderr)
            self.assertTrue((temps / "phrase_max.mlir").exists())
            self.assertTrue((temps / "phrase_max.lowered.mlir").exists())
            self.assertTrue((temps / "phrase_max.ll").exists())

            run_proc = subprocess.run(
                [sys.executable, "-m", "inscription", "run", str(source), "--save-temps", str(run_temps)],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(run_proc.returncode, 7, run_proc.stderr)
            self.assertEqual(run_proc.stdout, "")
            self.assertTrue((run_temps / "phrase_max.mlir").exists())
            self.assertTrue((run_temps / "phrase_max.lowered.mlir").exists())
            self.assertTrue((run_temps / "phrase_max.ll").exists())

    def test_v016_emit_llvm_ir_supports_runtime_checks_and_modules(self):
        try:
            resolve_toolchain()
        except ToolchainError as exc:
            self.skipTest(str(exc))

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            checked_ll = tmp_path / "checked.ll"
            checked_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "checked_dynamic_buffer_index.ins"),
                    "--runtime-checks",
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(checked_ll),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(checked_proc.returncode, 0, checked_proc.stderr)
            checked_ir = checked_ll.read_text()
            self.assertIn("storage upper-bound check failed", checked_ir)
            self.assertIn("declare void @abort", checked_ir)

            module_ll = tmp_path / "module.ll"
            module_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "export_module_phrase" / "main.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(module_ll),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(module_proc.returncode, 0, module_proc.stderr)
            module_ir = module_ll.read_text()
            self.assertIn("define i32 @ins_square", module_ir)
            self.assertIn("call i32 @ins_square", module_ir)

    def test_v017_optimization_presets_affect_downstream_artifacts_only(self):
        try:
            toolchain = resolve_toolchain()
        except ToolchainError as exc:
            self.skipTest(str(exc))

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        source = FIXTURES / "phrase_max.ins"
        expected_mlir = (GOLDENS / "04_main_calls_max.mlir").read_text()

        raw_with_o2 = subprocess.run(
            [sys.executable, "-m", "inscription", "compile", str(source), "--emit", "mlir", "-O2", "--verify"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(raw_with_o2.returncode, 0, raw_with_o2.stderr)
        self.assertEqual(raw_with_o2.stdout, expected_mlir)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            lowered = tmp_path / "phrase_max.o1.lowered.mlir"
            o2_ll = tmp_path / "phrase_max.o2.ll"
            module_ll = tmp_path / "module.o2.ll"
            object_path = tmp_path / "export_scalar_gives.o2.o"

            basic_lowered = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "lowered-mlir",
                    "-O1",
                    "--verify",
                    "-o",
                    str(lowered),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(basic_lowered.returncode, 0, basic_lowered.stderr)
            self.assertGreater(lowered.stat().st_size, 0)

            aggressive_llvm = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "llvm-ir",
                    "-O2",
                    "--verify",
                    "-o",
                    str(o2_ll),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(aggressive_llvm.returncode, 0, aggressive_llvm.stderr)
            self.assertIn("define i32 @main", o2_ll.read_text())

            optimized_module = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "export_module_phrase" / "main.ins"),
                    "--emit",
                    "llvm-ir",
                    "-O2",
                    "--verify",
                    "-o",
                    str(module_ll),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(optimized_module.returncode, 0, optimized_module.stderr)
            self.assertIn("define i32 @ins_square", module_ll.read_text())

            if toolchain.llc is not None:
                optimized_object = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "compile",
                        str(FIXTURES / "export_scalar_gives.ins"),
                        "--emit",
                        "object",
                        "-O2",
                        "--verify",
                        "-o",
                        str(object_path),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(optimized_object.returncode, 0, optimized_object.stderr)
                self.assertGreater(object_path.stat().st_size, 0)

    def test_v017_optimized_run_save_temps_and_diagnostics(self):
        try:
            resolve_toolchain()
        except ToolchainError as exc:
            self.skipTest(str(exc))

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        run_cases = [
            ("optimization_arithmetic.ins", ["-O2"], 42),
            ("optimization_loop.ins", ["-O2"], 10),
            ("checked_dynamic_buffer_index.ins", ["--runtime-checks", "-O1"], 3),
        ]
        for fixture, options, expected in run_cases:
            with self.subTest(fixture=fixture):
                proc = subprocess.run(
                    [sys.executable, "-m", "inscription", "run", str(FIXTURES / fixture), *options],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, expected, proc.stderr)
                self.assertEqual(proc.stdout, "")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            opt_temps = tmp_path / "opt-temps"
            none_temps = tmp_path / "none-temps"

            optimized_temps = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "phrase_max.ins"),
                    "--emit",
                    "llvm-ir",
                    "-O1",
                    "--save-temps",
                    str(opt_temps),
                    "-o",
                    str(tmp_path / "o1.ll"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(optimized_temps.returncode, 0, optimized_temps.stderr)
            self.assertTrue((opt_temps / "phrase_max.mlir").exists())
            self.assertTrue((opt_temps / "phrase_max.optimized.mlir").exists())
            self.assertTrue((opt_temps / "phrase_max.lowered.mlir").exists())
            self.assertTrue((opt_temps / "phrase_max.ll").exists())

            unoptimized_temps = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "phrase_max.ins"),
                    "--emit",
                    "llvm-ir",
                    "--save-temps",
                    str(none_temps),
                    "-o",
                    str(tmp_path / "none.ll"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(unoptimized_temps.returncode, 0, unoptimized_temps.stderr)
            self.assertTrue((none_temps / "phrase_max.mlir").exists())
            self.assertFalse((none_temps / "phrase_max.optimized.mlir").exists())
            self.assertTrue((none_temps / "phrase_max.lowered.mlir").exists())
            self.assertTrue((none_temps / "phrase_max.ll").exists())

        conflict = subprocess.run(
            [sys.executable, "-m", "inscription", "compile", str(FIXTURES / "phrase_max.ins"), "--opt-level", "basic", "-O2"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(conflict.returncode, 2)
        self.assertIn("conflicting optimization levels: basic and aggressive", conflict.stderr)

        duplicate_alias_conflict = subprocess.run(
            [sys.executable, "-m", "inscription", "compile", str(FIXTURES / "phrase_max.ins"), "-O1", "-O2"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(duplicate_alias_conflict.returncode, 2)
        self.assertIn("conflicting optimization levels: basic and aggressive", duplicate_alias_conflict.stderr)

        invalid = subprocess.run(
            [sys.executable, "-m", "inscription", "compile", str(FIXTURES / "phrase_max.ins"), "--opt-level", "fast"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("invalid optimization level fast", invalid.stderr)

        pipeline = subprocess.run(
            [sys.executable, "-m", "inscription", "check-tools", "--show-pipeline"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(pipeline.returncode, 0, pipeline.stderr)
        self.assertIn("optimization presets:", pipeline.stdout)
        self.assertIn("basic: canonicalize, cse", pipeline.stdout)
        self.assertIn("aggressive: canonicalize, cse, sccp", pipeline.stdout)

    def test_v018_executable_emission_and_save_temps(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        source = FIXTURES / "phrase_max.ins"
        no_output_executable = subprocess.run(
            [sys.executable, "-m", "inscription", "compile", str(source), "--emit", "executable"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(no_output_executable.returncode, 2)
        self.assertIn("executable emission requires -o OUTPUT", no_output_executable.stderr)

        try:
            toolchain = resolve_toolchain(require_executable=True)
        except ToolchainError as exc:
            self.skipTest(str(exc))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            cases = [
                (
                    FIXTURES / "phrase_max.ins",
                    [],
                    tmp_path / "phrase_max",
                    7,
                ),
                (
                    FIXTURES / "optimization_arithmetic.ins",
                    ["-O2"],
                    tmp_path / "optimization_arithmetic",
                    42,
                ),
                (
                    FIXTURES / "export_module_phrase" / "main.ins",
                    ["-O1"],
                    tmp_path / "export_module_phrase",
                    81,
                ),
                (
                    FIXTURES / "checked_dynamic_buffer_index.ins",
                    ["--runtime-checks"],
                    tmp_path / "checked_dynamic_buffer_index",
                    3,
                ),
            ]
            for fixture, options, executable, expected in cases:
                with self.subTest(fixture=fixture):
                    proc = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "inscription",
                            "compile",
                            str(fixture),
                            "--emit",
                            "executable",
                            *options,
                            "-o",
                            str(executable),
                        ],
                        cwd=ROOT,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stdout, "")
                    self.assertTrue(executable.exists())
                    self.assertGreater(executable.stat().st_size, 0)
                    self.assertTrue(os.access(executable, os.X_OK))
                    run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    self.assertEqual(run.returncode, expected, run.stderr)
                    self.assertEqual(run.stdout, "")

            temps = tmp_path / "exe-temps"
            saved_exe = tmp_path / "saved_phrase_max"
            save_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "executable",
                    "--save-temps",
                    str(temps),
                    "-o",
                    str(saved_exe),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(save_proc.returncode, 0, save_proc.stderr)
            self.assertTrue((temps / "phrase_max.mlir").exists())
            self.assertFalse((temps / "phrase_max.optimized.mlir").exists())
            self.assertTrue((temps / "phrase_max.lowered.mlir").exists())
            self.assertTrue((temps / "phrase_max.ll").exists())
            self.assertTrue((temps / "phrase_max.o").exists())
            self.assertTrue(saved_exe.exists())

            opt_temps = tmp_path / "exe-opt-temps"
            opt_save_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "executable",
                    "-O1",
                    "--save-temps",
                    str(opt_temps),
                    "-o",
                    str(tmp_path / "saved_phrase_max_o1"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(opt_save_proc.returncode, 0, opt_save_proc.stderr)
            self.assertTrue((opt_temps / "phrase_max.mlir").exists())
            self.assertTrue((opt_temps / "phrase_max.optimized.mlir").exists())
            self.assertTrue((opt_temps / "phrase_max.lowered.mlir").exists())
            self.assertTrue((opt_temps / "phrase_max.ll").exists())
            self.assertTrue((opt_temps / "phrase_max.o").exists())

            pipeline = subprocess.run(
                [sys.executable, "-m", "inscription", "check-tools", "--require-executable", "--show-pipeline"],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(pipeline.returncode, 0, pipeline.stderr)
            self.assertIn(f"clang={toolchain.clang}", pipeline.stdout)
            self.assertIn("object emission: llc", pipeline.stdout)
            self.assertIn("executable emission: clang", pipeline.stdout)

    def test_v018_executable_diagnostics_and_link_objects(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        try:
            toolchain = resolve_toolchain(require_executable=True)
        except ToolchainError as exc:
            self.skipTest(str(exc))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            no_main = tmp_path / "no_main.ins"
            no_main.write_text("helper gives i32:\n  0\n")
            no_main_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(no_main),
                    "--emit",
                    "executable",
                    "-o",
                    str(tmp_path / "no_main"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(no_main_proc.returncode, 2)
            self.assertIn("program must define a no-hole main to emit an executable", no_main_proc.stderr)

            missing = tmp_path / "missing_extern.ins"
            missing.write_text("extern missing call gives i32 as definitely_missing_symbol\n\nmain gives i32:\n  missing call\n")
            missing_object = tmp_path / "missing_extern.o"
            object_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(missing),
                    "--emit",
                    "object",
                    "-o",
                    str(missing_object),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(object_proc.returncode, 0, object_proc.stderr)
            self.assertGreater(missing_object.stat().st_size, 0)

            link_fail = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(missing),
                    "--emit",
                    "executable",
                    "-o",
                    str(tmp_path / "missing_extern"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(link_fail.returncode, 2)
            self.assertIn("executable link failed", link_fail.stderr)

            bad_link_object = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "phrase_max.ins"),
                    "--emit",
                    "executable",
                    "--link-object",
                    str(tmp_path / "missing_host.o"),
                    "-o",
                    str(tmp_path / "bad_link_object"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(bad_link_object.returncode, 2)
            self.assertIn("link object", bad_link_object.stderr)

            unsupported_link_object = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "phrase_max.ins"),
                    "--emit",
                    "object",
                    "--link-object",
                    str(missing_object),
                    "-o",
                    str(tmp_path / "phrase_max.o"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(unsupported_link_object.returncode, 2)
            self.assertIn("--link-object is supported only with --emit executable", unsupported_link_object.stderr)

            host_ll = tmp_path / "host_double.ll"
            host_ll.write_text(
                "define i32 @host_double(i32 %x) {\n"
                "entry:\n"
                "  %y = mul i32 %x, 2\n"
                "  ret i32 %y\n"
                "}\n"
            )
            host_object = tmp_path / "host_double.o"
            host_object_proc = subprocess.run(
                [str(toolchain.llc), "-filetype=obj", str(host_ll), "-o", str(host_object)],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(host_object_proc.returncode, 0, host_object_proc.stderr)

            host_source = tmp_path / "host_extern.ins"
            host_source.write_text("extern host double x: i32 gives i32 as host_double\n\nmain gives i32:\n  host double 21\n")
            host_executable = tmp_path / "host_extern"
            host_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(host_source),
                    "--emit",
                    "executable",
                    "--link-object",
                    str(host_object),
                    "-o",
                    str(host_executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(host_proc.returncode, 0, host_proc.stderr)
            run = subprocess.run([str(host_executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 42, run.stderr)


    def test_v019_interface_json_and_c_header(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}

        export_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "export_scalar_gives.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(export_json.returncode, 0, export_json.stderr)
        payload = json.loads(export_json.stdout)
        self.assertEqual(payload["format"], "inscription-interface-v1")
        self.assertEqual(payload["source"], "export_scalar_gives.ins")
        root_module = payload["modules"][0]
        self.assertIsNone(root_module["name"])
        export = root_module["exports"][0]
        self.assertEqual(export["phrase"], "add _ and _")
        self.assertEqual(export["symbol"], "ins_add")
        self.assertEqual(export["parameters"], [{"name": "left", "type": "i32"}, {"name": "right", "type": "i32"}])
        self.assertEqual(export["return"], "i32")

        extern_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "export_calls_extern.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(extern_json.returncode, 0, extern_json.stderr)
        extern_payload = json.loads(extern_json.stdout)
        extern_symbols = {entry["symbol"] for module in extern_payload["modules"] for entry in module["externs"]}
        export_symbols = {entry["symbol"] for module in extern_payload["modules"] for entry in module["exports"]}
        self.assertIn("llvm.ctpop.i32", extern_symbols)
        self.assertIn("ins_popcount", export_symbols)

        layout_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "layout_introspection.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(layout_json.returncode, 0, layout_json.stderr)
        layout_payload = json.loads(layout_json.stdout)
        header = layout_payload["modules"][0]["layout_records"][0]
        self.assertEqual(header["name"], "Header")
        self.assertEqual(header["kind"], "layout-record")
        self.assertEqual(header["size"], 6)
        self.assertEqual(header["alignment"], 2)
        self.assertEqual([field["offset"] for field in header["fields"]], [0, 2, 4])
        self.assertEqual(header["padding_offsets"], [1, 5])

        module_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "export_module_phrase" / "main.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(module_json.returncode, 0, module_json.stderr)
        module_payload = json.loads(module_json.stdout)
        math_module = next(module for module in module_payload["modules"] if module["name"] == "Math")
        self.assertEqual(math_module["path"], "Math.ins")
        self.assertEqual(math_module["exports"][0]["symbol"], "ins_square")

        header_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "export_scalar_gives.ins"),
                "--emit",
                "c-header",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(header_proc.returncode, 0, header_proc.stderr)
        self.assertIn("#pragma once", header_proc.stdout)
        self.assertIn("#include <stdint.h>", header_proc.stdout)
        self.assertIn('extern "C" {', header_proc.stdout)
        self.assertIn("int32_t ins_add(int32_t arg0, int32_t arg1);", header_proc.stdout)

        does_header = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "export_scalar_does.ins"),
                "--emit",
                "c-header",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(does_header.returncode, 0, does_header.stderr)
        self.assertIn("void ins_require_nonnegative(int32_t arg0);", does_header.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            answer = tmp_path / "answer.ins"
            answer.write_text("export answer gives i32 as ins_answer:\n  42\n")
            answer_header = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(answer),
                    "--emit",
                    "c-header",
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(answer_header.returncode, 0, answer_header.stderr)
            self.assertIn("int32_t ins_answer(void);", answer_header.stdout)

            module_header_path = tmp_path / "export_module_phrase.h"
            module_header = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "export_module_phrase" / "main.ins"),
                    "--emit",
                    "c-header",
                    "-o",
                    str(module_header_path),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(module_header.returncode, 0, module_header.stderr)
            self.assertEqual(module_header.stdout, "")
            self.assertIn("int32_t ins_square(int32_t arg0);", module_header_path.read_text())

            try:
                resolve_toolchain(require_object=True)
            except ToolchainError:
                return
            object_path = tmp_path / "export_scalar_gives.o"
            object_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "export_scalar_gives.ins"),
                    "--emit",
                    "object",
                    "-o",
                    str(object_path),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(object_proc.returncode, 0, object_proc.stderr)
            self.assertTrue(object_path.exists())
            self.assertGreater(object_path.stat().st_size, 0)

    def test_v019_c_header_diagnostics(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            narrow = tmp_path / "narrow.ins"
            narrow.write_text("export byte value gives u8 as ins_byte:\n  7\n")
            narrow_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(narrow),
                    "--emit",
                    "c-header",
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(narrow_proc.returncode, 2)
            self.assertIn(
                "C header emission supports exported scalar types i32, u32, i64, u64, f32, and f64 in v0.21; ins_byte uses u8",
                narrow_proc.stderr,
            )

            dotted = tmp_path / "dotted.ins"
            dotted.write_text("export add left: i32 and right: i32 gives i32 as runtime.add:\n  left plus right\n")
            dotted_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(dotted),
                    "--emit",
                    "c-header",
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(dotted_proc.returncode, 2)
            self.assertIn("C header emission requires exported symbol runtime.add to be a C identifier", dotted_proc.stderr)

    def test_v020_static_library_emission_and_save_temps(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        source = FIXTURES / "export_scalar_gives.ins"

        no_output = subprocess.run(
            [sys.executable, "-m", "inscription", "compile", str(source), "--emit", "static-library"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(no_output.returncode, 2)
        self.assertIn("static library emission requires -o OUTPUT", no_output.stderr)

        try:
            toolchain = resolve_toolchain(require_static_library=True)
        except ToolchainError as exc:
            self.skipTest(str(exc))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cases = [
                (source, ["--verify"], tmp_path / "libexport_scalar_gives.a"),
                (source, ["-O2"], tmp_path / "libexport_scalar_gives_o2.a"),
                (FIXTURES / "export_module_phrase" / "main.ins", ["-O1"], tmp_path / "libexport_module_phrase.a"),
                (FIXTURES / "checked_dynamic_buffer_index.ins", ["--runtime-checks"], tmp_path / "libchecked.a"),
            ]
            for fixture, options, archive in cases:
                with self.subTest(fixture=fixture, options=options):
                    proc = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "inscription",
                            "compile",
                            str(fixture),
                            "--emit",
                            "static-library",
                            *options,
                            "-o",
                            str(archive),
                        ],
                        cwd=ROOT,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stdout, "")
                    self.assertTrue(archive.exists())
                    self.assertGreater(archive.stat().st_size, 0)

            temps = tmp_path / "static-temps"
            save_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "static-library",
                    "--save-temps",
                    str(temps),
                    "-o",
                    str(tmp_path / "libsave.a"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(save_proc.returncode, 0, save_proc.stderr)
            self.assertTrue((temps / "export_scalar_gives.mlir").exists())
            self.assertFalse((temps / "export_scalar_gives.optimized.mlir").exists())
            self.assertTrue((temps / "export_scalar_gives.lowered.mlir").exists())
            self.assertTrue((temps / "export_scalar_gives.ll").exists())
            self.assertTrue((temps / "export_scalar_gives.o").exists())

            opt_temps = tmp_path / "static-opt-temps"
            opt_save_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "static-library",
                    "-O1",
                    "--save-temps",
                    str(opt_temps),
                    "-o",
                    str(tmp_path / "libsave_o1.a"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(opt_save_proc.returncode, 0, opt_save_proc.stderr)
            self.assertTrue((opt_temps / "export_scalar_gives.mlir").exists())
            self.assertTrue((opt_temps / "export_scalar_gives.optimized.mlir").exists())
            self.assertTrue((opt_temps / "export_scalar_gives.lowered.mlir").exists())
            self.assertTrue((opt_temps / "export_scalar_gives.ll").exists())
            self.assertTrue((opt_temps / "export_scalar_gives.o").exists())

            missing_archive_object = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "static-library",
                    "-o",
                    str(tmp_path / "libmissing.a"),
                    "--archive-object",
                    str(tmp_path / "missing.o"),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(missing_archive_object.returncode, 2)
            self.assertIn(f"archive object {tmp_path / 'missing.o'} does not exist", missing_archive_object.stderr)

            extra = tmp_path / "extra.o"
            extra.write_bytes(b"not a real object")
            invalid_archive_object_mode = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(source),
                    "--emit",
                    "object",
                    "-o",
                    str(tmp_path / "out.o"),
                    "--archive-object",
                    str(extra),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(invalid_archive_object_mode.returncode, 2)
            self.assertIn("--archive-object is only valid with --emit static-library", invalid_archive_object_mode.stderr)

            pipeline = subprocess.run(
                [sys.executable, "-m", "inscription", "check-tools", "--require-static-library", "--show-pipeline"],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(pipeline.returncode, 0, pipeline.stderr)
            self.assertIn(f"llvm-ar={toolchain.llvm_ar}", pipeline.stdout)
            self.assertIn("static library emission: llvm-ar rcsD output.a output.o", pipeline.stdout)

    def test_v020_c_header_static_library_integration(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        try:
            toolchain = resolve_toolchain(require_executable=True, require_static_library=True)
        except ToolchainError as exc:
            self.skipTest(str(exc))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def compile_header_and_archive(source: Path, header: Path, archive: Path) -> None:
                header_proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "compile",
                        str(source),
                        "--emit",
                        "c-header",
                        "-o",
                        str(header),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(header_proc.returncode, 0, header_proc.stderr)
                archive_proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "compile",
                        str(source),
                        "--emit",
                        "static-library",
                        "-o",
                        str(archive),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(archive_proc.returncode, 0, archive_proc.stderr)

            def compile_and_run_c(c_source: str, header_dir: Path, archive: Path, output: Path, expected: int) -> None:
                caller = output.with_suffix(".c")
                caller.write_text(c_source)
                compile_proc = subprocess.run(
                    [
                        str(toolchain.clang),
                        str(caller),
                        str(archive),
                        "-I",
                        str(header_dir),
                        "-o",
                        str(output),
                    ],
                    cwd=ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(compile_proc.returncode, 0, compile_proc.stderr)
                run = subprocess.run([str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                self.assertEqual(run.returncode, expected, run.stderr)

            add_header = tmp_path / "inscription_export.h"
            add_archive = tmp_path / "libins_add.a"
            compile_header_and_archive(FIXTURES / "export_scalar_gives.ins", add_header, add_archive)
            compile_and_run_c(
                '#include "inscription_export.h"\n\nint main(void) {\n  return ins_add(40, 2);\n}\n',
                tmp_path,
                add_archive,
                tmp_path / "caller_add",
                42,
            )

            module_header = tmp_path / "math.h"
            module_archive = tmp_path / "libmath.a"
            compile_header_and_archive(FIXTURES / "export_module_phrase" / "main.ins", module_header, module_archive)
            compile_and_run_c(
                '#include "math.h"\n\nint main(void) {\n  return ins_square(9);\n}\n',
                tmp_path,
                module_archive,
                tmp_path / "caller_square",
                81,
            )

            host_ll = tmp_path / "host_double.ll"
            host_ll.write_text(
                "define i32 @host_double(i32 %x) {\n"
                "entry:\n"
                "  %y = mul i32 %x, 2\n"
                "  ret i32 %y\n"
                "}\n"
            )
            host_object = tmp_path / "host_double.o"
            host_object_proc = subprocess.run(
                [str(toolchain.llc), "-filetype=obj", str(host_ll), "-o", str(host_object)],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(host_object_proc.returncode, 0, host_object_proc.stderr)

            host_source = tmp_path / "host_double.ins"
            host_source.write_text(
                "extern host double x: i32 gives i32 as host_double\n\n"
                "export exported double x: i32 gives i32 as ins_double:\n"
                "  host double x\n"
            )
            host_header = tmp_path / "host_double.h"
            host_archive = tmp_path / "libhost_double.a"
            header_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(host_source),
                    "--emit",
                    "c-header",
                    "-o",
                    str(host_header),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(header_proc.returncode, 0, header_proc.stderr)
            archive_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(host_source),
                    "--emit",
                    "static-library",
                    "-o",
                    str(host_archive),
                    "--archive-object",
                    str(host_object),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(archive_proc.returncode, 0, archive_proc.stderr)
            compile_and_run_c(
                '#include "host_double.h"\n\nint main(void) {\n  return ins_double(21);\n}\n',
                tmp_path,
                host_archive,
                tmp_path / "caller_host_double",
                42,
            )

    def test_v021_float_scalars_lower_and_emit_interfaces(self):
        arithmetic = compile_source(self.fixture("float_arithmetic.ins"))
        self.assertIn("arith.addf", arithmetic)
        self.assertIn("arith.divf", arithmetic)
        self.assertIn("arith.fptosi", arithmetic)

        comparison = compile_source(self.fixture("float_comparison.ins"))
        self.assertIn("arith.cmpf ogt", comparison)

        casts = compile_source(self.fixture("float_casts.ins"))
        self.assertIn("arith.sitofp", casts)
        self.assertIn("arith.fptosi", casts)

        buffer_view = compile_source(self.fixture("float_buffer_view.ins"))
        self.assertIn("memref<4xf32>", buffer_view)
        self.assertIn("memref<?xf32>", buffer_view)
        self.assertIn("arith.addf", buffer_view)

        record_return = compile_source(self.fixture("float_record_return.ins"))
        self.assertIn("func.func @make_vec(%x: f64, %y: f64) -> (f64, f64)", record_return)
        self.assertIn("arith.mulf", record_return)

        extern_float = compile_source((FIXTURES / "extern_float_compile_only.ins").read_text())
        self.assertIn("func.func private @llvm.sqrt.f64(f64) -> f64", extern_float)
        self.assertIn("func.call @llvm.sqrt.f64", extern_float)

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        interface_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "export_float_multiply.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(interface_proc.returncode, 0, interface_proc.stderr)
        payload = json.loads(interface_proc.stdout)
        export = payload["modules"][0]["exports"][0]
        self.assertEqual(export["symbol"], "ins_multiply_f64")
        self.assertEqual(export["parameters"], [{"name": "x", "type": "f64"}, {"name": "y", "type": "f64"}])
        self.assertEqual(export["return"], "f64")

        header_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "export_float_multiply.ins"),
                "--emit",
                "c-header",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(header_proc.returncode, 0, header_proc.stderr)
        self.assertIn("double ins_multiply_f64(double arg0, double arg1);", header_proc.stdout)

        f32_header_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "export_float_identity.ins"),
                "--emit",
                "c-header",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(f32_header_proc.returncode, 0, f32_header_proc.stderr)
        self.assertIn("float ins_identity_f32(float arg0);", f32_header_proc.stdout)

    def test_v021_float_artifacts_and_run_rejects_float_main(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            llvm_ir = tmp_path / "float_arithmetic.ll"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "float_arithmetic.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_ir),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("define i32 @main", llvm_ir.read_text())

            float_main = tmp_path / "float_main.ins"
            float_main.write_text("main gives f64:\n  1.0\n")
            run_proc = subprocess.run(
                [sys.executable, "-m", "inscription", "run", str(float_main)],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(run_proc.returncode, 2)
            self.assertIn("program main must return an integer scalar, got f64", run_proc.stderr)

            try:
                resolve_toolchain(require_executable=True)
            except ToolchainError:
                return
            executable = tmp_path / "float_arithmetic"
            exe_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "float_arithmetic.ins"),
                    "--emit",
                    "executable",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(exe_proc.returncode, 0, exe_proc.stderr)
            run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 3, run.stderr)

    def test_v022_arrays_and_literal_initialization_lower_and_check(self):
        buffer_containing = compile_source(self.fixture("buffer_containing.ins"))
        self.assertIn("memref.alloca() : memref<4xi32>", buffer_containing)
        self.assertIn("memref.store", buffer_containing)
        self.assertIn("arith.constant 4 : i32", buffer_containing)

        array_sum = compile_source(self.fixture("array_sum.ins"))
        self.assertIn("memref.alloca() : memref<4xi32>", array_sum)
        self.assertIn("memref.load", array_sum)
        self.assertIn("scf.for", array_sum)

        array_length = compile_source(self.fixture("array_length.ins"))
        self.assertIn("arith.constant 4 : i32", array_length)

        array_to_view = compile_source(self.fixture("array_passed_to_view.ins"))
        self.assertIn("memref.cast", array_to_view)
        self.assertIn("memref<?xi32>", array_to_view)

        float_values = compile_source(self.fixture("array_float_values.ins"))
        self.assertIn("memref<3xf64>", float_values)
        self.assertIn("arith.addf", float_values)

        layout_read = compile_source(self.fixture("layout_read_from_array.ins"))
        self.assertIn("memref<2xi8>", layout_read)
        self.assertIn("arith.extui", layout_read)

        checked_index = compile_source(self.fixture("checked_array_index.ins"), runtime_checks=True)
        self.assertIn("storage upper-bound check failed", checked_index)
        checked_view = compile_source(self.fixture("checked_array_view.ins"), runtime_checks=True)
        self.assertIn("view count range check failed", checked_view)

    def test_v022_array_artifacts_and_runtime_checks(self):
        try:
            resolve_toolchain()
        except ToolchainError as exc:
            self.skipTest(str(exc))

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        runtime_cases = [
            ("checked_array_index.ins", ["--runtime-checks"], 3),
            ("checked_array_view.ins", ["--runtime-checks"], 2),
        ]
        for fixture, options, expected in runtime_cases:
            with self.subTest(fixture=fixture):
                proc = subprocess.run(
                    [sys.executable, "-m", "inscription", "run", str(FIXTURES / fixture), *options],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, expected, proc.stderr)
                self.assertEqual(proc.stdout, "")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            llvm_ir = tmp_path / "array_sum.ll"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "array_sum.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_ir),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("define i32 @main", llvm_ir.read_text())

            try:
                resolve_toolchain(require_static_library=True)
            except ToolchainError:
                pass
            else:
                archive = tmp_path / "libarray_sum.a"
                archive_proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "compile",
                        str(FIXTURES / "array_sum.ins"),
                        "--emit",
                        "static-library",
                        "-o",
                        str(archive),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(archive_proc.returncode, 0, archive_proc.stderr)
                self.assertTrue(archive.exists())
                self.assertGreater(archive.stat().st_size, 0)

            try:
                resolve_toolchain(require_executable=True)
            except ToolchainError:
                return
            executable = tmp_path / "array_sum"
            exe_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "array_sum.ins"),
                    "--emit",
                    "executable",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(exe_proc.returncode, 0, exe_proc.stderr)
            run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 10, run.stderr)

    def test_v023_enums_lower_to_underlying_integer_storage(self):
        basic = compile_source(self.fixture("enum_basic.ins"))
        self.assertIn("func.func @choose_mode(%mode: i8) -> i32", basic)
        self.assertIn("arith.cmpi eq", basic)

        casts = compile_source(self.fixture("enum_casts.ins"))
        self.assertIn("arith.extui", casts)
        self.assertIn("return %", casts)

        constants = compile_source(self.fixture("enum_constants_checks.ins"))
        self.assertIn("arith.constant 1 : i8", constants)
        self.assertNotIn("check", constants)

        storage = compile_source(self.fixture("enum_array_buffer_view.ins"))
        self.assertIn("memref<4xi8>", storage)
        self.assertIn("memref<?xi8>", storage)
        self.assertIn("arith.cmpi eq", storage)

        record = compile_source(self.fixture("enum_record_return.ins"))
        self.assertIn("func.func @make_device() -> (i8, i8)", record)
        self.assertIn("return %", record)

        layout = compile_source(self.fixture("enum_layout_record.ins"))
        self.assertIn("memref<2xi8>", layout)
        self.assertIn("arith.cmpi eq", layout)

        layout_write = compile_source(self.fixture("enum_layout_write.ins"))
        self.assertIn("memref.store", layout_write)
        self.assertIn("memref<2xi8>", layout_write)

    def test_v023_module_enums_and_interface_json(self):
        fixture = FIXTURES / "enum_module" / "main.ins"
        mlir = compile_file(fixture, module_root=fixture.parent)
        self.assertIn("func.func @Protocol__choose_mode(%mode: i8) -> i32", mlir)
        self.assertIn("func.call @Protocol__choose_mode", mlir)
        try:
            result = run_file(fixture, module_root=fixture.parent)
        except ToolchainError:
            result = None
        if result is not None:
            self.assertEqual(result.exit_status, 7)

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        enum_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "enum_basic.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(enum_json.returncode, 0, enum_json.stderr)
        payload = json.loads(enum_json.stdout)
        mode = payload["modules"][0]["enums"][0]
        self.assertEqual(mode["name"], "Mode")
        self.assertEqual(mode["kind"], "enum")
        self.assertEqual(mode["underlying_type"], "u8")
        self.assertEqual([case["name"] for case in mode["cases"]], ["idle", "active", "failed"])
        self.assertEqual([case["value"] for case in mode["cases"]], [0, 1, 2])

        layout_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "enum_layout_record.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(layout_json.returncode, 0, layout_json.stderr)
        layout_payload = json.loads(layout_json.stdout)
        header = layout_payload["modules"][0]["layout_records"][0]
        self.assertEqual(header["name"], "Header")
        self.assertEqual(header["size"], 2)
        self.assertEqual([field["type"] for field in header["fields"]], ["Mode", "u8"])
        self.assertEqual([field["offset"] for field in header["fields"]], [0, 1])

        module_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(fixture),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(module_json.returncode, 0, module_json.stderr)
        module_payload = json.loads(module_json.stdout)
        protocol = next(module for module in module_payload["modules"] if module["name"] == "Protocol")
        self.assertEqual(protocol["enums"][0]["name"], "Mode")

        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / "enum_header_wrapper.ins"
            wrapper.write_text(
                "enum Mode: u8:\n"
                "  idle be 0\n"
                "  active be 1\n\n"
                "export active value gives i32 as ins_active_value:\n"
                "  Mode.active as i32\n"
            )
            header = subprocess.run(
                [sys.executable, "-m", "inscription", "compile", str(wrapper), "--emit", "c-header"],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(header.returncode, 0, header.stderr)
            self.assertIn("int32_t ins_active_value(void);", header.stdout)
            root = Path(tmp) / "modules"
            root.mkdir()
            (root / "Protocol.ins").write_text("module Protocol\n\nenum Mode: u8:\n  active be 1\n")
            (root / "Other.ins").write_text("module Other\n\nenum Mode: u8:\n  active be 1\n")
            (root / "main.ins").write_text(
                "import Protocol\n"
                "import Other\n\n"
                "use mode mode: Protocol.Mode gives i32:\n"
                "  0\n\n"
                "main gives i32:\n"
                "  use mode Other.Mode.active\n"
            )
            with self.assertRaises(InscriptionError) as ctx:
                compile_file(root / "main.ins", module_root=root)
            self.assertIn("argument mode must have type Protocol.Mode, got Other.Mode", str(ctx.exception))

    def test_v023_enum_artifacts(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        try:
            resolve_toolchain()
        except ToolchainError as exc:
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            llvm_ir = tmp_path / "enum_basic.ll"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "enum_basic.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_ir),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("define i32 @main", llvm_ir.read_text())

            try:
                resolve_toolchain(require_executable=True)
            except ToolchainError:
                return
            executable = tmp_path / "enum_basic"
            exe_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "enum_basic.ins"),
                    "--emit",
                    "executable",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(exe_proc.returncode, 0, exe_proc.stderr)
            run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 7, run.stderr)

    @unittest.skipUnless(importlib.util.find_spec("pygments"), "Pygments is not installed")
    def test_cli_highlight_outputs_terminal_ansi(self):
        proc = subprocess.run(
            [sys.executable, "-m", "inscription", "highlight", str(FIXTURES / "add.ins")],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(SRC)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("\x1b[", proc.stdout)
        self.assertIn("gives", proc.stdout)
        self.assertEqual(proc.stderr, "")

    @unittest.skipUnless(importlib.util.find_spec("pygments"), "Pygments is not installed")
    def test_cli_highlight_writes_full_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "add.html"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "highlight",
                    str(FIXTURES / "add.ins"),
                    "--format",
                    "html",
                    "--full",
                    "-o",
                    str(output),
                ],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(SRC)},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")
            html = output.read_text()
        self.assertIn("<html", html.lower())
        self.assertIn("gives", html)
        self.assertIn("highlight", html)

    @unittest.skipUnless(importlib.util.find_spec("pygments"), "Pygments is not installed")
    def test_highlight_accepts_full_v0_token_surface(self):
        from inscription.highlighting import highlight_source

        source = "\n".join(
            [
                (GOLDENS / "07_average_with_let.ins").read_text(),
                (GOLDENS / "09_factorial.ins").read_text(),
                (GOLDENS / "12_equals_boolean.ins").read_text(),
                (GOLDENS / "14_loop_sum.ins").read_text(),
                (GOLDENS / "16_gcd.ins").read_text(),
                (GOLDENS / "17_boolean_literals.ins").read_text(),
                (GOLDENS / "19_collatz.ins").read_text(),
                (GOLDENS / "22_boolean_operators.ins").read_text(),
                (GOLDENS / "23_u8_cast.ins").read_text(),
                (GOLDENS / "24_bitwise_flags.ins").read_text(),
                (GOLDENS / "25_shifts.ins").read_text(),
                (GOLDENS / "27_pack_bytes.ins").read_text(),
                (GOLDENS / "28_unsigned_comparison.ins").read_text(),
                (GOLDENS / "29_buffer_sum.ins").read_text(),
                (GOLDENS / "35_fill_buffer_procedure.ins").read_text(),
                (GOLDENS / "39_counted_loop_sum.ins").read_text(),
                (GOLDENS / "41_buffer_length.ins").read_text(),
                (GOLDENS / "43_for_each_fill.ins").read_text(),
                (GOLDENS / "46_record_field_access.ins").read_text(),
                (GOLDENS / "52_record_buffer_interop.ins").read_text(),
                (GOLDENS / "53_layout_introspection.ins").read_text(),
                (GOLDENS / "55_layout_roundtrip.ins").read_text(),
                (GOLDENS / "58_layout_write_procedure.ins").read_text(),
                (GOLDENS / "60_constants_layout_checks.ins").read_text(),
                (GOLDENS / "63_phrase_body_check.ins").read_text(),
                (GOLDENS / "67_module_import.ins").read_text(),
                (GOLDENS / "75_view_parameter_sum.ins").read_text(),
                (GOLDENS / "81_require_divide.ins").read_text(),
                (GOLDENS / "94_extern_ctpop.ins").read_text(),
                (GOLDENS / "99_export_scalar_gives.ins").read_text(),
                (GOLDENS / "105_float_arithmetic.ins").read_text(),
                (GOLDENS / "112_buffer_containing.ins").read_text(),
                (GOLDENS / "113_array_sum.ins").read_text(),
                (GOLDENS / "127_match_enum_expression.ins").read_text(),
                "highlight new widths a: i8 and b: i16 and c: u64 gives u64:\n  c bitwise xor c\n",
                "highlight floats x: f32 and y: f64 gives f64:\n  y plus (x as f64) plus 1.5e2\n",
                "highlight arrays gives i32:\n  let numbers be array of 2 i32 containing 1, 2\n  length of numbers\n",
                "enum HighlightMode: u8:\n  idle be 0\n  active be 1\n\nhighlight enum mode: HighlightMode gives i32:\n  Mode.active as i32\n",
                "union HighlightMaybe:\n  none\n  some value: i32\n\nhighlight union gives i32:\n  match HighlightMaybe.some with value be 1:\n    HighlightMaybe.some with value gives value\n    otherwise gives 0\n",
                "union HighlightToken:\n  eof\n  operator symbol: u8 and precedence: u8\n\nhighlight token gives i32:\n  match HighlightToken.operator with symbol be 1 and precedence be 2:\n    HighlightToken.operator with symbol as op and precedence as prec gives (op as i32) plus (prec as i32)\n    otherwise gives 0\n",
                "highlight bytes gives i32:\n  let text be array of bytes \"A\\n\"\n  match text at 0:\n    byte \"A\" gives length of bytes \"A\\n\"\n    otherwise gives 0\n",
                "highlight owned n: i32 gives i32:\n  let cells be owned buffer of n i32 filled with 1\n  length of cells\n",
            ]
        )
        html = highlight_source(source, output_format="html")
        self.assertNotIn('class="err"', html)

    def test_phrase_call_lowers_to_func_call(self):
        mlir = compile_source(self.fixture("add.ins"))
        self.assertIn("func.func @add", mlir)
        self.assertIn("func.func @main() -> i32", mlir)
        self.assertIn("func.call @add", mlir)
        self.assertIn("arith.addi", mlir)

    def test_value_block_lowers_to_scf_if_result(self):
        mlir = compile_source(self.fixture("phrase_max.ins"))
        self.assertIn("func.func @max", mlir)
        self.assertIn("arith.cmpi sgt", mlir)
        self.assertRegex(mlir, r"%\d+ = scf\.if %\d+ -> \(i32\)")
        self.assertIn("scf.yield", mlir)

    def test_multiple_when_lines_lower_to_nested_scf_if_results(self):
        mlir = compile_source(self.fixture("clamp.ins"))
        self.assertIn("func.func @clamp", mlir)
        self.assertEqual(mlir.count("scf.if"), 2)
        try:
            result = run_source(self.fixture("clamp.ins"))
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 255)

    def test_phrase_body_supports_let_and_word_zero(self):
        source = """absolute value of n: i32 gives i32:
  let flipped be zero minus n
  flipped when n is less than zero
  otherwise n

main gives i32:
  absolute value of -5
"""
        try:
            result = run_source(source)
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 5)

    def test_i64_literals_can_take_type_from_numeric_neighbor(self):
        source = """negate of n: i64 gives i64:
  let flipped be 0 minus n
  flipped when 0 is less than n
  otherwise n
"""
        mlir = compile_source(source)
        self.assertIn("arith.subi %0, %n : i64", mlir)
        self.assertIn("arith.cmpi slt, %0, %n : i64", mlir)

    def test_typed_let_annotation_drives_initializer_type(self):
        source = """one as i64 gives i64:
  let one: i64 be 1
  one
"""
        mlir = compile_source(source)
        self.assertIn("arith.constant 1 : i64", mlir)

    def test_recursive_phrase_call(self):
        mlir = compile_source(self.fixture("recursive_factorial.ins"))
        self.assertIn("func.call @factorial", mlir)
        try:
            result = run_source(self.fixture("recursive_factorial.ins"))
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 120)

    def test_emits_required_core_ops_without_memory_or_custom_dialects(self):
        mlir = compile_source(self.fixture("phrase_max.ins"))
        self.assertIn("func.func @main() -> i32", mlir)
        self.assertIn("arith.cmpi", mlir)
        self.assertIn("scf.if", mlir)
        forbidden = ["memref", "alloca", "llvm.alloca", "global", "store", "load", "scf.while"]
        for needle in forbidden:
            self.assertNotIn(needle, mlir)

    def test_loop_carried_state_lowers_to_scf_while_without_memory(self):
        mlir = compile_source(self.fixture("gcd.ins"))
        self.assertIn("scf.while", mlir)
        self.assertIn("scf.condition", mlir)
        self.assertIn("scf.yield", mlir)
        self.assertIn("arith.remsi", mlir)
        forbidden = ["memref", "alloca", "llvm.alloca", "global", "store", "load"]
        for needle in forbidden:
            self.assertNotIn(needle, mlir)

    def test_v03_scalar_system_ops_lower_to_expected_arith(self):
        source = """ops of x: u32 and y: i8 gives i32:
  let unsigned_half be x divided by 2
  let unsigned_shifted be unsigned_half shifted right by 1
  let signed_shifted be y shifted right by 1
  let inverted be bitwise not (unsigned_shifted as u8)
  let mixed be inverted bitwise xor (signed_shifted as u8)
  let widened be signed_shifted as i32
  (mixed as i32) plus widened
"""
        mlir = compile_source(source)
        self.assertIn("arith.divui", mlir)
        self.assertIn("arith.shrui", mlir)
        self.assertIn("arith.shrsi", mlir)
        self.assertIn("arith.xori", mlir)
        self.assertIn("arith.extui", mlir)
        self.assertIn("arith.extsi", mlir)

    def test_v04_buffers_lower_to_memref_without_heap_alloc(self):
        mlir = compile_source(self.fixture("buffer_sum.ins"))
        self.assertIn("memref.alloca", mlir)
        self.assertIn("memref.store", mlir)
        self.assertIn("memref.load", mlir)
        self.assertIn("scf.for", mlir)
        self.assertIn("arith.index_cast", mlir)
        self.assertNotIn("memref.alloc()", mlir)
        self.assertNotIn("memref.dealloc", mlir)

    def test_v05_buffer_parameters_and_does_phrases_lower_to_memref_calls(self):
        mlir = compile_source(self.fixture("fill_buffer_procedure.ins"))
        self.assertIn("func.func @fill_buffer(%cells: memref<4xi32>, %value: i32)", mlir)
        self.assertIn("func.call @fill_buffer", mlir)
        self.assertIn(": (memref<4xi32>, i32) -> ()", mlir)
        self.assertIn("memref.store %value, %cells", mlir)
        self.assertIn("func.func @sum_buffer(%cells: memref<4xi32>) -> i32", mlir)

    def test_v06_for_loops_and_length_lower_to_scf_for(self):
        mlir = compile_source(self.fixture("for_each_fill.ins"))
        self.assertIn("func.func @fill_each(%cells: memref<4xi32>, %value: i32)", mlir)
        self.assertIn("scf.for", mlir)
        self.assertIn("iter_args", mlir)
        self.assertIn("arith.index_cast", mlir)
        self.assertIn("memref.store %value, %cells", mlir)

        length_mlir = compile_source(self.fixture("buffer_length.ins"))
        self.assertIn("arith.constant 4 : i32", length_mlir)
        self.assertNotIn("memref.dim", length_mlir)

        length_bound_mlir = compile_source(
            "sum by length cells: buffer of 4 i32 gives i32:\n"
            "  let total be 0\n"
            "  for i from 0 up to length of cells:\n"
            "    total becomes total plus cells at i\n"
            "  total\n"
        )
        self.assertIn("arith.constant 4 : i32", length_bound_mlir)
        self.assertIn("scf.for", length_bound_mlir)

    def test_v07_records_flatten_to_scalar_ssa(self):
        mlir = compile_source(self.fixture("record_field_access.ins"))
        self.assertIn("func.func @sum_point(%p_x: i32, %p_y: i32) -> i32", mlir)
        self.assertIn("func.call @sum_point", mlir)
        self.assertNotIn("llvm.struct", mlir)
        self.assertNotIn("tensor", mlir)

        loop_mlir = compile_source(self.fixture("record_loop_carry.ins"))
        self.assertIn("iter_args(%p_x_iter", loop_mlir)
        self.assertIn("%p_y_iter", loop_mlir)
        self.assertIn("scf.yield", loop_mlir)

        interop_mlir = compile_source(self.fixture("record_buffer_interop.ins"))
        self.assertIn("func.func @write_offset(%offset_index: i32, %offset_value: i32, %cells: memref<4xi32>)", interop_mlir)
        self.assertIn("memref.store %offset_value", interop_mlir)

    def test_v08_layout_records_lower_to_byte_serialization(self):
        introspection_mlir = compile_source(self.fixture("layout_introspection.ins"))
        self.assertIn("arith.constant 6 : i32", introspection_mlir)
        self.assertIn("arith.constant 2 : i32", introspection_mlir)
        self.assertIn("arith.constant 4 : i32", introspection_mlir)

        roundtrip_mlir = compile_source(self.fixture("layout_roundtrip.ins"))
        self.assertIn("memref.store", roundtrip_mlir)
        self.assertIn("memref.load", roundtrip_mlir)
        self.assertIn("arith.extui", roundtrip_mlir)
        self.assertIn("arith.shrui", roundtrip_mlir)
        self.assertIn("arith.trunci", roundtrip_mlir)
        self.assertNotIn("llvm.struct", roundtrip_mlir)

    def test_v09_constants_checks_and_compile_time_lengths_emit_inline_constants(self):
        constants_mlir = compile_source(self.fixture("constants_layout_checks.ins"))
        self.assertIn("arith.constant 6 : i32", constants_mlir)
        self.assertIn("arith.constant 4 : i32", constants_mlir)
        self.assertNotIn("global", constants_mlir)

        length_mlir = compile_source(self.fixture("constant_buffer_length.ins"))
        self.assertIn("memref<4xi32>", length_mlir)
        self.assertIn("func.func @sum_cells(%cells: memref<4xi32>) -> i32", length_mlir)

        check_mlir = compile_source(self.fixture("phrase_body_check.ins"))
        self.assertIn("memref<6xi8>", check_mlir)
        self.assertNotIn("check", check_mlir)


    def test_v010_modules_import_qualified_phrases(self):
        mlir = compile_file(FIXTURES / "module_import_main.ins", module_root=FIXTURES)
        self.assertIn("func.func @modules__math__add", mlir)
        self.assertIn("func.call @modules__math__add", mlir)
        self.assertNotIn("func.func @add", mlir)

    def test_v011_views_lower_to_dynamic_memref_base_start_length(self):
        mlir = compile_source(self.fixture("view_parameter_sum.ins"))
        self.assertIn("func.func @sum_view(%cells_base: memref<?xi32>, %cells_start: i32, %cells_length: i32) -> i32", mlir)
        self.assertIn("memref.cast", mlir)
        self.assertIn("func.call @sum_view", mlir)
        self.assertIn(": (memref<?xi32>, i32, i32) -> i32", mlir)

        local_mlir = compile_source(self.fixture("local_view_sum.ins"))
        self.assertIn("memref.load", local_mlir)
        self.assertIn("arith.addi", local_mlir)
        self.assertIn("memref<?xi32>", local_mlir)

        layout_mlir = compile_source(self.fixture("layout_read_from_view.ins"))
        self.assertIn("memref<?xi8>", layout_mlir)
        self.assertIn("arith.extui", layout_mlir)

    def test_v012_require_and_runtime_checks_lower_to_cf_assert(self):
        mlir = compile_source(self.fixture("require_divide.ins"))
        self.assertIn('cf.assert', mlir)
        self.assertIn('require failed at line 2', mlir)
        self.assertIn("arith.divsi", mlir)

        static_require_mlir = compile_source("always valid gives i32:\n  require true\n  7\n")
        self.assertNotIn("cf.assert", static_require_mlir)

        unchecked = compile_source(self.fixture("checked_dynamic_buffer_index.ins"))
        checked = compile_source(self.fixture("checked_dynamic_buffer_index.ins"), runtime_checks=True)
        self.assertNotIn("cf.assert", unchecked)
        self.assertIn("storage lower-bound check failed", checked)
        self.assertIn("storage upper-bound check failed", checked)

        checked_view = compile_source(self.fixture("checked_dynamic_view.ins"), runtime_checks=True)
        self.assertIn("view start range check failed", checked_view)
        self.assertIn("view count range check failed", checked_view)

        checked_layout = compile_source(self.fixture("checked_dynamic_layout.ins"), runtime_checks=True)
        self.assertIn("storage range check failed", checked_layout)

    def test_v013_record_returns_lower_to_flattened_results(self):
        mlir = compile_source(self.fixture("record_return_constructor.ins"))
        self.assertIn("func.func @make_point(%x: i32, %y: i32) -> (i32, i32)", mlir)
        self.assertIn("return %x, %y : i32, i32", mlir)
        self.assertIn("func.call @make_point", mlir)
        self.assertIn("-> (i32, i32)", mlir)
        self.assertNotIn("llvm.struct", mlir)
        self.assertNotIn("tensor", mlir)

        guarded_mlir = compile_source(self.fixture("record_return_guarded.ins"))
        self.assertIn("scf.if %flag -> (i32, i32)", guarded_mlir)
        self.assertIn("scf.yield", guarded_mlir)

        layout_mlir = compile_source(self.fixture("layout_record_return.ins"))
        self.assertIn("func.func @parse_word", layout_mlir)
        self.assertIn("memref.load", layout_mlir)
        self.assertIn("return %", layout_mlir)

    def test_v013_module_record_return_uses_qualified_nominal_type(self):
        fixture = FIXTURES / "module_record_return" / "main.ins"
        mlir = compile_file(fixture, module_root=fixture.parent)
        self.assertIn("func.func @Geometry__make_point", mlir)
        self.assertIn("func.call @Geometry__make_point", mlir)
        try:
            result = run_file(fixture, module_root=fixture.parent)
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 30)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Geometry.ins").write_text(
                "module Geometry\n\n"
                "record Point:\n  x: i32\n  y: i32\n\n"
                "make point gives Point:\n  Point with x be 1 and y be 2\n"
            )
            (root / "Other.ins").write_text("module Other\n\nrecord Point:\n  x: i32\n  y: i32\n")
            self.assertIn(
                "let p must have type Other.Point, got Geometry.Point",
                self._compile_file_error(
                    root,
                    "import Geometry\nimport Other\n\nmain gives i32:\n  let p: Other.Point be Geometry.make point\n  p.x\n",
                ),
            )

    def test_v013_run_rejects_record_returning_main(self):
        source = """record Point:
  x: i32
  y: i32

main gives Point:
  Point with x be 1 and y be 2
"""
        with self.assertRaises(InscriptionError) as ctx:
            run_source(source)
        self.assertIn("program main must return an integer scalar, got Point", str(ctx.exception))

        with self.assertRaises(InscriptionError) as bool_ctx:
            run_source("main gives i1:\n  true\n")
        self.assertIn("program main must return an integer scalar, got i1", str(bool_ctx.exception))

    def test_v014_extern_phrases_lower_to_external_declarations(self):
        mlir = compile_source(self.fixture("extern_ctpop.ins"))
        self.assertIn("func.func private @llvm.ctpop.i32(i32) -> i32", mlir)
        self.assertIn("func.call @llvm.ctpop.i32", mlir)
        self.assertNotIn("func.func @population_count", mlir)
        try:
            result = run_source(self.fixture("extern_ctpop.ins"))
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 4)

        loop_mlir = compile_source(self.fixture("extern_in_loop.ins"))
        self.assertIn("scf.for", loop_mlir)
        self.assertIn("func.call @llvm.ctpop.i32", loop_mlir)

        constant_mlir = compile_source(self.fixture("extern_constant_argument.ins"))
        self.assertIn("arith.constant 15 : i32", constant_mlir)
        self.assertIn("func.call @llvm.ctpop.i32", constant_mlir)

        does_mlir = compile_source(self.fixture("extern_does_compile_only.ins"))
        self.assertIn("func.func private @host_notify(i32)", does_mlir)
        self.assertIn("func.call @host_notify", does_mlir)

        duplicate_symbol_mlir = compile_source(
            "extern pop of x: i32 gives i32 as llvm.ctpop.i32\n"
            "extern count bits of x: i32 gives i32 as llvm.ctpop.i32\n\n"
            "main gives i32:\n"
            "  pop of 15 plus count bits of 15\n"
        )
        self.assertEqual(duplicate_symbol_mlir.count("func.func private @llvm.ctpop.i32"), 1)

    def test_v014_module_extern_phrase_uses_external_symbol(self):
        fixture = FIXTURES / "extern_module_intrinsic" / "main.ins"
        mlir = compile_file(fixture, module_root=fixture.parent)
        self.assertIn("func.func private @llvm.ctpop.i32(i32) -> i32", mlir)
        self.assertIn("func.call @llvm.ctpop.i32", mlir)
        self.assertNotIn("Intrinsics__population_count", mlir)
        try:
            result = run_file(fixture, module_root=fixture.parent)
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 4)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "A.ins").write_text(
                "module A\n\nextern pop of x: i32 gives i32 as host_pop\n"
            )
            (root / "B.ins").write_text(
                "module B\n\nextern pop of x: i64 gives i64 as host_pop\n"
            )
            self.assertIn(
                "external symbol host_pop declared with incompatible types",
                self._compile_file_error(root, "import A\nimport B\n\nmain gives i32:\n  A.pop of 1\n"),
            )

            (root / "Intrinsics.ins").write_text(
                "module Intrinsics\n\nextern population count of x: i32 gives i32 as llvm.ctpop.i32\n"
            )
            self.assertIn(
                "unexpected token 'count'",
                self._compile_file_error(root, "import Intrinsics\n\nmain gives i32:\n  population count of 15\n"),
            )

            missing_symbol_mlir = compile_source(
                "extern missing call gives i32 as definitely_missing_symbol\n\nmain gives i32:\n  missing call\n"
            )
            self.assertIn("func.func private @definitely_missing_symbol() -> i32", missing_symbol_mlir)

    def test_v015_exported_phrases_lower_to_public_symbols(self):
        mlir = compile_source(self.fixture("export_scalar_gives.ins"))
        self.assertIn("func.func @ins_add(%left: i32, %right: i32) -> i32", mlir)
        self.assertIn("func.call @ins_add", mlir)
        self.assertNotIn("func.func @add", mlir)
        try:
            result = run_source(self.fixture("export_scalar_gives.ins"))
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 42)

        does_mlir = compile_source(self.fixture("export_scalar_does.ins"))
        self.assertIn("func.func @ins_require_nonnegative(%value: i32)", does_mlir)
        self.assertIn("cf.assert", does_mlir)
        self.assertIn("func.call @ins_require_nonnegative", does_mlir)

        extern_mlir = compile_source(self.fixture("export_calls_extern.ins"))
        self.assertIn("func.func private @llvm.ctpop.i32(i32) -> i32", extern_mlir)
        self.assertIn("func.func @ins_popcount(%x: i32) -> i32", extern_mlir)
        self.assertIn("func.call @llvm.ctpop.i32", extern_mlir)
        self.assertIn("func.call @ins_popcount", extern_mlir)

        record_mlir = compile_source(self.fixture("export_uses_record_local.ins"))
        self.assertIn("func.func @ins_make_and_sum(%x: i32, %y: i32) -> i32", record_mlir)
        self.assertIn("arith.addi", record_mlir)

        buffer_mlir = compile_source(self.fixture("export_uses_buffer_local.ins"))
        self.assertIn("func.func @ins_sum_local_buffer() -> i32", buffer_mlir)
        self.assertIn("memref.alloca", buffer_mlir)
        self.assertIn("scf.for", buffer_mlir)

    def test_v015_module_exported_phrase_uses_public_symbol(self):
        fixture = FIXTURES / "export_module_phrase" / "main.ins"
        mlir = compile_file(fixture, module_root=fixture.parent)
        self.assertIn("func.func @ins_square(%x: i32) -> i32", mlir)
        self.assertIn("func.call @ins_square", mlir)
        self.assertNotIn("Math__square", mlir)
        try:
            result = run_file(fixture, module_root=fixture.parent)
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 81)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Math.ins").write_text(
                "module Math\n\nexport square of x: i32 gives i32 as ins_square:\n  x times x\n"
            )
            self.assertIn(
                "unexpected token 'of'",
                self._compile_file_error(root, "import Math\n\nmain gives i32:\n  square of 9\n"),
            )

            (root / "A.ins").write_text(
                "module A\n\nexport add x: i32 and y: i32 gives i32 as ins_add:\n  x plus y\n"
            )
            (root / "B.ins").write_text(
                "module B\n\nexport sub x: i32 and y: i32 gives i32 as ins_add:\n  x minus y\n"
            )
            self.assertIn(
                "exported symbol ins_add is already defined",
                self._compile_file_error(root, "import A\nimport B\n\nmain gives i32:\n  A.add 1 and 2\n"),
            )

    def test_v010_module_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "math.ins").write_text("module math\n\nadd a: i32 and b: i32 gives i32:\n  a plus b\n")
            self.assertIn(
                "unexpected token '1'",
                self._compile_file_error(root, "import math\n\nmain gives i32:\n  add 1 and 2\n"),
            )

            (root / "wrong.ins").write_text("module other\n\nvalue gives i32:\n  0\n")
            self.assertIn(
                "module declaration other does not match import wrong",
                self._compile_file_error(root, "import wrong\n\nmain gives i32:\n  0\n"),
            )

            (root / "plain.ins").write_text("value gives i32:\n  0\n")
            self.assertIn(
                "must declare module plain",
                self._compile_file_error(root, "import plain\n\nmain gives i32:\n  0\n"),
            )

            (root / "a.ins").write_text("module a\nimport b\n\na gives i32:\n  0\n")
            (root / "b.ins").write_text("module b\nimport a\n\nb gives i32:\n  0\n")
            self.assertIn(
                "import cycle detected: a -> b -> a",
                self._compile_file_error(root, "import a\n\nmain gives i32:\n  0\n"),
            )

    def _compile_file_error(self, root: Path, source: str) -> str:
        path = root / "main.ins"
        path.write_text(source)
        with self.assertRaises(InscriptionError) as ctx:
            compile_file(path, module_root=root)
        return str(ctx.exception)

    def test_record_parameter_rebinding_does_not_mutate_caller(self):
        source = """record Point:
  x: i32
  y: i32

move point p: Point by dx: i32 and dy: i32 gives i32:
  p.x becomes p.x plus dx
  p.y becomes p.y plus dy
  p.x plus p.y

main gives i32:
  let p be Point with x be 1 and y be 2
  let moved be move point p by 3 and 4
  p.x plus p.y
"""
        try:
            result = run_source(source)
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 3)

    def test_valid_identifier_cannot_collide_with_generated_ssa_names(self):
        source = """echo of v0: i32 gives i32:
  v0

main gives i32:
  echo of 7
"""
        mlir = compile_source(source)
        self.assertIn("func.func @echo(%v0: i32) -> i32", mlir)
        try:
            result = run_source(source)
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 7)

    def test_output_is_deterministic(self):
        source = self.fixture("recursive_factorial.ins")
        self.assertEqual(compile_source(source), compile_source(source))

    def test_llvm22_toolchain_and_pipeline_are_exact(self):
        try:
            toolchain = resolve_toolchain()
        except ToolchainError as exc:
            self.skipTest(str(exc))
        expected_root = Path(os.environ.get("MLIR_TOOLCHAIN", "/usr/lib/llvm-22/bin"))
        self.assertEqual(toolchain.root, expected_root)
        self.assertEqual(
            LOWERING_PASSES,
            [
                "--convert-scf-to-cf",
                "--convert-cf-to-llvm",
                "--convert-arith-to-llvm",
                "--expand-strided-metadata",
                "--finalize-memref-to-llvm",
                "--convert-func-to-llvm",
                "--reconcile-unrealized-casts",
            ],
        )
        self.assertEqual(
            OPTIMIZATION_PRESETS,
            {
                "none": (),
                "basic": ("--canonicalize", "--cse"),
                "aggressive": (
                    "--canonicalize",
                    "--cse",
                    "--sccp",
                    "--canonicalize",
                    "--cse",
                    "--control-flow-sink",
                    "--loop-invariant-code-motion",
                    "--canonicalize",
                    "--cse",
                ),
            },
        )
        verify_mlir(compile_source(self.fixture("add.ins")), toolchain)

    def assertCompileError(self, source: str, contains: str):
        with self.assertRaises(InscriptionError) as ctx:
            compile_source(source)
        self.assertIn(contains, str(ctx.exception))

    def assertCompileErrorWithRuntimeChecks(self, source: str, contains: str):
        with self.assertRaises(InscriptionError) as ctx:
            compile_source(source, runtime_checks=True)
        self.assertIn(contains, str(ctx.exception))

    def test_v012_runtime_checks_preserve_static_diagnostics(self):
        self.assertCompileErrorWithRuntimeChecks(
            "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  cells at 4\n",
            "buffer index 4 is out of bounds for buffer cells of length 4",
        )
        self.assertCompileErrorWithRuntimeChecks(
            "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let window be view of cells from 3 for 2\n  0\n",
            "view range 3 for 2 exceeds source cells of length 4",
        )
        self.assertCompileErrorWithRuntimeChecks(
            "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let bytes be buffer of 2 u8 filled with 0\n  let word be read Word from bytes at 1\n  0\n",
            "read Word at index 1 exceeds buffer bytes of length 2",
        )

    def test_phrase_definitions_reject_unsupported_types(self):
        self.assertCompileError(
            "identity of x: f16 gives i32:\n  x\n\nmain gives i32:\n  0\n",
            "supported scalar types",
        )
        self.assertCompileError(
            "identity of x: i32 gives f16:\n  x\n\nmain gives i32:\n  0\n",
            "supported scalar types",
        )

    def test_value_block_requires_otherwise_after_when(self):
        self.assertCompileError(
            "max of a: i32 and b: i32 gives i32:\n  a when a is greater than b\n\nmain gives i32:\n  max of 1 and 2\n",
            "requires an otherwise",
        )

    def test_let_bindings_must_precede_value_block(self):
        self.assertCompileError(
            "main gives i32:\n  1\n  let x be 2\n",
            "let bindings must appear before",
        )

    def test_legacy_statement_ceremony_is_rejected(self):
        self.assertCompileError(
            "Function main takes no parameters.\nReturn 0.\nEnd function.\n",
            "expected phrase definition",
        )
        self.assertCompileError("main gives i32:\n  Return 0\n", "invalid token")
        self.assertCompileError(
            "add a: i32 and b: i32 gives i32:\n  a plus b\n\nmain gives i32:\n  call add with 1 and 2\n",
            "unexpected token 'call'",
        )
        self.assertCompileError("main gives i32:\n  Set result to 1\n", "invalid token")

    def test_v024_match_expressions_and_blocks(self):
        enum_match = compile_source(self.fixture("match_enum_expression.ins"))
        self.assertIn("scf.if", enum_match)
        self.assertIn("arith.cmpi eq", enum_match)

        integer_match = compile_source(self.fixture("match_integer_expression.ins"))
        self.assertIn("func.func @classify(%code: i32) -> i32", integer_match)
        self.assertIn("arith.cmpi eq", integer_match)

        step_match = compile_source(self.fixture("match_enum_steps.ins"))
        self.assertIn("scf.if", step_match)
        self.assertIn("scf.for", step_match)

        record_match = compile_source(self.fixture("match_record_result.ins"))
        self.assertIn("func.func @point_for_mode(%mode: i8) -> (i32, i32)", record_match)
        self.assertIn("scf.if", record_match)

        compile_time = compile_source(self.fixture("match_compile_time.ins"))
        self.assertIn("arith.constant 7 : i32", compile_time)
        self.assertNotIn("match", compile_time)

        boolean_match = compile_source(self.fixture("match_boolean.ins"))
        self.assertIn("arith.cmpi eq", boolean_match)

        let_match = compile_source(self.fixture("match_expression_let.ins"))
        self.assertIn("arith.constant 42 : i32", let_match)

    def test_v024_module_match_and_artifacts(self):
        fixture = FIXTURES / "match_module_enum" / "main.ins"
        mlir = compile_file(fixture, module_root=fixture.parent)
        self.assertIn("func.func @code_for_mode(%mode: i8) -> i32", mlir)
        self.assertIn("scf.if", mlir)
        try:
            result = run_file(fixture, module_root=fixture.parent)
        except ToolchainError:
            result = None
        if result is not None:
            self.assertEqual(result.exit_status, 7)

        try:
            resolve_toolchain()
        except ToolchainError:
            return
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            llvm_path = tmp_path / "match_enum_expression.ll"
            llvm_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "match_enum_expression.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_path),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(llvm_proc.returncode, 0, llvm_proc.stderr)
            self.assertIn("define i32 @main", llvm_path.read_text())

            try:
                resolve_toolchain(require_executable=True)
            except ToolchainError:
                return
            executable = tmp_path / "match_enum_expression"
            exe_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "match_enum_expression.ins"),
                    "--emit",
                    "executable",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(exe_proc.returncode, 0, exe_proc.stderr)
            run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 7, run.stderr)

    def test_v025_unions_lower_to_flattened_tag_and_payload_slots(self):
        basic = compile_source(self.fixture("union_basic.ins"))
        self.assertIn("func.func @value_or_zero(%maybe_tag: i32, %maybe_some_value: i32) -> i32", basic)
        self.assertIn("arith.cmpi eq", basic)
        self.assertIn("scf.if", basic)

        payload_free = compile_source(self.fixture("union_payload_match.ins"))
        self.assertIn("func.func @code_for_door(%door_tag: i32) -> i32", payload_free)
        self.assertIn("arith.constant 1 : i32", payload_free)

        union_return = compile_source(self.fixture("union_return.ins"))
        self.assertIn("func.func @make_maybe(%flag: i1) -> (i32, i32)", union_return)
        self.assertIn("func.call @make_maybe", union_return)

        rebinding = compile_source(self.fixture("union_rebinding.ins"))
        self.assertIn("MaybeI32", self.fixture("union_rebinding.ins"))
        self.assertIn("arith.constant 5 : i32", rebinding)

        record_payload = compile_source(self.fixture("union_record_payload.ins"))
        self.assertIn("scf.if", record_payload)
        self.assertIn("arith.addi", record_payload)

        step_match = compile_source(self.fixture("union_match_steps.ins"))
        self.assertIn("scf.if", step_match)
        self.assertIn("arith.extui", step_match)

        guarded_return = compile_source(self.fixture("union_guarded_return.ins"))
        self.assertIn("func.func @choose_maybe(%flag: i1) -> (i32, i32)", guarded_return)
        self.assertIn("scf.if", guarded_return)

        require_match = compile_source(self.fixture("union_require.ins"))
        self.assertIn("cf.assert", compile_source(self.fixture("union_require.ins"), runtime_checks=True))
        self.assertIn("scf.if", require_match)

    def test_v025_module_unions_interface_json_and_artifacts(self):
        fixture = FIXTURES / "union_module" / "main.ins"
        mlir = compile_file(fixture, module_root=fixture.parent)
        self.assertIn("func.func @Maybe__value_or_zero(%maybe_tag: i32, %maybe_some_value: i32) -> i32", mlir)
        self.assertIn("func.call @Maybe__value_or_zero", mlir)
        try:
            result = run_file(fixture, module_root=fixture.parent)
        except ToolchainError:
            result = None
        if result is not None:
            self.assertEqual(result.exit_status, 7)

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        union_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "union_basic.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(union_json.returncode, 0, union_json.stderr)
        payload = json.loads(union_json.stdout)
        maybe = payload["modules"][0]["unions"][0]
        self.assertEqual(maybe["name"], "MaybeI32")
        self.assertEqual(maybe["kind"], "union")
        self.assertEqual(maybe["tag_type"], "i32")
        self.assertEqual(maybe["variants"][0], {"name": "none", "tag": 0, "payloads": []})
        self.assertEqual(
            maybe["variants"][1],
            {"name": "some", "tag": 1, "payloads": [{"name": "value", "type": "i32"}]},
        )

        module_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(fixture),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(module_json.returncode, 0, module_json.stderr)
        module_payload = json.loads(module_json.stdout)
        maybe_module = next(module for module in module_payload["modules"] if module["name"] == "Maybe")
        self.assertEqual(maybe_module["unions"][0]["name"], "MaybeI32")

        with tempfile.TemporaryDirectory() as tmp:
            union_main = Path(tmp) / "union_main.ins"
            union_main.write_text("union MaybeI32:\n  none\n\nmain gives MaybeI32:\n  MaybeI32.none\n")
            run_union_main = subprocess.run(
                [sys.executable, "-m", "inscription", "run", str(union_main)],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(run_union_main.returncode, 2)
            self.assertIn("program main must return an integer scalar, got MaybeI32", run_union_main.stderr)

        try:
            resolve_toolchain()
        except ToolchainError:
            return
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            llvm_path = tmp_path / "union_basic.ll"
            llvm_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "union_basic.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_path),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(llvm_proc.returncode, 0, llvm_proc.stderr)
            self.assertIn("define i32 @main", llvm_path.read_text())

            try:
                resolve_toolchain(require_executable=True)
            except ToolchainError:
                return
            executable = tmp_path / "union_basic"
            exe_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "union_basic.ins"),
                    "--emit",
                    "executable",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(exe_proc.returncode, 0, exe_proc.stderr)
            run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 7, run.stderr)

    def test_v026_multi_payload_unions_and_aliases(self):
        basic = compile_source(self.fixture("union_multi_payload_basic.ins"))
        self.assertIn(
            "func.func @score_token(%token_tag: i32, %token_operator_symbol: i8, %token_operator_precedence: i8) -> i32",
            basic,
        )
        self.assertIn("arith.extui %token_operator_symbol", basic)
        self.assertIn("arith.extui %token_operator_precedence", basic)

        alias = compile_source(self.fixture("union_payload_alias.ins"))
        self.assertIn("arith.constant 10 : i8", alias)
        self.assertIn("arith.addi", alias)

        union_return = compile_source(self.fixture("union_multi_payload_return.ins"))
        self.assertIn("func.func @make_operator() -> (i32, i64, i8, i8)", union_return)
        self.assertIn("func.call @make_operator", union_return)

        record_payload = compile_source(self.fixture("union_multi_record_payload.ins"))
        self.assertIn("arith.constant 3 : i32", record_payload)
        self.assertIn("arith.constant 4 : i32", record_payload)
        self.assertIn("arith.constant 2 : i8", record_payload)

        step_match = compile_source(self.fixture("union_multi_match_steps.ins"))
        self.assertIn("func.func @main() -> i32", step_match)
        self.assertIn("scf.if", step_match)

        guarded = compile_source(self.fixture("union_multi_guarded_result.ins"))
        self.assertIn("func.func @choose_token(%flag: i1) -> (i32, i8, i8)", guarded)
        self.assertIn("scf.if", guarded)

    def test_v026_multi_payload_union_module_interface_and_artifacts(self):
        fixture = FIXTURES / "union_multi_module" / "main.ins"
        mlir = compile_file(fixture, module_root=fixture.parent)
        self.assertIn("func.func @Tokens__score_token(%token_tag: i32, %token_operator_symbol: i8, %token_operator_precedence: i8) -> i32", mlir)
        try:
            result = run_file(fixture, module_root=fixture.parent)
        except ToolchainError:
            result = None
        if result is not None:
            self.assertEqual(result.exit_status, 15)

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        union_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "union_multi_payload_basic.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(union_json.returncode, 0, union_json.stderr)
        payload = json.loads(union_json.stdout)
        token = payload["modules"][0]["unions"][0]
        self.assertEqual(token["name"], "Token")
        self.assertEqual(token["variants"][0], {"name": "eof", "tag": 0, "payloads": []})
        self.assertEqual(
            token["variants"][1],
            {
                "name": "operator",
                "tag": 1,
                "payloads": [{"name": "symbol", "type": "u8"}, {"name": "precedence", "type": "u8"}],
            },
        )

        try:
            resolve_toolchain()
        except ToolchainError:
            return
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            llvm_path = tmp_path / "union_multi_payload_basic.ll"
            llvm_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "union_multi_payload_basic.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_path),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(llvm_proc.returncode, 0, llvm_proc.stderr)
            self.assertIn("define i32 @main", llvm_path.read_text())

            try:
                resolve_toolchain(require_executable=True)
            except ToolchainError:
                return
            executable = tmp_path / "union_multi_payload_basic"
            exe_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "union_multi_payload_basic.ins"),
                    "--emit",
                    "executable",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(exe_proc.returncode, 0, exe_proc.stderr)
            run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 15, run.stderr)

    def test_v027_type_aliases_lower_transparently(self):
        scalar = compile_source(self.fixture("type_alias_scalar.ins"))
        self.assertIn("func.func @add_counts(%left: i32, %right: i32) -> i32", scalar)
        self.assertIn("arith.addi %left, %right : i32", scalar)

        buffer_array = compile_source(self.fixture("type_alias_buffer_array.ins"))
        self.assertIn("memref.alloca() : memref<4xi32>", buffer_array)
        self.assertIn("memref.store", buffer_array)

        storage = compile_source(self.fixture("type_alias_storage.ins"))
        self.assertIn("memref.alloca() : memref<4xi32>", storage)
        self.assertIn("scf.for", storage)

        view_parameter = compile_source(self.fixture("type_alias_view_parameter.ins"))
        self.assertIn("func.func @sum_cells(%cells_base: memref<?xi32>, %cells_start: i32, %cells_length: i32) -> i32", view_parameter)

        record_union = compile_source(self.fixture("type_alias_record_union.ins"))
        self.assertIn("func.func @score_maybe(%maybe_tag: i32", record_union)
        self.assertIn("arith.cmpi eq", record_union)

        layout_enum = compile_source(self.fixture("type_alias_layout_enum.ins"))
        self.assertIn("memref.alloca() : memref<3xi8>", layout_enum)
        self.assertIn("arith.cmpi eq", layout_enum)

        header_export = compile_source(self.fixture("type_alias_export_header.ins"))
        self.assertIn("func.func @ins_add_counts(%left: i32, %right: i32) -> i32", header_export)

    def test_v027_module_alias_interface_header_and_artifacts(self):
        fixture = FIXTURES / "type_alias_module" / "main.ins"
        mlir = compile_file(fixture, module_root=fixture.parent)
        self.assertIn("func.func @Types__sum_cells(%cells_base: memref<?xi32>, %cells_start: i32, %cells_length: i32) -> i32", mlir)
        try:
            result = run_file(fixture, module_root=fixture.parent)
        except ToolchainError:
            result = None
        if result is not None:
            self.assertEqual(result.exit_status, 12)

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        alias_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "type_alias_scalar.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(alias_json.returncode, 0, alias_json.stderr)
        payload = json.loads(alias_json.stdout)
        self.assertEqual(
            payload["modules"][0]["type_aliases"][0],
            {"name": "Count", "kind": "type-alias", "target": "i32"},
        )

        storage_json = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "type_alias_storage.ins"),
                "--emit",
                "interface-json",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(storage_json.returncode, 0, storage_json.stderr)
        storage_payload = json.loads(storage_json.stdout)
        aliases = {entry["name"]: entry["target"] for entry in storage_payload["modules"][0]["type_aliases"]}
        self.assertEqual(aliases["CellBuffer"], "buffer of 4 i32")
        self.assertEqual(aliases["CellArray"], "array of 4 i32")

        header_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "type_alias_export_header.ins"),
                "--emit",
                "c-header",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(header_proc.returncode, 0, header_proc.stderr)
        self.assertIn("int32_t ins_add_counts(int32_t arg0, int32_t arg1);", header_proc.stdout)

        float_header_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "compile",
                str(FIXTURES / "type_alias_export_float_header.ins"),
                "--emit",
                "c-header",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(float_header_proc.returncode, 0, float_header_proc.stderr)
        self.assertIn("double ins_multiply_weights(double arg0, double arg1);", float_header_proc.stdout)

        try:
            resolve_toolchain(require_static_library=True)
        except ToolchainError:
            pass
        else:
            with tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp) / "libtype_alias_export.a"
                archive_proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "compile",
                        str(FIXTURES / "type_alias_export_header.ins"),
                        "--emit",
                        "static-library",
                        "-o",
                        str(archive),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(archive_proc.returncode, 0, archive_proc.stderr)
                self.assertGreater(archive.stat().st_size, 0)

        try:
            resolve_toolchain()
        except ToolchainError:
            return
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            llvm_path = tmp_path / "type_alias_scalar.ll"
            llvm_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "type_alias_scalar.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_path),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(llvm_proc.returncode, 0, llvm_proc.stderr)
            self.assertIn("define i32 @main", llvm_path.read_text())

            try:
                resolve_toolchain(require_executable=True)
            except ToolchainError:
                return
            executable = tmp_path / "type_alias_scalar"
            exe_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "type_alias_scalar.ins"),
                    "--emit",
                    "executable",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(exe_proc.returncode, 0, exe_proc.stderr)
            run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 42, run.stderr)

    def test_v028_byte_literals_and_byte_sequences_lower_without_runtime_strings(self):
        byte_literal = compile_source(self.fixture("byte_literal.ins"))
        self.assertIn("arith.constant 65 : i8", byte_literal)
        self.assertNotIn("memref.global", byte_literal)

        byte_array = compile_source(self.fixture("byte_array_literal.ins"))
        self.assertIn("memref.alloca() : memref<5xi8>", byte_array)
        self.assertIn("memref.store", byte_array)
        self.assertNotIn("memref.global", byte_array)

        byte_buffer = compile_source(self.fixture("byte_buffer_literal.ins"))
        self.assertIn("memref.alloca() : memref<5xi8>", byte_buffer)
        self.assertIn("arith.constant 72 : i8", byte_buffer)

        splice = compile_source(self.fixture("byte_containing_splice.ins"))
        self.assertIn("memref.alloca() : memref<6xi8>", splice)
        self.assertIn("arith.constant 0 : i8", splice)

        escapes = compile_source(self.fixture("byte_escapes.ins"))
        self.assertIn("arith.constant 10 : i8", escapes)

        length = compile_source(self.fixture("byte_length.ins"))
        self.assertIn("arith.constant 5 : i32", length)

        layout = compile_source(self.fixture("byte_layout_read.ins"))
        self.assertIn("memref.alloca() : memref<2xi8>", layout)
        self.assertIn("arith.constant 42 : i8", layout)

        view = compile_source(self.fixture("byte_view.ins"))
        self.assertIn("memref.cast", view)

        match = compile_source(self.fixture("byte_match.ins"))
        self.assertIn("arith.cmpi eq", match)

        alias = compile_source(self.fixture("byte_alias.ins"))
        self.assertIn("memref.alloca() : memref<5xi8>", alias)

    def test_v028_byte_artifacts_and_runtime_checks(self):
        try:
            resolve_toolchain()
        except ToolchainError:
            return

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        checked = subprocess.run(
            [
                sys.executable,
                "-m",
                "inscription",
                "run",
                str(FIXTURES / "checked_byte_index.ins"),
                "--runtime-checks",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 101, checked.stderr)
        self.assertEqual(checked.stdout, "")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            llvm_ir = tmp_path / "byte_array_literal.ll"
            llvm_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "byte_array_literal.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_ir),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(llvm_proc.returncode, 0, llvm_proc.stderr)
            self.assertIn("define i32 @main", llvm_ir.read_text())

            try:
                resolve_toolchain(require_static_library=True)
            except ToolchainError:
                pass
            else:
                archive = tmp_path / "libbyte_array_literal.a"
                archive_proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "compile",
                        str(FIXTURES / "byte_array_literal.ins"),
                        "--emit",
                        "static-library",
                        "-o",
                        str(archive),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(archive_proc.returncode, 0, archive_proc.stderr)
                self.assertGreater(archive.stat().st_size, 0)

            try:
                resolve_toolchain(require_executable=True)
            except ToolchainError:
                return
            executable = tmp_path / "byte_array_literal"
            exe_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "byte_array_literal.ins"),
                    "--emit",
                    "executable",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(exe_proc.returncode, 0, exe_proc.stderr)
            run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 5, run.stderr)


    def test_v029_owned_buffers_lower_to_heap_storage_and_deallocate(self):
        owned_sum = compile_source(self.fixture("owned_buffer_sum.ins"))
        self.assertIn("memref.alloc(", owned_sum)
        self.assertIn("memref<?xi32>", owned_sum)
        self.assertIn("memref.dealloc", owned_sum)
        self.assertIn("scf.for", owned_sum)

        write_indices = compile_source(self.fixture("owned_buffer_write_indices.ins"))
        self.assertIn("memref.store", write_indices)
        self.assertIn("memref.load", write_indices)

        view = compile_source(self.fixture("owned_buffer_view.ins"))
        self.assertIn("memref<?xi32>", view)
        self.assertIn("memref.dealloc", view)

        view_parameter = compile_source(self.fixture("owned_buffer_view_parameter.ins"))
        self.assertIn("func.call @sum_view", view_parameter)
        self.assertIn("memref<?xi32>", view_parameter)

        layout = compile_source(self.fixture("owned_buffer_layout.ins"))
        self.assertIn("memref<?xi8>", layout)
        self.assertIn("memref.dealloc", layout)

        float_buffer = compile_source(self.fixture("owned_buffer_float.ins"))
        self.assertIn("memref<?xf64>", float_buffer)

        enum_buffer = compile_source(self.fixture("owned_buffer_enum.ins"))
        self.assertIn("memref<?xi8>", enum_buffer)

        alias_buffer = compile_source(self.fixture("owned_buffer_alias_element.ins"))
        self.assertIn("arith.constant 65 : i8", alias_buffer)

    def test_v029_owned_buffer_artifacts_and_runtime_checks(self):
        try:
            resolve_toolchain()
        except ToolchainError:
            return

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        for fixture, status in [
            ("checked_owned_index.ins", 3),
            ("checked_owned_length.ins", 5),
            ("checked_owned_view.ins", 7),
        ]:
            with self.subTest(runtime_checked=fixture):
                checked = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "run",
                        str(FIXTURES / fixture),
                        "--runtime-checks",
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(checked.returncode, status, checked.stderr)
                self.assertEqual(checked.stdout, "")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            llvm_ir = tmp_path / "owned_buffer_sum.ll"
            llvm_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "owned_buffer_sum.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_ir),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(llvm_proc.returncode, 0, llvm_proc.stderr)
            self.assertIn("define i32 @main", llvm_ir.read_text())

            try:
                resolve_toolchain(require_static_library=True)
            except ToolchainError:
                pass
            else:
                archive = tmp_path / "libowned_buffer_sum.a"
                archive_proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "compile",
                        str(FIXTURES / "owned_buffer_sum.ins"),
                        "--emit",
                        "static-library",
                        "-o",
                        str(archive),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(archive_proc.returncode, 0, archive_proc.stderr)
                self.assertGreater(archive.stat().st_size, 0)

            try:
                resolve_toolchain(require_executable=True)
            except ToolchainError:
                return
            executable = tmp_path / "owned_buffer_sum"
            exe_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "owned_buffer_sum.ins"),
                    "--emit",
                    "executable",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(exe_proc.returncode, 0, exe_proc.stderr)
            run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 7, run.stderr)

    def test_v030_nested_owned_buffers_cleanup_at_lexical_scope(self):
        if_scope = compile_source(self.fixture("owned_buffer_if_scope.ins"))
        self.assertIn("memref.alloc(", if_scope)
        self.assertIn("memref.dealloc", if_scope)
        self.assertRegex(if_scope, r"memref\.dealloc %\d+ : memref<\?xi32>\n      scf\.yield")

        for_scope = compile_source(self.fixture("owned_buffer_for_scope.ins"))
        self.assertIn("scf.for", for_scope)
        self.assertRegex(for_scope, r"memref\.dealloc %\d+ : memref<\?xi32>\n +scf\.yield")

        while_scope = compile_source(self.fixture("owned_buffer_while_scope.ins"))
        self.assertIn("scf.while", while_scope)
        self.assertRegex(while_scope, r"memref\.dealloc %\d+ : memref<\?xi32>\n +scf\.yield")

        match_scope = compile_source(self.fixture("owned_buffer_match_scope.ins"))
        self.assertIn("memref.dealloc", match_scope)
        self.assertIn("memref<?xi32>", match_scope)

        nested_scope = compile_source(self.fixture("owned_buffer_nested_scope.ins"))
        self.assertIn("memref.dealloc", nested_scope)

        record_return = compile_source(self.fixture("owned_buffer_scope_record_return.ins"))
        self.assertRegex(
            record_return,
            r"memref\.load %\d+\[%\d+\] : memref<\?xi32>\n    memref\.dealloc %\d+ : memref<\?xi32>\n    return",
        )

        union_return = compile_source(self.fixture("owned_buffer_scope_union_return.ins"))
        self.assertIn("memref.dealloc", union_return)
        self.assertIn("return", union_return)

        view_parameter = compile_source(self.fixture("owned_buffer_nested_view_parameter.ins"))
        self.assertIn("func.call @sum_view", view_parameter)
        self.assertIn("memref.dealloc", view_parameter)

    def test_v030_nested_owned_buffer_artifacts_and_runtime_checks(self):
        try:
            resolve_toolchain()
        except ToolchainError:
            return

        env = {**os.environ, "PYTHONPATH": str(SRC)}
        for fixture, status in [
            ("checked_nested_owned_index.ins", 3),
            ("checked_loop_owned_view.ins", 7),
        ]:
            with self.subTest(runtime_checked=fixture):
                checked = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "run",
                        str(FIXTURES / fixture),
                        "--runtime-checks",
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(checked.returncode, status, checked.stderr)
                self.assertEqual(checked.stdout, "")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            llvm_ir = tmp_path / "owned_buffer_if_scope.ll"
            llvm_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "owned_buffer_if_scope.ins"),
                    "--emit",
                    "llvm-ir",
                    "--verify",
                    "-o",
                    str(llvm_ir),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(llvm_proc.returncode, 0, llvm_proc.stderr)
            self.assertIn("define i32 @main", llvm_ir.read_text())

            try:
                resolve_toolchain(require_static_library=True)
            except ToolchainError:
                pass
            else:
                archive = tmp_path / "libowned_buffer_if_scope.a"
                archive_proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "inscription",
                        "compile",
                        str(FIXTURES / "owned_buffer_if_scope.ins"),
                        "--emit",
                        "static-library",
                        "-o",
                        str(archive),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(archive_proc.returncode, 0, archive_proc.stderr)
                self.assertGreater(archive.stat().st_size, 0)

            try:
                resolve_toolchain(require_executable=True)
            except ToolchainError:
                return
            executable = tmp_path / "owned_buffer_if_scope"
            exe_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inscription",
                    "compile",
                    str(FIXTURES / "owned_buffer_if_scope.ins"),
                    "--emit",
                    "executable",
                    "-o",
                    str(executable),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(exe_proc.returncode, 0, exe_proc.stderr)
            run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(run.returncode, 7, run.stderr)

    def test_negative_diagnostics(self):
        cases = {
            "malformed top level": ("Please add two numbers\n", "expected phrase definition"),
            "unsupported free prose": ("main gives i32:\n  Please understand this naturally\n", "invalid token"),
            "undefined variable": ("main gives i32:\n  missing\n", "used before initialization"),
            "duplicate phrase": ("main gives i32:\n  0\nmain gives i32:\n  0\n", "duplicate phrase"),
            "duplicate parameter": (
                "add a: i32 and a: i32 gives i32:\n  a\n\nmain gives i32:\n  add 1 and 2\n",
                "duplicate parameter",
            ),
            "invalid main": ("main of argc: i32 gives i32:\n  argc\n", "main must take no parameters"),
            "unsupported operator": ("main gives i32:\n  4 modulo 2\n", "unexpected token"),
            "glued plus operator": ("main gives i32:\n  1plus 2\n", "missing whitespace"),
            "glued times operator": ("main gives i32:\n  3times 2\n", "missing whitespace"),
            "glued phrase connector": (
                "add a: i32 and b: i32 gives i32:\n  a plus b\n\nmain gives i32:\n  add 2and 3\n",
                "missing whitespace",
            ),
            "unsupported io": ("main gives i32:\n  print 1\n", "unexpected token"),
            "arrays": ("main gives i32:\n  array of 1\n", "unexpected token"),
            "float in integer return": ("main gives i32:\n  1.5\n", "expected i32, got f64"),
            "mixed integer float arithmetic": (
                "bad gives f64:\n  1 plus 2.0\n",
                "plus requires matching numeric types, got i32 and f64",
            ),
            "mixed f32 f64 arithmetic": (
                "bad gives f64:\n  let x: f32 be 1.0\n  let y: f64 be 2.0\n  x plus y\n",
                "plus requires matching numeric types, got f32 and f64",
            ),
            "float remainder": ("bad gives f64:\n  1.0 remainder 2.0\n", "remainder requires integer operands, got f64 and f64"),
            "float buffer index": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  cells at 1.0\n",
                "buffer index must be an integer type, got f64",
            ),
            "float view start": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let window be view of cells from 1.0 for 2\n  0\n",
                "view start must have type i32, got f64",
            ),
            "layout record float field": (
                "layout record Bad:\n  x: f32\n",
                "layout record fields must be integer types, got f32",
            ),
            "float to boolean cast": ("bad gives i1:\n  1.0 as i1\n", "cannot cast f64 to i1"),
            "boolean to float cast": ("bad gives f64:\n  true as f64\n", "cannot cast i1 to f64"),
            "constant float division by zero": (
                "constant bad: f64 be 1.0 divided by 0.0\n",
                "constant expression divides by zero",
            ),
            "pointers": ("main gives i32:\n  pointer\n", "unexpected token"),
            "memrefs": ("main gives i32:\n  memref\n", "unexpected token"),
            "reserved hole name": ("echo of let: i32 gives i32:\n  let\n\nmain gives i32:\n  0\n", "reserved word"),
            "out of range literal": ("main gives i64:\n  9223372036854775808\n", "out of range for i64"),
            "assignment to undeclared binding": ("bad gives i32:\n  x becomes 1\n  0\n", "unknown binding x"),
            "assignment type mismatch": (
                "bad gives i32:\n  let x be 0\n  x becomes x is equal to 0\n  x\n",
                "assignment to x must have type i32, got i1",
            ),
            "let annotation mismatch": ("bad gives i32:\n  let x: i32 be true\n  x\n", "let x must have type i32, got i1"),
            "old track syntax": (
                "bad gives i32:\n  track x: i32 from 0\n  x\n",
                "`track` is not valid Inscription syntax; use `let name be ...`",
            ),
            "while condition is not i1": (
                "bad gives i32:\n  let x be 0\n  while x:\n    x becomes x plus 1\n  x\n",
                "while condition must be i1",
            ),
            "while let does not escape": (
                "bad gives i32:\n  let x be 0\n  while x is less than 1:\n    let y be 2\n    x becomes x plus 1\n  y\n",
                "unknown binding y",
            ),
            "missing while body": (
                "bad gives i32:\n  let x be 0\n  while x is less than 1:\n  x\n",
                "while loop requires an indented body",
            ),
            "remainder on i1": ("bad gives i1:\n  true remainder false\n", "remainder requires integer operands"),
            "remainder mismatched operands": (
                "to i64 of x: i32 gives i64:\n  1\n\nbad of y: i32 gives i32:\n  y remainder to i64 of y\n",
                "remainder requires matching integer types",
            ),
            "if condition is not i1": (
                "bad gives i32:\n  let x be 0\n  if x:\n    x becomes 1\n  otherwise:\n    x becomes 2\n  x\n",
                "if condition must be i1",
            ),
            "missing if otherwise": (
                "bad gives i32:\n  let x be 0\n  if x is equal to 0:\n    x becomes 1\n  x\n",
                "if block requires otherwise",
            ),
            "empty if branch": (
                "bad gives i32:\n  let x be 0\n  if x is equal to 0:\n  otherwise:\n    x becomes 1\n  x\n",
                "if branch must contain at least one step",
            ),
            "empty otherwise branch": (
                "bad gives i32:\n  let x be 0\n  if x is equal to 0:\n    x becomes 1\n  otherwise:\n  x\n",
                "otherwise branch must contain at least one step",
            ),
            "branch let does not escape": (
                "bad gives i32:\n  let x be 0\n  if x is equal to 0:\n    let y be 1\n  otherwise:\n    let y be 2\n  y\n",
                "unknown binding y",
            ),
            "boolean and requires i1": ("bad gives i1:\n  1 and 2\n", "and requires i1 operands"),
            "boolean or requires i1": ("bad gives i1:\n  1 or 2\n", "or requires i1 operands"),
            "boolean not requires i1": ("bad gives i1:\n  not 1\n", "not requires i1 operand"),
            "u8 literal out of range": (
                "bad gives i32:\n  let x: u8 be 256\n  x as i32\n",
                "integer literal 256 is out of range for u8",
            ),
            "i8 literal out of range": (
                "bad gives i32:\n  let x: i8 be 128\n  x as i32\n",
                "integer literal 128 is out of range for i8",
            ),
            "arithmetic width mismatch": (
                "bad gives i32:\n  let x: i32 be 1\n  let y: i64 be 2\n  x plus y\n",
                "plus requires matching integer types, got i32 and i64",
            ),
            "arithmetic signed unsigned mismatch": (
                "bad gives i32:\n  let x: i32 be 1\n  let y: u32 be 2\n  x plus y\n",
                "plus requires matching integer types, got i32 and u32",
            ),
            "bitwise on boolean": (
                "bad gives i1:\n  true bitwise and false\n",
                "bitwise and requires integer operands, got i1 and i1",
            ),
            "boolean and on integers": (
                "bad gives i1:\n  let x: u8 be 1\n  let y: u8 be 2\n  x and y\n",
                "and requires i1 operands, got u8 and u8",
            ),
            "shift amount mismatch": (
                "bad gives u8:\n  let x: u8 be 1\n  let amount: u32 be 3\n  x shifted left by amount\n",
                "shifted left by requires matching integer types, got u8 and u32",
            ),
            "cast from boolean": ("bad gives i32:\n  true as i32\n", "cannot cast i1 to i32"),
            "cast to boolean": ("bad gives i1:\n  1 as i1\n", "cannot cast i32 to i1"),
            "comparison signed unsigned mismatch": (
                "bad gives i1:\n  let x: i32 be 1\n  let y: u32 be 1\n  x is equal to y\n",
                "comparison requires matching integer types, got i32 and u32",
            ),
            "zero length buffer": (
                "bad gives i32:\n  let cells be buffer of 0 i32 filled with 0\n  0\n",
                "buffer length must be at least 1",
            ),
            "unsupported i1 buffer": (
                "bad gives i32:\n  let flags be buffer of 4 i1 filled with false\n  0\n",
                "buffer element type must be an integer type, got i1",
            ),
            "buffer fill type mismatch": (
                "bad gives i32:\n  let bytes be buffer of 4 u8 filled with 300\n  0\n",
                "integer literal 300 is out of range for u8",
            ),
            "buffer containing count mismatch": (
                "bad gives i32:\n  let cells be buffer of 4 i32 containing 1, 2, 3\n  0\n",
                "buffer cells expects 4 elements, got 3",
            ),
            "buffer store type mismatch": (
                "bad gives i32:\n  let bytes be buffer of 4 u8 filled with 0\n  bytes at 0 becomes 300\n  0\n",
                "integer literal 300 is out of range for u8",
            ),
            "boolean buffer index": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  cells at true\n",
                "buffer index must be an integer type, got i1",
            ),
            "load literal index out of bounds": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  cells at 4\n",
                "buffer index 4 is out of bounds for buffer cells of length 4",
            ),
            "store literal index out of bounds": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  cells at 4 becomes 1\n  0\n",
                "buffer index 4 is out of bounds for buffer cells of length 4",
            ),
            "unknown buffer": ("bad gives i32:\n  missing at 0\n", "unknown binding missing"),
            "scalar used as buffer": (
                "bad gives i32:\n  let x be 0\n  x at 0\n",
                "x is not a buffer",
            ),
            "rebind buffer": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  cells becomes 1\n  0\n",
                "cannot rebind buffer cells; use `cells at index becomes value`",
            ),
            "buffer used as scalar": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  cells\n",
                "buffer cells cannot be used as a scalar value; use `cells at index`",
            ),
            "array containing count mismatch": (
                "bad gives i32:\n  let numbers be array of 4 i32 containing 1, 2, 3\n  0\n",
                "array numbers expects 4 elements, got 3",
            ),
            "array element type mismatch": (
                "bad gives i32:\n  let numbers be array of 4 i32 containing 1, true, 3, 4\n  0\n",
                "array numbers element 1 must have type i32, got i1",
            ),
            "array of i1 unsupported": (
                "bad gives i32:\n  let flags be array of 4 i1 containing true, false, true, false\n  0\n",
                "array element type must be numeric, got i1",
            ),
            "array store invalid": (
                "bad gives i32:\n  let numbers be array of 4 i32 containing 1, 2, 3, 4\n  numbers at 0 becomes 9\n  0\n",
                "cannot store into array numbers; arrays are immutable",
            ),
            "array rebind invalid": (
                "bad gives i32:\n  let numbers be array of 4 i32 containing 1, 2, 3, 4\n  numbers becomes 0\n  0\n",
                "cannot rebind array numbers",
            ),
            "array used as scalar": (
                "bad gives i32:\n  let numbers be array of 4 i32 containing 1, 2, 3, 4\n  numbers\n",
                "array numbers cannot be used as a scalar value; use `numbers at index`",
            ),
            "array passed to buffer parameter": (
                "sum buffer cells: buffer of 4 i32 gives i32:\n  0\n\nbad gives i32:\n  let numbers be array of 4 i32 containing 1, 2, 3, 4\n  sum buffer numbers\n",
                "argument numbers must have type buffer of 4 i32, got array of 4 i32",
            ),
            "array passed to writable view parameter": (
                "fill view cells: view of i32 with value: i32 does:\n  for each index i of cells:\n    cells at i becomes value\n\nbad gives i32:\n  let numbers be array of 4 i32 containing 1, 2, 3, 4\n  fill view numbers with 9\n  0\n",
                "cannot pass read-only array numbers to effectful phrase `fill view _ with _`",
            ),
            "array index out of bounds": (
                "bad gives i32:\n  let numbers be array of 4 i32 containing 1, 2, 3, 4\n  numbers at 4\n",
                "array index 4 is out of bounds for array numbers of length 4",
            ),
            "array view out of bounds": (
                "bad gives i32:\n  let numbers be array of 4 i32 containing 1, 2, 3, 4\n  let window be view of numbers from 2 for 3\n  0\n",
                "view range 2 for 3 exceeds source numbers of length 4",
            ),
            "array return unsupported": (
                "bad gives array of 4 i32:\n  0\n",
                "array return types are not supported",
            ),
            "array parameter unsupported": (
                "bad numbers: array of 4 i32 gives i32:\n  0\n",
                "array parameters are not supported in v0.22; use view of i32",
            ),
            "buffer passed to phrase call": (
                "identity of x: i32 gives i32:\n  x\n\nbad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  identity of cells\n",
                "argument cells must have type i32, got buffer of 4 i32",
            ),
            "branch local buffer does not escape": (
                "bad gives i32:\n  let flag be true\n  if flag:\n    let cells be buffer of 1 i32 filled with 1\n  otherwise:\n    let cells be buffer of 1 i32 filled with 2\n  cells at 0\n",
                "unknown binding cells",
            ),
            "store to readonly buffer parameter": (
                "bad buffer cells: buffer of 4 i32 gives i32:\n  cells at 0 becomes 1\n  0\n",
                "cannot store to read-only buffer parameter cells",
            ),
            "does phrase used as expression": (
                "fill buffer cells: buffer of 4 i32 with value: i32 does:\n  cells at 0 becomes value\n\nbad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let x be fill buffer cells with 7\n  x\n",
                "phrase `fill buffer _ with _` does not return a value",
            ),
            "gives phrase used as step": (
                "sum buffer cells: buffer of 4 i32 gives i32:\n  0\n\nbad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  sum buffer cells\n  0\n",
                "phrase `sum buffer _` returns i32 and cannot be used as a step",
            ),
            "buffer parameter length mismatch": (
                "sum buffer cells: buffer of 4 i32 gives i32:\n  0\n\nbad gives i32:\n  let cells be buffer of 5 i32 filled with 0\n  sum buffer cells\n",
                "buffer argument cells must have type buffer of 4 i32, got buffer of 5 i32",
            ),
            "buffer parameter element mismatch": (
                "sum buffer cells: buffer of 4 i32 gives i32:\n  0\n\nbad gives i32:\n  let cells be buffer of 4 u32 filled with 0\n  sum buffer cells\n",
                "buffer argument cells must have type buffer of 4 i32, got buffer of 4 u32",
            ),
            "scalar passed where buffer expected": (
                "sum buffer cells: buffer of 4 i32 gives i32:\n  0\n\nbad gives i32:\n  let cells be 0\n  sum buffer cells\n",
                "argument cells must be buffer of 4 i32, got i32",
            ),
            "duplicate buffer actuals": (
                "copy from source: buffer of 4 i32 to destination: buffer of 4 i32 does:\n  destination at 0 becomes source at 0\n\nbad gives i32:\n  let cells be buffer of 4 i32 filled with 1\n  copy from cells to cells\n  0\n",
                "buffer cells cannot be passed to multiple buffer parameters in one call",
            ),
            "readonly buffer passed to does phrase": (
                "clear cells: buffer of 4 i32 does:\n  cells at 0 becomes 0\n\nbad buffer cells: buffer of 4 i32 gives i32:\n  clear cells\n  0\n",
                "cannot pass read-only buffer cells to effectful phrase `clear _`",
            ),
            "buffer parameter cannot be rebound": (
                "bad buffer cells: buffer of 4 i32 does:\n  cells becomes 1\n",
                "cannot rebind buffer cells; use `cells at index becomes value`",
            ),
            "does phrase with final scalar value": ("bad does:\n  1\n", "does phrase body cannot end with a value expression"),
            "empty does phrase": ("bad does:\n", "does phrase body must contain at least one step"),
            "for bounds type mismatch": (
                "bad gives i32:\n  let end: i64 be 10\n  for i from 0 up to end:\n    let x be i\n  0\n",
                "for loop bounds must have matching integer types, got i32 and i64",
            ),
            "for bounds boolean": (
                "bad gives i32:\n  for i from false up to true:\n    let x be 0\n  0\n",
                "for loop bounds must be integer types, got i1 and i1",
            ),
            "for zero step": (
                "bad gives i32:\n  for i from 0 up to 10 by 0:\n    let x be i\n  0\n",
                "for loop step must be at least 1",
            ),
            "for missing body": (
                "bad gives i32:\n  for i from 0 up to 10:\n  0\n",
                "for loop body must contain at least one step",
            ),
            "for index escapes": (
                "bad gives i32:\n  for i from 0 up to 10:\n    let x be i\n  i\n",
                "unknown binding i",
            ),
            "for index cannot be rebound": (
                "bad gives i32:\n  for i from 0 up to 10:\n    i becomes i plus 1\n  0\n",
                "cannot rebind for-loop index i",
            ),
            "for index cannot shadow": (
                "bad gives i32:\n  let i be 0\n  for i from 0 up to 10:\n    let x be i\n  0\n",
                "binding i already exists",
            ),
            "length of unknown": ("bad gives i32:\n  length of cells\n", "unknown binding cells"),
            "length of scalar": (
                "bad gives i32:\n  let cells be 0\n  length of cells\n",
                "length of cells requires a buffer, got i32",
            ),
            "for each unknown": (
                "bad gives i32:\n  for each index i of cells:\n    let x be i\n  0\n",
                "unknown binding cells",
            ),
            "for each scalar": (
                "bad gives i32:\n  let cells be 0\n  for each index i of cells:\n    let x be i\n  0\n",
                "for each index requires a buffer, got i32",
            ),
            "for each index shadowing": (
                "bad gives i32:\n  let i be 0\n  let cells be buffer of 4 i32 filled with 0\n  for each index i of cells:\n    cells at i becomes 1\n  0\n",
                "binding i already exists",
            ),
            "for each missing body": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  for each index i of cells:\n  0\n",
                "for loop body must contain at least one step",
            ),
            "length used as guard": (
                "bad cells: buffer of 4 i32 gives i32:\n  1 when length of cells\n  otherwise 0\n",
                "value block condition must be i1, got i32",
            ),
            "duplicate record name": (
                "record Point:\n  x: i32\n\nrecord Point:\n  y: i32\n\nmain gives i32:\n  0\n",
                "record Point is already defined",
            ),
            "duplicate record field": (
                "record Point:\n  x: i32\n  x: i32\n\nmain gives i32:\n  0\n",
                "record Point has duplicate field x",
            ),
            "empty record": ("record Empty:\n\nmain gives i32:\n  0\n", "record Empty must declare at least one field"),
            "record buffer field unsupported": (
                "record Bad:\n  cells: buffer of 4 i32\n\nmain gives i32:\n  0\n",
                "record fields must be scalar types, got buffer of 4 i32",
            ),
            "unknown record type in parameter": (
                "use thing x: Missing gives i32:\n  0\n",
                "unknown type Missing",
            ),
            "unknown record type in constructor": (
                "bad gives i32:\n  let p be Missing with x be 1\n  0\n",
                "unknown record type Missing",
            ),
            "record initializer missing field": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let p be Point with x be 1\n  0\n",
                "record Point initializer requires fields x, y",
            ),
            "record initializer extra field": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let p be Point with x be 1 and y be 2 and z be 3\n  0\n",
                "record Point has no field z",
            ),
            "record initializer wrong field order": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let p be Point with y be 2 and x be 1\n  0\n",
                "record Point initializer fields must appear in declaration order: x, y",
            ),
            "record field type mismatch": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let p be Point with x be true and y be 2\n  0\n",
                "field x of Point must have type i32, got i1",
            ),
            "unknown record field access": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let p be Point with x be 1 and y be 2\n  p.z\n",
                "record Point has no field z",
            ),
            "field access on scalar": ("bad gives i32:\n  let x be 1\n  x.y\n", "x is not a record"),
            "record field assignment type mismatch": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let p be Point with x be 1 and y be 2\n  p.x becomes true\n  p.x\n",
                "field x of Point must have type i32, got i1",
            ),
            "record used as scalar": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let p be Point with x be 1 and y be 2\n  p\n",
                "record p cannot be used as a scalar value; use a field such as p.x",
            ),
            "record plus record": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let p be Point with x be 1 and y be 2\n  p plus p\n",
                "plus requires integer operands, got Point and Point",
            ),
            "record passed where scalar expected": (
                "record Point:\n  x: i32\n  y: i32\n\nidentity of x: i32 gives i32:\n  x\n\nbad gives i32:\n  let p be Point with x be 1 and y be 2\n  identity of p\n",
                "argument p must have type i32, got Point",
            ),
            "scalar passed where record expected": (
                "record Point:\n  x: i32\n  y: i32\n\nsum point p: Point gives i32:\n  p.x plus p.y\n\nbad gives i32:\n  let p be 1\n  sum point p\n",
                "argument p must have type Point, got i32",
            ),
            "nominal record mismatch": (
                "record Point:\n  x: i32\n  y: i32\n\nrecord Pair:\n  x: i32\n  y: i32\n\nsum point p: Point gives i32:\n  p.x plus p.y\n\nbad gives i32:\n  let pair be Pair with x be 1 and y be 2\n  sum point pair\n",
                "argument pair must have type Point, got Pair",
            ),
            "unknown record return type": ("make thing gives Missing:\n  0\n", "unknown type Missing"),
            "buffer return type unsupported": (
                "bad gives buffer of 4 i32:\n  0\n",
                "buffer return types are not supported",
            ),
            "scalar returned from record phrase": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives Point:\n  0\n",
                "phrase bad must return Point, got i32",
            ),
            "record returned from scalar phrase": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  Point with x be 1 and y be 2\n",
                "phrase bad must return i32, got Point",
            ),
            "guarded record branches mismatch": (
                "record Point:\n  x: i32\n  y: i32\n\nrecord Pair:\n  left: i32\n  right: i32\n\nbad flag: i1 gives Point:\n  Point with x be 1 and y be 2 when flag\n  otherwise Pair with left be 1 and right be 2\n",
                "guarded value branches must have matching types, got Point and Pair",
            ),
            "guarded record scalar branch mismatch": (
                "record Point:\n  x: i32\n  y: i32\n\nbad flag: i1 gives Point:\n  Point with x be 1 and y be 2 when flag\n  otherwise 0\n",
                "guarded value branches must have matching types, got Point and i32",
            ),
            "record returning phrase used as scalar": (
                "record Point:\n  x: i32\n  y: i32\n\nmake point gives Point:\n  Point with x be 1 and y be 2\n\nbad gives i32:\n  make point plus 1\n",
                "plus requires integer operands, got Point and i32",
            ),
            "scalar returning phrase used as record initializer": (
                "record Point:\n  x: i32\n  y: i32\n\nmake number gives i32:\n  1\n\nbad gives i32:\n  let p: Point be make number\n  p.x\n",
                "let p must have type Point, got i32",
            ),
            "record returning phrase used as step": (
                "record Point:\n  x: i32\n  y: i32\n\nmake point gives Point:\n  Point with x be 1 and y be 2\n\nbad gives i32:\n  make point\n  0\n",
                "phrase `make point` returns Point and cannot be used as a step",
            ),
            "record buffer element unsupported": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let points be buffer of 4 Point filled with Point with x be 0 and y be 0\n  0\n",
                "buffer element type must be an integer type, got Point",
            ),
            "branch local record does not escape": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let flag be true\n  if flag:\n    let p be Point with x be 1 and y be 2\n  otherwise:\n    let p be Point with x be 3 and y be 4\n  p.x\n",
                "unknown binding p",
            ),
            "duplicate record and layout record name": (
                "record Point:\n  x: i32\n\nlayout record Point:\n  x: i32\n\nmain gives i32:\n  0\n",
                "record Point is already defined",
            ),
            "empty layout record": ("layout record Empty:\n\nmain gives i32:\n  0\n", "layout record Empty must declare at least one field"),
            "duplicate layout field": (
                "layout record Header:\n  tag: u8\n  tag: u8\n\nmain gives i32:\n  0\n",
                "layout record Header has duplicate field tag",
            ),
            "layout i1 field unsupported": (
                "layout record Bad:\n  flag: i1\n\nmain gives i32:\n  0\n",
                "layout record fields must be integer types, got i1",
            ),
            "layout buffer field unsupported": (
                "layout record Bad:\n  bytes: buffer of 4 u8\n\nmain gives i32:\n  0\n",
                "layout record fields must be integer types, got buffer of 4 u8",
            ),
            "ordinary record has no layout size": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  size of Point\n",
                "size of Point requires a layout record",
            ),
            "size unknown record type": ("bad gives i32:\n  size of Missing\n", "unknown record type Missing"),
            "offset unknown layout field": (
                "layout record Header:\n  tag: u8\n\nbad gives i32:\n  offset of length in Header\n",
                "layout record Header has no field length",
            ),
            "read unknown layout type": (
                "bad gives i32:\n  let bytes be buffer of 4 u8 filled with 0\n  let header be read Missing from bytes at 0\n  0\n",
                "unknown record type Missing",
            ),
            "read ordinary record": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let bytes be buffer of 8 u8 filled with 0\n  let p be read Point from bytes at 0\n  0\n",
                "read Point requires a layout record",
            ),
            "read non u8 buffer": (
                "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let cells be buffer of 2 i32 filled with 0\n  let word be read Word from cells at 0\n  0\n",
                "read Word requires a u8 buffer, got buffer of 2 i32",
            ),
            "write ordinary record": (
                "record Point:\n  x: i32\n  y: i32\n\nbad gives i32:\n  let bytes be buffer of 8 u8 filled with 0\n  let p be Point with x be 1 and y be 2\n  write p into bytes at 0\n  0\n",
                "write p requires a layout record value, got Point",
            ),
            "write non u8 buffer": (
                "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let cells be buffer of 2 i32 filled with 0\n  let word be Word with value be 1\n  write word into cells at 0\n  0\n",
                "write Word requires a u8 buffer, got buffer of 2 i32",
            ),
            "write readonly buffer parameter": (
                "packed layout record Word:\n  value: u16\n\nbad bytes: buffer of 2 u8 gives i32:\n  let word be Word with value be 1\n  write word into bytes at 0\n  0\n",
                "cannot write to read-only buffer parameter bytes",
            ),
            "layout write into array invalid": (
                "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let bytes be array of 2 u8 containing 0, 0\n  let word be Word with value be 1\n  write word into bytes at 0\n  0\n",
                "cannot write into array bytes; arrays are immutable",
            ),
            "layout read static out of bounds": (
                "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let bytes be buffer of 2 u8 filled with 0\n  let word be read Word from bytes at 1\n  0\n",
                "read Word at index 1 exceeds buffer bytes of length 2",
            ),
            "layout write static out of bounds": (
                "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let bytes be buffer of 2 u8 filled with 0\n  let word be Word with value be 1\n  write word into bytes at 1\n  0\n",
                "write Word at index 1 exceeds buffer bytes of length 2",
            ),
            "layout read boolean index": (
                "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let bytes be buffer of 2 u8 filled with 0\n  let word be read Word from bytes at true\n  0\n",
                "layout read index must be an integer type, got i1",
            ),
            "layout write boolean index": (
                "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let bytes be buffer of 2 u8 filled with 0\n  let word be Word with value be 1\n  write word into bytes at false\n  0\n",
                "layout write index must be an integer type, got i1",
            ),
            "write used as expression": (
                "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let bytes be buffer of 2 u8 filled with 0\n  let word be Word with value be 1\n  let result be write word into bytes at 0\n  0\n",
                "write is a step and cannot be used as an expression",
            ),
            "duplicate constant": ("constant x: i32 be 1\nconstant x: i32 be 2\n", "constant x is already defined"),
            "constant collides with record": (
                "record Point:\n  x: i32\n\nconstant Point: i32 be 1\n",
                "constant Point conflicts with record Point",
            ),
            "constant forward reference": (
                "constant b: i32 be a plus 1\nconstant a: i32 be 1\n",
                "unknown binding a",
            ),
            "constant initializer type mismatch": ("constant x: i32 be true\n", "constant x must have type i32, got i1"),
            "check expression not compile-time evaluable": (
                "identity of x: i32 gives i32:\n  x\n\nbad of x: i32 gives i32:\n  check identity of x is equal to 1\n  x\n",
                "check expression must be compile-time evaluable",
            ),
            "check expression is not i1": ("check 1\n", "check expression must have type i1, got i32"),
            "failing top-level check": ("check 1 is equal to 2\n", "compile-time check failed"),
            "failing phrase-body check": (
                "bad gives i32:\n  check 1 is equal to 2\n  0\n",
                "compile-time check failed",
            ),
            "rebind constant": (
                "constant x: i32 be 1\n\nbad gives i32:\n  x becomes 2\n  x\n",
                "cannot rebind constant x",
            ),
            "local binding shadows constant": (
                "constant x: i32 be 1\n\nbad gives i32:\n  let x be 2\n  x\n",
                "binding x conflicts with constant x",
            ),
            "buffer length constant is boolean": (
                "constant n: i1 be true\n\nbad gives i32:\n  let cells be buffer of n i32 filled with 0\n  0\n",
                "buffer length must be an integer type, got i1",
            ),
            "buffer length constant is zero": (
                "constant n: i32 be 0\n\nbad gives i32:\n  let cells be buffer of n i32 filled with 0\n  0\n",
                "buffer length must be at least 1",
            ),
            "buffer length expression not compile-time evaluable": (
                "bad of n: i32 gives i32:\n  let cells be buffer of (n plus 1) i32 filled with 0\n  0\n",
                "buffer length must be compile-time evaluable",
            ),
            "buffer parameter length mismatch after constant evaluation": (
                "constant four: i32 be 4\nconstant five: i32 be 5\n\nsum cells cells: buffer of four i32 gives i32:\n  0\n\nbad gives i32:\n  let cells be buffer of five i32 filled with 0\n  sum cells cells\n",
                "buffer argument cells must have type buffer of 4 i32, got buffer of 5 i32",
            ),
            "constant layout read out of bounds": (
                "packed layout record Word:\n  value: u16\n\nconstant start: i32 be 1\n\nbad gives i32:\n  let bytes be buffer of (size of Word) u8 filled with 0\n  let word be read Word from bytes at start\n  0\n",
                "read Word at index 1 exceeds buffer bytes of length 2",
            ),
            "constant layout write out of bounds": (
                "packed layout record Word:\n  value: u16\n\nconstant start: i32 be 1\n\nbad gives i32:\n  let bytes be buffer of (size of Word) u8 filled with 0\n  let word be Word with value be 1\n  write word into bytes at start\n  0\n",
                "write Word at index 1 exceeds buffer bytes of length 2",
            ),
            "constant division by zero": ("constant x: i32 be 1 divided by 0\n", "constant expression divides by zero"),
            "constant shift too large": ("constant x: u8 be 1 shifted left by 8\n", "constant shift amount 8 is out of range for u8"),
            "check used as expression": (
                "bad gives i32:\n  let x be check 1 is equal to 1\n  0\n",
                "check is a step and cannot be used as an expression",
            ),
            "require condition not i1": (
                "bad gives i32:\n  require 1\n  0\n",
                "require condition must have type i1, got i32",
            ),
            "require at top level": (
                "require true\n\nmain gives i32:\n  0\n",
                "require may only appear inside phrase bodies",
            ),
            "require used as expression": (
                "bad gives i32:\n  let x be require true\n  0\n",
                "require is a step and cannot be used as an expression",
            ),
            "compile-time false require": (
                "bad gives i32:\n  require 1 is equal to 2\n  0\n",
                "require condition is known to be false",
            ),
            "require does not satisfy value block": (
                "bad gives i32:\n  require true\n",
                "gives phrase body must end with a value expression",
            ),
            "view source unknown": (
                "bad gives i32:\n  let window be view of cells from 0 for 1\n  0\n",
                "unknown binding cells",
            ),
            "view source scalar": (
                "bad gives i32:\n  let cells be 0\n  let window be view of cells from 0 for 1\n  0\n",
                "view source cells must be a buffer or view, got i32",
            ),
            "view start not i32": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let start: i64 be 0\n  let window be view of cells from start for 1\n  0\n",
                "view start must have type i32, got i64",
            ),
            "view count not i32": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let count: i64 be 1\n  let window be view of cells from 0 for count\n  0\n",
                "view count must have type i32, got i64",
            ),
            "static view out of bounds": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let window be view of cells from 2 for 3\n  0\n",
                "view range 2 for 3 exceeds source cells of length 4",
            ),
            "negative static view count": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let window be view of cells from 0 for (zero minus 1)\n  0\n",
                "view count must be nonnegative",
            ),
            "view load static out of bounds": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let window be view of cells from 1 for 2\n  window at 2\n",
                "view index 2 is out of bounds for view window of length 2",
            ),
            "view store static out of bounds": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let window be view of cells from 1 for 2\n  window at 2 becomes 1\n  0\n",
                "view index 2 is out of bounds for view window of length 2",
            ),
            "view used as scalar": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let window be view of cells from 0 for 4\n  window\n",
                "view window cannot be used as a scalar value; use `window at index`",
            ),
            "view cannot be rebound": (
                "bad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let window be view of cells from 0 for 4\n  window becomes 1\n  0\n",
                "cannot rebind view window",
            ),
            "store through readonly view parameter": (
                "bad view cells: view of i32 gives i32:\n  cells at 0 becomes 1\n  0\n",
                "cannot store through read-only view cells",
            ),
            "readonly view passed to does phrase": (
                "fill view cells: view of i32 with value: i32 does:\n  cells at 0 becomes value\n\nbad view cells: view of i32 gives i32:\n  fill view cells with 1\n  0\n",
                "cannot pass read-only view cells to effectful phrase `fill view _ with _`",
            ),
            "view element type mismatch": (
                "sum view cells: view of i32 gives i32:\n  0\n\nbad gives i32:\n  let bytes be buffer of 4 u8 filled with 0\n  sum view bytes\n",
                "argument bytes must have type view of i32, got buffer of 4 u8",
            ),
            "duplicate root storage through views": (
                "copy view source: view of i32 to destination: view of i32 does:\n  for each index i of source:\n    destination at i becomes source at i\n\nbad gives i32:\n  let cells be buffer of 4 i32 filled with 1\n  let left be view of cells from 0 for 2\n  let right be view of cells from 2 for 2\n  copy view left to right\n  0\n",
                "views left and right share root buffer cells and cannot be passed to multiple view parameters in one call",
            ),
            "layout read from non u8 view": (
                "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let cells be buffer of 4 i32 filled with 0\n  let window be view of cells from 0 for 2\n  let word be read Word from window at 0\n  0\n",
                "read Word requires a u8 buffer or view, got view of i32",
            ),
            "layout write to readonly u8 view": (
                "packed layout record Word:\n  value: u16\n\nbad view bytes: view of u8 gives i32:\n  let word be Word with value be 1\n  write word into bytes at 0\n  0\n",
                "cannot write to read-only view bytes",
            ),
            "view return type unsupported": (
                "bad gives view of i32:\n  0\n",
                "view return types are not supported",
            ),
            "duplicate enum name": (
                "enum Mode: u8:\n  idle be 0\n\nenum Mode: u8:\n  active be 1\n",
                "enum Mode is already defined",
            ),
            "enum collides with record": (
                "record Mode:\n  value: u8\n\nenum Mode: u8:\n  idle be 0\n",
                "enum Mode conflicts with record Mode",
            ),
            "enum unsupported underlying type": (
                "enum Bad: f64:\n  value be 0\n",
                "enum underlying type must be an integer type, got f64",
            ),
            "enum i1 underlying type": (
                "enum Bad: i1:\n  no be false\n  yes be true\n",
                "enum underlying type must be an integer type, got i1",
            ),
            "empty enum": (
                "enum Empty: u8:\n",
                "enum Empty must declare at least one case",
            ),
            "duplicate enum case name": (
                "enum Mode: u8:\n  idle be 0\n  idle be 1\n",
                "enum Mode has duplicate case idle",
            ),
            "duplicate enum case value": (
                "enum Mode: u8:\n  idle be 0\n  inactive be 0\n",
                "enum Mode has duplicate case value 0",
            ),
            "enum case value out of range": (
                "enum Mode: u8:\n  invalid be 256\n",
                "integer literal 256 is out of range for u8",
            ),
            "unknown enum case": (
                "enum Mode: u8:\n  idle be 0\n\nbad gives i32:\n  Mode.active as i32\n",
                "enum Mode has no case active",
            ),
            "unknown enum type": (
                "bad gives i32:\n  Missing.active as i32\n",
                "unknown type Missing",
            ),
            "enum arithmetic invalid": (
                "enum Mode: u8:\n  idle be 0\n  active be 1\n\nbad gives u8:\n  Mode.idle plus Mode.active\n",
                "plus requires numeric primitive operands, got Mode and Mode",
            ),
            "enum ordered comparison invalid": (
                "enum Mode: u8:\n  idle be 0\n  active be 1\n\nbad gives i1:\n  Mode.active is greater than Mode.idle\n",
                "ordered comparisons are not supported for enum Mode; cast to u8 first",
            ),
            "enum comparison mismatch": (
                "enum Mode: u8:\n  idle be 0\n\nenum Status: u8:\n  idle be 0\n\nbad gives i1:\n  Mode.idle is equal to Status.idle\n",
                "comparison requires matching enum types, got Mode and Status",
            ),
            "integer assigned to enum without cast": (
                "enum Mode: u8:\n  idle be 0\n\nbad gives i32:\n  let mode: Mode be 0\n  0\n",
                "let mode must have type Mode, got i32",
            ),
            "enum assigned to integer without cast": (
                "enum Mode: u8:\n  idle be 0\n\nbad gives i32:\n  let value: u8 be Mode.idle\n  value as i32\n",
                "let value must have type u8, got Mode",
            ),
            "enum as array index": (
                "enum Index: u8:\n  zero be 0\n\nbad gives i32:\n  let cells be array of 1 i32 containing 7\n  cells at Index.zero\n",
                "array index must be an integer type, got Index",
            ),
            "enum export parameter unsupported": (
                "enum Mode: u8:\n  idle be 0\n\nexport set mode mode: Mode does as ins_set_mode:\n  require mode is equal to Mode.idle\n",
                "exported phrase parameters must be primitive scalar types, got Mode",
            ),
            "enum extern parameter unsupported": (
                "enum Mode: u8:\n  idle be 0\n\nextern host set mode mode: Mode does as host_set_mode\n",
                "extern phrase parameters must be primitive scalar types, got Mode",
            ),
            "enum cast through wrong integer type": (
                "enum Mode: u8:\n  idle be 0\n\nbad gives i32:\n  let value: i32 be 0\n  let mode: Mode be value as Mode\n  0\n",
                "cannot cast i32 to Mode; cast to u8 first",
            ),
            "match expression missing otherwise": (
                "enum Mode: u8:\n  idle be 0\n  active be 1\n\nbad mode: Mode gives i32:\n  match mode:\n    Mode.idle gives 0\n    Mode.active gives 1\n",
                "match expression requires otherwise",
            ),
            "match block missing otherwise": (
                "enum Mode: u8:\n  idle be 0\n  active be 1\n\nbad mode: Mode gives i32:\n  let x be 0\n  match mode:\n    Mode.idle:\n      x becomes 1\n  x\n",
                "match block requires otherwise",
            ),
            "match pattern type mismatch": (
                "enum Mode: u8:\n  idle be 0\n\nbad gives i32:\n  match Mode.idle:\n    0 gives 1\n    otherwise gives 2\n",
                "match pattern must have type Mode, got u8",
            ),
            "match enum mismatch pattern": (
                "enum Mode: u8:\n  idle be 0\n\nenum Status: u8:\n  idle be 0\n\nbad gives i32:\n  match Mode.idle:\n    Status.idle gives 1\n    otherwise gives 2\n",
                "match pattern must have type Mode, got Status",
            ),
            "match result type mismatch": (
                "enum Mode: u8:\n  idle be 0\n\nbad gives i32:\n  match Mode.idle:\n    Mode.idle gives 1\n    otherwise gives true\n",
                "match expression arms must have matching types, got i32 and i1",
            ),
            "match record result nominal mismatch": (
                "enum Mode: u8:\n  idle be 0\n\nrecord Point:\n  x: i32\n\nrecord Other:\n  x: i32\n\nbad gives Point:\n  match Mode.idle:\n    Mode.idle gives Point with x be 1\n    otherwise gives Other with x be 2\n",
                "match expression arms must have matching types, got Point and Other",
            ),
            "match duplicate enum case": (
                "enum Mode: u8:\n  idle be 0\n\nbad gives i32:\n  match Mode.idle:\n    Mode.idle gives 1\n    Mode.idle gives 2\n    otherwise gives 3\n",
                "match has duplicate pattern Mode.idle",
            ),
            "match duplicate integer pattern": (
                "bad x: i32 gives i32:\n  match x:\n    1 gives 10\n    1 gives 20\n    otherwise gives 30\n",
                "match has duplicate pattern 1",
            ),
            "match duplicate boolean pattern": (
                "bad flag: i1 gives i32:\n  match flag:\n    true gives 1\n    true gives 2\n    otherwise gives 3\n",
                "match has duplicate pattern true",
            ),
            "match float scrutinee unsupported": (
                "bad x: f64 gives i32:\n  match x:\n    1.0 gives 1\n    otherwise gives 2\n",
                "match scrutinee must be i1, integer, or enum, got f64",
            ),
            "match record scrutinee unsupported": (
                "record Point:\n  x: i32\n\nbad p: Point gives i32:\n  match p:\n    otherwise gives 0\n",
                "match scrutinee must be i1, integer, or enum, got Point",
            ),
            "match float pattern unsupported": (
                "bad x: i32 gives i32:\n  match x:\n    1.0 gives 1\n    otherwise gives 2\n",
                "match pattern must have type i32, got f64",
            ),
            "match otherwise not last": (
                "bad x: i32 gives i32:\n  match x:\n    otherwise gives 0\n    1 gives 1\n",
                "otherwise must be the final match arm",
            ),
            "match empty step arm": (
                "bad x: i32 gives i32:\n  let y be 0\n  match x:\n    0:\n    otherwise:\n      y becomes 1\n  y\n",
                "match arm must contain at least one step",
            ),
            "match step does not satisfy value block": (
                "bad x: i32 gives i32:\n  match x:\n    0:\n      let y be 1\n    otherwise:\n      let y be 2\n",
                "gives phrase body must end with a value expression",
            ),
            "match arm binding does not escape": (
                "bad x: i32 gives i32:\n  match x:\n    0:\n      let y be 1\n    otherwise:\n      let y be 2\n  y\n",
                "unknown binding y",
            ),
            "match over buffer unsupported": (
                "bad gives i32:\n  let cells be buffer of 1 i32 filled with 0\n  match cells:\n    otherwise gives 0\n",
                "match scrutinee must be i1, integer, or enum, got buffer of 1 i32",
            ),
            "duplicate union name": (
                "union MaybeI32:\n  none\n\nunion MaybeI32:\n  some value: i32\n",
                "union MaybeI32 is already defined",
            ),
            "union collides with enum": (
                "enum MaybeI32: u8:\n  none be 0\n\nunion MaybeI32:\n  none\n",
                "union MaybeI32 conflicts with enum MaybeI32",
            ),
            "empty union": (
                "union Empty:\n",
                "union Empty must declare at least one variant",
            ),
            "duplicate union variant name": (
                "union MaybeI32:\n  none\n  none\n",
                "union MaybeI32 has duplicate variant none",
            ),
            "union duplicate payload field": (
                "union Token:\n  operator symbol: u8 and symbol: u8\n",
                "variant Token.operator has duplicate payload field symbol",
            ),
            "union payload buffer unsupported": (
                "union Bad:\n  data bytes: buffer of 4 u8\n",
                "union payloads may not be buffer types in v0.26",
            ),
            "union payload union unsupported": (
                "union MaybeI32:\n  none\n\nunion Bad:\n  nested value: MaybeI32\n",
                "union payloads may not be union types in v0.26",
            ),
            "unknown union variant constructor": (
                "union MaybeI32:\n  none\n\nbad gives i32:\n  let maybe be MaybeI32.some with value be 1\n  0\n",
                "union MaybeI32 has no variant some",
            ),
            "union constructor missing payload": (
                "union MaybeI32:\n  some value: i32\n\nbad gives i32:\n  let maybe be MaybeI32.some\n  0\n",
                "variant MaybeI32.some requires payload fields value",
            ),
            "union constructor extra payload": (
                "union MaybeI32:\n  none\n\nbad gives i32:\n  let maybe be MaybeI32.none with value be 1\n  0\n",
                "variant MaybeI32.none has no payload",
            ),
            "union constructor wrong payload name": (
                "union MaybeI32:\n  some value: i32\n\nbad gives i32:\n  let maybe be MaybeI32.some with other be 1\n  0\n",
                "variant MaybeI32.some has no payload field other",
            ),
            "union constructor field order mismatch": (
                "union Token:\n  operator symbol: u8 and precedence: u8\n\nbad gives i32:\n  let token be Token.operator with precedence be 5 and symbol be 10\n  0\n",
                "variant Token.operator payload fields must appear in declaration order: symbol, precedence",
            ),
            "union constructor missing field": (
                "union Token:\n  operator symbol: u8 and precedence: u8\n\nbad gives i32:\n  let token be Token.operator with symbol be 10\n  0\n",
                "variant Token.operator requires payload fields symbol, precedence",
            ),
            "union constructor extra field": (
                "union Token:\n  operator symbol: u8 and precedence: u8\n\nbad gives i32:\n  let token be Token.operator with symbol be 10 and precedence be 5 and associativity be 1\n  0\n",
                "variant Token.operator has no payload field associativity",
            ),
            "union constructor payload type mismatch": (
                "union MaybeI32:\n  some value: i32\n\nbad gives i32:\n  let maybe be MaybeI32.some with value be true\n  0\n",
                "variant MaybeI32.some payload value must have type i32, got i1",
            ),
            "union used as scalar": (
                "union MaybeI32:\n  none\n\nbad gives i32:\n  let maybe be MaybeI32.none\n  maybe\n",
                "union maybe cannot be used as a scalar value; use match",
            ),
            "union field access invalid": (
                "union MaybeI32:\n  some value: i32\n\nbad gives i32:\n  let maybe be MaybeI32.some with value be 1\n  maybe.value\n",
                "union payloads are accessed through match arms",
            ),
            "union match payload missing": (
                "union MaybeI32:\n  some value: i32\n\nbad maybe: MaybeI32 gives i32:\n  match maybe:\n    MaybeI32.some gives 1\n    otherwise gives 0\n",
                "variant MaybeI32.some pattern requires payload fields value",
            ),
            "union match payload on payload-free variant": (
                "union MaybeI32:\n  none\n\nbad maybe: MaybeI32 gives i32:\n  match maybe:\n    MaybeI32.none with value gives value\n    otherwise gives 0\n",
                "variant MaybeI32.none has no payload",
            ),
            "union pattern field order mismatch": (
                "union Token:\n  operator symbol: u8 and precedence: u8\n\nbad token: Token gives i32:\n  match token:\n    Token.operator with precedence and symbol gives 0\n    otherwise gives 1\n",
                "variant Token.operator payload fields must appear in declaration order: symbol, precedence",
            ),
            "union pattern missing field": (
                "union Token:\n  operator symbol: u8 and precedence: u8\n\nbad token: Token gives i32:\n  match token:\n    Token.operator with symbol gives 0\n    otherwise gives 1\n",
                "variant Token.operator pattern requires payload fields symbol, precedence",
            ),
            "union pattern extra field": (
                "union Token:\n  operator symbol: u8\n\nbad token: Token gives i32:\n  match token:\n    Token.operator with symbol and precedence gives 0\n    otherwise gives 1\n",
                "variant Token.operator has no payload field precedence",
            ),
            "union pattern duplicate alias": (
                "union Token:\n  operator symbol: u8 and precedence: u8\n\nbad token: Token gives i32:\n  match token:\n    Token.operator with symbol as x and precedence as x gives 0\n    otherwise gives 1\n",
                "match pattern has duplicate binding x",
            ),
            "union payload binding shadows existing": (
                "union Token:\n  operator symbol: u8 and precedence: u8\n\nbad token: Token gives i32:\n  let symbol be 1\n  match token:\n    Token.operator with symbol and precedence gives symbol\n    otherwise gives 0\n",
                "match payload binding symbol conflicts with existing binding symbol",
            ),
            "union payload alias shadows existing": (
                "union Token:\n  operator symbol: u8 and precedence: u8\n\nbad token: Token gives i32:\n  let op be 1\n  match token:\n    Token.operator with symbol as op and precedence as prec gives op\n    otherwise gives 0\n",
                "match payload binding op conflicts with existing binding op",
            ),
            "union original field unavailable after alias": (
                "union MaybeI32:\n  some value: i32\n\nbad maybe: MaybeI32 gives i32:\n  match maybe:\n    MaybeI32.some with value as n gives value\n    otherwise gives 0\n",
                "unknown binding value",
            ),
            "union match duplicate variant": (
                "union MaybeI32:\n  none\n\nbad maybe: MaybeI32 gives i32:\n  match maybe:\n    MaybeI32.none gives 1\n    MaybeI32.none gives 2\n    otherwise gives 0\n",
                "match has duplicate pattern MaybeI32.none",
            ),
            "union match pattern type mismatch": (
                "union A:\n  none\n\nunion B:\n  none\n\nbad a: A gives i32:\n  match a:\n    B.none gives 1\n    otherwise gives 0\n",
                "match pattern must have type A, got B",
            ),
            "union constants unsupported": (
                "union MaybeI32:\n  none\n\nconstant none: MaybeI32 be MaybeI32.none\n",
                "union constants are not supported in v0.25",
            ),
            "union record field unsupported": (
                "union MaybeI32:\n  none\n\nrecord Bad:\n  maybe: MaybeI32\n",
                "record fields may not be union types in v0.25",
            ),
            "array of union unsupported": (
                "union MaybeI32:\n  none\n\nbad gives i32:\n  let values be array of 1 MaybeI32 containing MaybeI32.none\n  0\n",
                "array element type may not be a union type in v0.25",
            ),
            "duplicate type alias": (
                "type Count be i32\ntype Count be i64\n\nmain gives i32:\n  0\n",
                "type Count is already defined",
            ),
            "type alias collides with record": (
                "record Count:\n  value: i32\n\ntype Count be i32\n",
                "type Count conflicts with record Count",
            ),
            "type alias collides with constant": (
                "constant Count: i32 be 1\n\ntype Count be i32\n",
                "type Count conflicts with constant Count",
            ),
            "unknown type alias target": (
                "type MissingAlias be Missing\n\nmain gives i32:\n  0\n",
                "unknown type Missing",
            ),
            "direct type alias cycle": (
                "type A be A\n\nmain gives i32:\n  0\n",
                "type alias cycle detected: A -> A",
            ),
            "indirect type alias cycle": (
                "type A be B\ntype B be C\ntype C be A\n\nmain gives i32:\n  0\n",
                "type alias cycle detected: A -> B -> C -> A",
            ),
            "view alias storage constructor": (
                "type CellView be view of i32\n\nbad gives i32:\n  let cells be CellView filled with 0\n  0\n",
                "type alias CellView resolves to view of i32 and cannot be constructed with filled with",
            ),
            "scalar alias storage constructor": (
                "type Count be i32\n\nbad gives i32:\n  let cells be Count filled with 0\n  0\n",
                "type alias Count resolves to i32 and cannot be constructed with filled with",
            ),
            "array alias mutation": (
                "type CellArray be array of 4 i32\n\nbad gives i32:\n  let numbers be CellArray containing 1, 2, 3, 4\n  numbers at 0 becomes 9\n  0\n",
                "cannot store into array numbers; arrays are immutable",
            ),
            "alias to i1 array element invalid": (
                "type Flag be i1\n\nbad gives i32:\n  let flags be array of 2 Flag containing true, false\n  0\n",
                "array element type must be numeric, got i1",
            ),
            "alias to union record field invalid": (
                "union MaybeI32:\n  none\n\ntype OptionalNumber be MaybeI32\n\nrecord Bad:\n  maybe: OptionalNumber\n",
                "record fields may not be union types in v0.25",
            ),
            "alias to f64 layout field invalid": (
                "type Float be f64\n\nlayout record Bad:\n  value: Float\n",
                "layout record fields must be integer types, got f64",
            ),
            "alias to enum export rejected": (
                "enum Mode: u8:\n  idle be 0\n\ntype ModeAlias be Mode\n\nexport set mode mode: ModeAlias does as ins_set_mode:\n  require mode is equal to Mode.idle\n",
                "exported phrase parameters must be primitive scalar types, got Mode",
            ),
            "qualified alias unknown": (
                "module Types\n\ntype Count be i32\n\nmain gives i32:\n  let x: Types.Missing be 0\n  x\n",
                "unknown type Types.Missing",
            ),
            "alias to array parameter rejected": (
                "type Scores be array of 4 i32\n\nbad scores: Scores gives i32:\n  0\n",
                "array parameters are not supported in v0.22; use view of i32",
            ),
            "byte literal empty": ("bad gives i32:\n  byte \"\" as i32\n", "byte literal must decode to exactly one byte, got 0"),
            "byte literal too long": ("bad gives i32:\n  byte \"AB\" as i32\n", "byte literal must decode to exactly one byte, got 2"),
            "byte literal invalid escape": ("bad gives i32:\n  byte \"\\q\" as i32\n", "invalid escape sequence \\q"),
            "byte literal short hex escape": (
                "bad gives i32:\n  byte \"\\x4\" as i32\n",
                "hex escape must contain exactly two hexadecimal digits",
            ),
            "byte literal invalid hex digits": (
                "bad gives i32:\n  byte \"\\xGG\" as i32\n",
                "hex escape contains non-hexadecimal digit",
            ),
            "byte string used as value": (
                "bad gives i32:\n  let x be bytes \"hello\"\n  0\n",
                "byte string literal cannot be used as a value; use `array of bytes` or `buffer of bytes`",
            ),
            "empty inferred byte array": (
                "bad gives i32:\n  let text be array of bytes \"\"\n  0\n",
                "byte array literal must contain at least one byte",
            ),
            "empty inferred byte buffer": (
                "bad gives i32:\n  let text be buffer of bytes \"\"\n  0\n",
                "byte buffer literal must contain at least one byte",
            ),
            "byte string splice in non-u8 array": (
                "bad gives i32:\n  let cells be array of 5 i32 containing bytes \"hello\"\n  0\n",
                "byte string literal can only initialize u8 arrays or buffers, got i32",
            ),
            "byte string splice count mismatch": (
                "bad gives i32:\n  let text be array of 4 u8 containing bytes \"hello\"\n  0\n",
                "array text expects 4 elements, got 5",
            ),
            "byte string splice in enum array": (
                "enum ByteEnum: u8:\n  a be 65\n\nbad gives i32:\n  let values be array of 1 ByteEnum containing bytes \"A\"\n  0\n",
                "byte string literal can only initialize u8 arrays or buffers, got ByteEnum",
            ),
            "duplicate byte match pattern": (
                "bad b: u8 gives i32:\n  match b:\n    byte \"A\" gives 1\n    65 gives 2\n    otherwise gives 3\n",
                "match has duplicate pattern 65",
            ),
            "length of bytes invalid escape": ("bad gives i32:\n  length of bytes \"\\q\"\n", "invalid escape sequence \\q"),
            "unterminated byte string": ("bad gives i32:\n  byte \"A\n", "unterminated string literal"),
            "export union unsupported": (
                "union MaybeI32:\n  none\n\nexport exported maybe maybe: MaybeI32 gives i32 as ins_maybe:\n  0\n",
                "exported phrase parameters must be primitive scalar types, got MaybeI32",
            ),
            "extern union unsupported": (
                "union MaybeI32:\n  none\n\nextern host maybe maybe: MaybeI32 does as host_maybe\n",
                "extern phrase parameters must be primitive scalar types, got MaybeI32",
            ),
            "extern with body": (
                "extern population count of x: i32 gives i32 as llvm.ctpop.i32:\n  x\n",
                "extern phrase declarations cannot have bodies",
            ),
            "extern buffer parameter unsupported": (
                "extern sum cells cells: buffer of 4 i32 gives i32 as sum_cells\n",
                "extern phrase parameters must be scalar types, got buffer of 4 i32",
            ),
            "extern view parameter unsupported": (
                "extern sum view cells: view of i32 gives i32 as sum_view\n",
                "extern phrase parameters must be scalar types, got view of i32",
            ),
            "extern record parameter unsupported": (
                "record Point:\n  x: i32\n  y: i32\n\nextern sum point p: Point gives i32 as sum_point\n",
                "extern phrase parameters must be scalar types, got Point",
            ),
            "extern record return unsupported": (
                "record Point:\n  x: i32\n  y: i32\n\nextern make point gives Point as make_point\n",
                "extern phrase return types must be scalar types, got Point",
            ),
            "extern duplicate normal phrase": (
                "extern population count of x: i32 gives i32 as llvm.ctpop.i32\n\npopulation count of x: i32 gives i32:\n  x\n",
                "phrase `population count of _` is already defined",
            ),
            "extern gives used as step": (
                "extern population count of x: i32 gives i32 as llvm.ctpop.i32\n\nbad gives i32:\n  population count of 15\n  0\n",
                "phrase `population count of _` returns i32 and cannot be used as a step",
            ),
            "extern does used as expression": (
                "extern host notify code: i32 does as host_notify\n\nbad gives i32:\n  let x be host notify 1\n  x\n",
                "phrase `host notify _` does not return a value",
            ),
            "extern call in constant initializer": (
                "extern population count of x: i32 gives i32 as llvm.ctpop.i32\n\nconstant x: i32 be population count of 15\n",
                "constant x must be compile-time evaluable",
            ),
            "extern call in check": (
                "extern population count of x: i32 gives i32 as llvm.ctpop.i32\n\ncheck population count of 15 is equal to 4\n",
                "check expression must be compile-time evaluable",
            ),
            "external symbol incompatible declarations": (
                "extern pop of x: i32 gives i32 as host_pop\nextern pop wide of x: i64 gives i64 as host_pop\n\nmain gives i32:\n  pop of 1\n",
                "external symbol host_pop declared with incompatible types",
            ),
            "external symbol conflicts with generated function": (
                "extern external main gives i32 as main\n\nmain gives i32:\n  0\n",
                "external symbol main conflicts with generated function main",
            ),
            "exported phrase missing body": (
                "export add x: i32 and y: i32 gives i32 as ins_add\n",
                "exported phrase definitions require a body",
            ),
            "exported buffer parameter unsupported": (
                "export sum cells cells: buffer of 4 i32 gives i32 as ins_sum_cells:\n  0\n",
                "exported phrase parameters must be scalar types, got buffer of 4 i32",
            ),
            "exported view parameter unsupported": (
                "export sum view cells: view of i32 gives i32 as ins_sum_view:\n  0\n",
                "exported phrase parameters must be scalar types, got view of i32",
            ),
            "exported record parameter unsupported": (
                "record Point:\n  x: i32\n  y: i32\n\nexport sum point p: Point gives i32 as ins_sum_point:\n  p.x plus p.y\n",
                "exported phrase parameters must be scalar types, got Point",
            ),
            "exported record return unsupported": (
                "record Point:\n  x: i32\n  y: i32\n\nexport make point gives Point as ins_make_point:\n  Point with x be 1 and y be 2\n",
                "exported phrase return types must be scalar types, got Point",
            ),
            "exported duplicate normal phrase": (
                "export add x: i32 and y: i32 gives i32 as ins_add:\n  x plus y\n\nadd x: i32 and y: i32 gives i32:\n  x plus y\n",
                "phrase `add _ and _` is already defined",
            ),
            "exported duplicate extern phrase": (
                "extern add x: i32 and y: i32 gives i32 as host_add\n\nexport add x: i32 and y: i32 gives i32 as ins_add:\n  x plus y\n",
                "phrase `add _ and _` is already defined",
            ),
            "exported symbol duplicate": (
                "export add x: i32 and y: i32 gives i32 as ins_op:\n  x plus y\n\nexport sub x: i32 and y: i32 gives i32 as ins_op:\n  x minus y\n",
                "exported symbol ins_op is already defined",
            ),
            "exported symbol conflicts with extern symbol": (
                "extern host add x: i32 and y: i32 gives i32 as ins_add\n\nexport add x: i32 and y: i32 gives i32 as ins_add:\n  x plus y\n",
                "exported symbol ins_add conflicts with external symbol ins_add",
            ),
            "exported symbol conflicts with generated normal function": (
                "normal helper gives i32:\n  0\n\nexport exported helper gives i32 as normal_helper:\n  0\n",
                "exported symbol normal_helper conflicts with generated function normal_helper",
            ),
            "exported symbol main rejected": (
                "export exported main gives i32 as main:\n  0\n",
                "exported symbol main conflicts with generated function main",
            ),
            "exported gives used as step": (
                "export add x: i32 and y: i32 gives i32 as ins_add:\n  x plus y\n\nbad gives i32:\n  add 1 and 2\n  0\n",
                "phrase `add _ and _` returns i32 and cannot be used as a step",
            ),
            "exported does used as expression": (
                "export notify code: i32 does as ins_notify:\n  require code is greater than or equal to 0\n\nbad gives i32:\n  let x be notify 1\n  x\n",
                "phrase `notify _` does not return a value",
            ),
            "exported call in constant initializer": (
                "export add x: i32 and y: i32 gives i32 as ins_add:\n  x plus y\n\nconstant x: i32 be add 1 and 2\n",
                "constant x must be compile-time evaluable",
            ),
            "exported call in check": (
                "export add x: i32 and y: i32 gives i32 as ins_add:\n  x plus y\n\ncheck add 1 and 2 is equal to 3\n",
                "check expression must be compile-time evaluable",
            ),
            "owned buffer static zero length": (
                "bad gives i32:\n  let cells be owned buffer of 0 i32 filled with 0\n  0\n",
                "owned buffer length must be at least 1",
            ),
            "owned buffer length type mismatch": (
                "bad n: i64 gives i32:\n  let cells be owned buffer of n i32 filled with 0\n  0\n",
                "owned buffer length must have type i32, got i64",
            ),
            "owned buffer boolean length": (
                "bad gives i32:\n  let cells be owned buffer of true i32 filled with 0\n  0\n",
                "owned buffer length must have type i32, got i1",
            ),
            "owned buffer i1 element unsupported": (
                "bad n: i32 gives i32:\n  let flags be owned buffer of n i1 filled with false\n  0\n",
                "owned buffer element type must be numeric or enum, got i1",
            ),
            "owned buffer union element unsupported": (
                "union MaybeI32:\n  none\n\nbad n: i32 gives i32:\n  let values be owned buffer of n MaybeI32 filled with MaybeI32.none\n  0\n",
                "owned buffer element type may not be a union type in v0.30",
            ),
            "owned buffer fill type mismatch": (
                "bad n: i32 gives i32:\n  let cells be owned buffer of n i32 filled with true\n  0\n",
                "owned buffer cells fill value must have type i32, got i1",
            ),
            "owned buffer used as scalar": (
                "bad gives i32:\n  let cells be owned buffer of 4 i32 filled with 0\n  cells\n",
                "owned buffer cells cannot be used as a scalar value; use `cells at index`",
            ),
            "owned buffer rebind invalid": (
                "bad gives i32:\n  let cells be owned buffer of 4 i32 filled with 0\n  cells becomes 1\n  0\n",
                "cannot rebind owned buffer cells",
            ),
            "owned buffer copy invalid": (
                "bad gives i32:\n  let cells be owned buffer of 4 i32 filled with 0\n  let copy be cells\n  0\n",
                "owned buffer cells cannot be used as a value",
            ),
            "owned buffer passed to fixed buffer parameter": (
                "sum buffer cells: buffer of 4 i32 gives i32:\n  0\n\nbad gives i32:\n  let cells be owned buffer of 4 i32 filled with 0\n  sum buffer cells\n",
                "argument cells must have type buffer of 4 i32, got owned buffer of i32",
            ),
            "branch local owned buffer escape": (
                "bad flag: i1 gives i32:\n  if flag:\n    let cells be owned buffer of 4 i32 filled with 0\n  otherwise:\n    let ignored be 0\n  cells at 0\n",
                "unknown binding cells",
            ),
            "loop local owned buffer escape": (
                "bad gives i32:\n  for i from 0 up to 1:\n    let cells be owned buffer of 4 i32 filled with 0\n  cells at 0\n",
                "unknown binding cells",
            ),
            "match arm local owned buffer escape": (
                "enum Mode: u8:\n  small be 0\n\nbad mode: Mode gives i32:\n  match mode:\n    Mode.small:\n      let cells be owned buffer of 4 i32 filled with 0\n    otherwise:\n      let ignored be 0\n  cells at 0\n",
                "unknown binding cells",
            ),
            "branch local owned view escape": (
                "bad flag: i1 gives i32:\n  if flag:\n    let cells be owned buffer of 4 i32 filled with 0\n    let window be view of cells from 0 for 4\n  otherwise:\n    let ignored be 0\n  length of window\n",
                "unknown binding window",
            ),
            "nested owned buffer copy invalid": (
                "bad flag: i1 gives i32:\n  if flag:\n    let cells be owned buffer of 4 i32 filled with 0\n    let copy be cells\n  otherwise:\n    let ignored be 0\n  0\n",
                "owned buffer cells cannot be used as a value",
            ),
            "nested owned buffer rebind invalid": (
                "bad gives i32:\n  for i from 0 up to 1:\n    let cells be owned buffer of 4 i32 filled with 0\n    cells becomes 1\n  0\n",
                "cannot rebind owned buffer cells",
            ),
            "owned buffer byte string unsupported": (
                "bad gives i32:\n  let bytes be owned buffer of bytes \"hello\"\n  0\n",
                "owned buffer byte-string initialization is not supported in v0.29",
            ),
            "owned buffer static index out of bounds": (
                "bad gives i32:\n  let cells be owned buffer of 4 i32 filled with 0\n  cells at 4\n",
                "owned buffer index 4 is out of bounds for owned buffer cells of length 4",
            ),
            "nested owned buffer static index out of bounds": (
                "bad gives i32:\n  let result be 0\n  if true:\n    let cells be owned buffer of 4 i32 filled with 0\n    result becomes cells at 4\n  otherwise:\n    let ignored be 0\n  result\n",
                "owned buffer index 4 is out of bounds for owned buffer cells of length 4",
            ),
            "layout write to non u8 owned buffer": (
                "packed layout record Word:\n  value: u16\n\nbad gives i32:\n  let cells be owned buffer of 2 i32 filled with 0\n  let word be Word with value be 1\n  write word into cells at 0\n  0\n",
                "write Word requires a u8 buffer or view, got owned buffer of i32",
            ),
        }
        for name, (source, contains) in cases.items():
            with self.subTest(name=name):
                self.assertCompileError(source, contains)


if __name__ == "__main__":
    unittest.main()
