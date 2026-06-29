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
from inscription.runner import LOWERING_PASSES, ToolchainError, resolve_toolchain, run_file, run_source, verify_mlir

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
            "record return type unsupported": (
                "record Point:\n  x: i32\n  y: i32\n\nmake point gives Point:\n  Point with x be 1 and y be 2\n",
                "record return types are not supported in v0.7",
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
                "view return types are not supported in v0.11",
            ),
        }
        for name, (source, contains) in cases.items():
            with self.subTest(name=name):
                self.assertCompileError(source, contains)


if __name__ == "__main__":
    unittest.main()
