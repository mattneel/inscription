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

from inscription.compiler import compile_source
from inscription.diagnostics import InscriptionError
from inscription.runner import LOWERING_PASSES, ToolchainError, resolve_toolchain, run_source, verify_mlir

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
                actual = compile_source(source_path.read_text())
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
            "only support",
        )
        self.assertCompileError(
            "identity of x: i32 gives f64:\n  x\n\nmain gives i32:\n  0\n",
            "only support",
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
            "floats": ("main gives i32:\n  1.5\n", "invalid token"),
            "pointers": ("main gives i32:\n  pointer\n", "unexpected token"),
            "memrefs": ("main gives i32:\n  memref\n", "unexpected token"),
            "reserved hole name": ("echo of let: i32 gives i32:\n  let\n\nmain gives i32:\n  0\n", "reserved word"),
            "out of range literal": ("main gives i64:\n  9223372036854775808\n", "outside signed 64-bit"),
            "assignment to phrase hole": ("bad of x: i32 gives i32:\n  x becomes 1\n  x\n", "cannot assign to immutable phrase hole x"),
            "assignment to let binding": ("bad gives i32:\n  let x be 1\n  x becomes 2\n  x\n", "cannot assign to immutable let binding x"),
            "assignment to undeclared binding": ("bad gives i32:\n  y becomes 1\n  0\n", "unknown binding y"),
            "track initializer type mismatch": ("bad gives i32:\n  track x: i32 from false\n  x\n", "track x initializer must have type i32, got i1"),
            "assignment type mismatch": (
                "bad gives i32:\n  track x: i32 from 0\n  x becomes x is equal to 0\n  x\n",
                "assignment to x must have type i32, got i1",
            ),
            "while condition is not i1": (
                "bad gives i32:\n  track x: i32 from 0\n  while x:\n    x becomes x plus 1\n  x\n",
                "while condition must be i1",
            ),
            "while let does not escape": (
                "bad gives i32:\n  track x: i32 from 0\n  while x is less than 1:\n    let y be 2\n    x becomes x plus 1\n  y\n",
                "unknown binding y",
            ),
            "missing while body": (
                "bad gives i32:\n  track x: i32 from 0\n  while x is less than 1:\n  x\n",
                "while loop requires an indented body",
            ),
            "remainder on i1": ("bad gives i1:\n  true remainder false\n", "remainder requires numeric operands"),
            "remainder mismatched operands": (
                "to i64 of x: i32 gives i64:\n  1\n\nbad of y: i32 gives i32:\n  y remainder to i64 of y\n",
                "remainder operands must have same type",
            ),
            "if condition is not i1": (
                "bad gives i32:\n  track x: i32 from 0\n  if x:\n    x becomes 1\n  otherwise:\n    x becomes 2\n  x\n",
                "if condition must be i1",
            ),
            "missing if otherwise": (
                "bad gives i32:\n  track x: i32 from 0\n  if x is equal to 0:\n    x becomes 1\n  x\n",
                "if block requires otherwise",
            ),
            "empty if branch": (
                "bad gives i32:\n  track x: i32 from 0\n  if x is equal to 0:\n  otherwise:\n    x becomes 1\n  x\n",
                "if branch must contain at least one step",
            ),
            "empty otherwise branch": (
                "bad gives i32:\n  track x: i32 from 0\n  if x is equal to 0:\n    x becomes 1\n  otherwise:\n  x\n",
                "otherwise branch must contain at least one step",
            ),
            "branch let does not escape": (
                "bad gives i32:\n  track x: i32 from 0\n  if x is equal to 0:\n    let y be 1\n  otherwise:\n    let y be 2\n  y\n",
                "unknown binding y",
            ),
            "branch track does not escape": (
                "bad gives i32:\n  track x: i32 from 0\n  if x is equal to 0:\n    track y: i32 from 1\n  otherwise:\n    track y: i32 from 2\n  y\n",
                "unknown binding y",
            ),
            "boolean and requires i1": ("bad gives i1:\n  1 and 2\n", "and requires i1 operands"),
            "boolean or requires i1": ("bad gives i1:\n  1 or 2\n", "or requires i1 operands"),
            "boolean not requires i1": ("bad gives i1:\n  not 1\n", "not requires i1 operand"),
        }
        for name, (source, contains) in cases.items():
            with self.subTest(name=name):
                self.assertCompileError(source, contains)


if __name__ == "__main__":
    unittest.main()
