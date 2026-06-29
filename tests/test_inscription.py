from __future__ import annotations

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

from inscription.compiler import compile_source
from inscription.diagnostics import InscriptionError
from inscription.runner import LOWERING_PASSES, ToolchainError, resolve_toolchain, run_source, verify_mlir

FIXTURES = ROOT / "tests" / "fixtures" / "positive"


class CompilerTests(unittest.TestCase):
    def fixture(self, name: str) -> str:
        return (FIXTURES / name).read_text()

    def test_known_fixtures_execute_with_expected_exit_statuses(self):
        expected = json.loads((FIXTURES / "manifest.json").read_text())
        self.assertTrue(all(0 <= status <= 255 for status in expected.values()))
        for filename, status in expected.items():
            with self.subTest(filename=filename):
                try:
                    result = run_source(self.fixture(filename))
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
        self.assertIn("Function", proc.stdout)
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
        self.assertIn("Function", html)
        self.assertIn("highlight", html)

    def test_emits_required_core_ops_without_memory_or_custom_dialects(self):
        mlir = compile_source(self.fixture("while_factorial.ins"))
        self.assertIn("func.func @main() -> i32", mlir)
        self.assertIn("scf.while", mlir)
        self.assertIn("arith.muli", mlir)
        forbidden = ["memref", "alloca", "llvm.alloca", "global", "store", "load"]
        for needle in forbidden:
            self.assertNotIn(needle, mlir)

    def test_if_joins_lower_through_scf_if_results(self):
        mlir = compile_source(self.fixture("max_call.ins"))
        self.assertRegex(mlir, r"%v\d+ = scf\.if %v\d+ -> \(i32\)")
        self.assertIn("scf.yield", mlir)

    def test_while_reassignment_lowers_as_loop_carried_values(self):
        mlir = compile_source(self.fixture("while_factorial.ins"))
        self.assertRegex(mlir, r"%v\d+:2 = scf\.while \(")
        self.assertIn("scf.condition", mlir)
        self.assertIn("scf.yield", mlir)


    def test_valid_identifier_cannot_collide_with_generated_ssa_names(self):
        source = """Function echo takes v0.
Return v0.
End function.

Function main takes no parameters.
Return call echo with 7.
End function.
"""
        mlir = compile_source(source)
        self.assertIn("func.func @echo(%v0: i32) -> i32", mlir)
        try:
            result = run_source(source)
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 7)

    def test_empty_while_body_is_rejected_before_mlir_verification(self):
        self.assertCompileError(
            "Function main takes no parameters.\nSet n to 1.\nWhile n is greater than 0 do.\nEnd while.\nReturn n.\nEnd function.\n",
            "while body must reassign",
        )

    def test_name_list_matches_frozen_grammar(self):
        valid = """Function f takes a, b, and c.
Return a plus b plus c.
End function.
Function main takes no parameters.
Return call f with 1, 2, and 3.
End function.
"""
        self.assertIn("func.func @f", compile_source(valid))
        for source in (
            "Function f takes a and b and c.\nReturn a.\nEnd function.\nFunction main takes no parameters.\nReturn call f with 1, 2, and 3.\nEnd function.\n",
            "Function f takes a, b and c.\nReturn a.\nEnd function.\nFunction main takes no parameters.\nReturn call f with 1, 2, and 3.\nEnd function.\n",
            "Function f takes a, and b.\nReturn a.\nEnd function.\nFunction main takes no parameters.\nReturn call f with 1 and 2.\nEnd function.\n",
            "Function f takes a, b, and c, d.\nReturn a.\nEnd function.\nFunction main takes no parameters.\nReturn call f with 1, 2, 3, and 4.\nEnd function.\n",
            "Function f takes a, b, and c, and d.\nReturn a.\nEnd function.\nFunction main takes no parameters.\nReturn call f with 1, 2, 3, and 4.\nEnd function.\n",
        ):
            with self.subTest(source=source):
                self.assertCompileError(source, "malformed name list")

    def test_call_argument_list_matches_frozen_grammar(self):
        valid = """Function f takes a, b, and c.
Return a plus b plus c.
End function.
Function main takes no parameters.
Return call f with 1, 2, and 3.
End function.
"""
        try:
            result = run_source(valid)
        except ToolchainError as exc:
            self.skipTest(str(exc))
        self.assertEqual(result.exit_status, 6)
        for source in (
            "Function f takes a and b.\nReturn a plus b.\nEnd function.\nFunction main takes no parameters.\nReturn call f with 1, and 2.\nEnd function.\n",
            "Function f takes a, b, and c.\nReturn a plus b plus c.\nEnd function.\nFunction main takes no parameters.\nReturn call f with 1 and 2 and 3.\nEnd function.\n",
        ):
            with self.subTest(source=source):
                self.assertCompileError(source, "malformed call argument list")

    def test_block_terminators_are_case_sensitive(self):
        self.assertCompileError(
            "Function main takes no parameters.\nReturn 0.\nend function.\n",
            "unsupported or malformed",
        )

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
                "--convert-func-to-llvm",
                "--reconcile-unrealized-casts",
            ],
        )
        verify_mlir(compile_source(self.fixture("add.ins")), toolchain)

    def assertCompileError(self, source: str, contains: str):
        with self.assertRaises(InscriptionError) as ctx:
            compile_source(source)
        self.assertIn(contains, str(ctx.exception))

    def test_negative_diagnostics(self):
        cases = {
            "malformed sentence": ("Please add two numbers.\n", "expected function definition"),
            "unsupported free prose": (
                "Function main takes no parameters.\nPlease understand this naturally.\nReturn 0.\nEnd function.\n",
                "unsupported or malformed",
            ),
            "undefined variable": (
                "Function main takes no parameters.\nReturn missing.\nEnd function.\n",
                "used before initialization",
            ),
            "duplicate function": (
                "Function main takes no parameters.\nReturn 0.\nEnd function.\nFunction main takes no parameters.\nReturn 0.\nEnd function.\n",
                "duplicate function",
            ),
            "duplicate parameter": (
                "Function f takes a and a.\nReturn a.\nEnd function.\nFunction main takes no parameters.\nReturn call f with 1 and 2.\nEnd function.\n",
                "duplicate parameter",
            ),
            "wrong arity": (
                "Function f takes a.\nReturn a.\nEnd function.\nFunction main takes no parameters.\nReturn call f with 1 and 2.\nEnd function.\n",
                "expects 1 argument",
            ),
            "unknown function": (
                "Function main takes no parameters.\nReturn call nope with no arguments.\nEnd function.\n",
                "unknown function",
            ),
            "missing main": ("Function f takes no parameters.\nReturn 0.\nEnd function.\n", "must define main"),
            "invalid main": ("Function main takes argc.\nReturn argc.\nEnd function.\n", "main must take no parameters"),
            "unsupported operator": (
                "Function main takes no parameters.\nReturn 4 divided by 2.\nEnd function.\n",
                "unexpected token",
            ),
            "glued plus operator": (
                "Function main takes no parameters.\nReturn 1plus 2.\nEnd function.\n",
                "missing whitespace",
            ),
            "glued times operator": (
                "Function main takes no parameters.\nReturn 3times 2.\nEnd function.\n",
                "missing whitespace",
            ),
            "glued call separator": (
                "Function add takes a and b.\nReturn a plus b.\nEnd function.\nFunction main takes no parameters.\nReturn call add with 2and 3.\nEnd function.\n",
                "missing whitespace",
            ),
            "unsupported io": (
                "Function main takes no parameters.\nPrint 1.\nReturn 0.\nEnd function.\n",
                "unsupported or malformed",
            ),
            "arrays": (
                "Function main takes no parameters.\nSet xs to array of 1.\nReturn 0.\nEnd function.\n",
                "unexpected token",
            ),
            "floats": (
                "Function main takes no parameters.\nReturn 1.5.\nEnd function.\n",
                "invalid token",
            ),
            "pointers": (
                "Function main takes no parameters.\nSet pointer to address.\nReturn pointer.\nEnd function.\n",
                "reserved word",
            ),
            "memrefs": (
                "Function main takes no parameters.\nSet memref to 1.\nReturn memref.\nEnd function.\n",
                "reserved word",
            ),
            "reserved arguments keyword": (
                "Function echo takes arguments.\nReturn arguments.\nEnd function.\nFunction main takes no parameters.\nReturn call echo with 1.\nEnd function.\n",
                "reserved word",
            ),
            "out of range literal": (
                "Function main takes no parameters.\nReturn 2147483648.\nEnd function.\n",
                "outside signed i32",
            ),
        }
        for name, (source, contains) in cases.items():
            with self.subTest(name=name):
                self.assertCompileError(source, contains)


if __name__ == "__main__":
    unittest.main()
