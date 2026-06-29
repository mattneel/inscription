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
                (GOLDENS / "23_u8_cast.ins").read_text(),
                (GOLDENS / "24_bitwise_flags.ins").read_text(),
                (GOLDENS / "25_shifts.ins").read_text(),
                (GOLDENS / "27_pack_bytes.ins").read_text(),
                (GOLDENS / "28_unsigned_comparison.ins").read_text(),
                (GOLDENS / "29_buffer_sum.ins").read_text(),
                (GOLDENS / "35_fill_buffer_procedure.ins").read_text(),
                "highlight new widths a: i8 and b: i16 and c: u64 gives u64:\n  c bitwise xor c\n",
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
        verify_mlir(compile_source(self.fixture("add.ins")), toolchain)

    def assertCompileError(self, source: str, contains: str):
        with self.assertRaises(InscriptionError) as ctx:
            compile_source(source)
        self.assertIn(contains, str(ctx.exception))

    def test_phrase_definitions_reject_unsupported_types(self):
        self.assertCompileError(
            "identity of x: f64 gives i32:\n  x\n\nmain gives i32:\n  0\n",
            "supported scalar types",
        )
        self.assertCompileError(
            "identity of x: i32 gives f64:\n  x\n\nmain gives i32:\n  0\n",
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
        }
        for name, (source, contains) in cases.items():
            with self.subTest(name=name):
                self.assertCompileError(source, contains)


if __name__ == "__main__":
    unittest.main()
