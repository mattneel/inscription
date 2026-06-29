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
        self.assertRegex(mlir, r"%v\d+ = scf\.if %v\d+ -> \(i32\)")
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
                "--convert-func-to-llvm",
                "--reconcile-unrealized-casts",
            ],
        )
        verify_mlir(compile_source(self.fixture("add.ins")), toolchain)

    def assertCompileError(self, source: str, contains: str):
        with self.assertRaises(InscriptionError) as ctx:
            compile_source(source)
        self.assertIn(contains, str(ctx.exception))

    def test_phrase_definitions_reject_unsupported_types(self):
        self.assertCompileError(
            "identity of x: f64 gives i32:\n  x\n\nmain gives i32:\n  0\n",
            "only support i32",
        )
        self.assertCompileError(
            "identity of x: i32 gives f64:\n  x\n\nmain gives i32:\n  0\n",
            "only support i32 return",
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
            "missing main": ("one gives i32:\n  1\n", "must define main"),
            "invalid main": ("main of argc: i32 gives i32:\n  argc\n", "main must take no parameters"),
            "unsupported operator": ("main gives i32:\n  4 divided by 2\n", "unexpected token"),
            "glued plus operator": ("main gives i32:\n  1plus 2\n", "missing whitespace"),
            "glued times operator": ("main gives i32:\n  3times 2\n", "missing whitespace"),
            "glued phrase connector": (
                "add a: i32 and b: i32 gives i32:\n  a plus b\n\nmain gives i32:\n  add 2and 3\n",
                "missing whitespace",
            ),
            "unsupported io": ("main gives i32:\n  print 1\n", "unexpected token"),
            "arrays": ("main gives i32:\n  array of 1\n", "unexpected token"),
            "floats": ("main gives i32:\n  1.5\n", "invalid token"),
            "pointers": ("main gives i32:\n  pointer\n", "unexpected token"),
            "memrefs": ("main gives i32:\n  memref\n", "unexpected token"),
            "reserved hole name": ("echo of let: i32 gives i32:\n  let\n\nmain gives i32:\n  0\n", "reserved word"),
            "out of range literal": ("main gives i32:\n  2147483648\n", "outside signed i32"),
        }
        for name, (source, contains) in cases.items():
            with self.subTest(name=name):
                self.assertCompileError(source, contains)


if __name__ == "__main__":
    unittest.main()
