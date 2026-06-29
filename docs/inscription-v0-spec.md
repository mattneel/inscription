# Inscription v0 specification

Inscription v0 is a deterministic, fixed-pattern, phrase-shaped compiler. It is prose-like, but it is not a natural-language system: every accepted source line matches one grammar production exactly. Unsupported prose is rejected with a diagnostic.

## Execution model

- A program is a list of phrase definitions.
- A phrase definition introduces a callable phrase template with zero or more typed holes.
- Source-visible scalar types are `i1`, `i32`, and `i64`.
- Arithmetic operates on numeric values: `i32` and `i64`.
- Comparisons produce `i1` values and may be used in conditions or returned from phrases.
- Each phrase block evaluates to a value, which is the phrase result.
- Library compilation does not require `main`.
- If `main` exists, it must take no holes. Executable fixtures use `main gives i32:` and observe the LLVM `lli` process exit status.
- Fixture expected exits must be in `0..255`.
- v0 has no source I/O.

## Toolchain contract

The CLI resolves LLVM tools from `MLIR_TOOLCHAIN` when set, otherwise `/usr/lib/llvm-22/bin`. It requires `mlir-opt`, `mlir-translate`, and `lli` to report LLVM/MLIR `22.x`; there is no fallback to another LLVM version.

The run pipeline verifies emitted MLIR before lowering, then uses this lowering/translation/execution pipeline with LLVM 22 tools:

```sh
mlir-opt input.mlir \
  --convert-scf-to-cf \
  --convert-cf-to-llvm \
  --convert-arith-to-llvm \
  --convert-func-to-llvm \
  --reconcile-unrealized-casts \
  -o lowered.mlir
mlir-translate --mlir-to-llvmir lowered.mlir -o output.ll
lli output.ll
```

## Lexical rules

- Blank lines are ignored.
- Phrase headers end with `:`.
- Body lines are bare lines without statement terminators.
- Identifiers match `[a-z][a-z0-9_]*` and cannot be reserved words.
- Integer literals are base-10 signed 64-bit literals and are typed by context; untyped integer-only arithmetic defaults to `i32`.
- `zero` is sugar for integer literal `0`.
- Keywords are fixed English words shown in the grammar.

## Phrase definitions

A phrase definition has a template and a value block:

```text
max of a: i32 and b: i32 gives i32:
  a when a is greater than b
  otherwise b
```

The template's literal words define the callable surface. Typed holes (`a: i32`, `b: i32`) define parameters. A call fills those holes with expressions:

```text
max of 7 and 3
```

The compiler lowers the example above to a `func.func @max(%a: i32, %b: i32) -> i32` and an `scf.if` result expression.

Phrase names are generated from the leading literal words in a phrase definition. v0 has no overloads, so generated phrase names must be unique.

## Value blocks

An Inscription block evaluates to a value. v0 supports:

```text
expression
expression when condition
otherwise expression
let name be expression
```

Rules:

- A block may contain zero or more `let` bindings before its value lines.
- A block with one unconditional expression evaluates to that expression.
- A block with `when` lines must end with exactly one `otherwise` line.
- `otherwise` is the fallback value.
- `let` bindings cannot appear after value lines.
- There is no statement-level `return` in v0.

## Expressions

Expressions are deterministic and statically typed:

- integer literal: `120`
- zero literal: `zero`
- variable reference: `result`
- phrase call: `max of 7 and 3`
- binary arithmetic: `plus`, `minus`, `times`, `divided by`
- parenthesized expression: `(a plus b) times 2`
- comparison expression: `x is equal to 0`

Precedence is `times` and `divided by` before `plus` and `minus`; operators are left-associative. Parentheses override precedence.

Comparisons are expressions returning `i1` and are also used by `when` clauses:

- `left is equal to right`
- `left is not equal to right`
- `left is less than right`
- `left is less than or equal to right`
- `left is greater than right`
- `left is greater than or equal to right`

## Semantic rules

- Generated phrase names are unique; v0 has no overloads.
- Parameter names are unique.
- Calls must match a known phrase template.
- Variables must be initialized by a phrase hole or prior `let` before use.
- If `main` exists, it must take no holes.
- Types are exactly `i1`, `i32`, and `i64`.
- Arithmetic requires matching numeric operand types (`i32` or `i64`).
- Comparisons require matching numeric operand types and return `i1`.
- Integer literals are coerced to the numeric type required by their context when possible.
- Conditional value blocks require `otherwise` and lower through `scf.if` results.
- Unsupported `Function`, `End function`, `Set`, `Return`, `call ... with`, I/O, arrays, floats, pointers, memrefs, structs, proof prose, natural-language requests, and custom dialect syntax are rejected.

## MLIR subset

The phrase-only v0 emitter uses only:

```text
builtin.module
func.func
func.call
return
arith.constant
arith.addi
arith.subi
arith.muli
arith.divsi
arith.cmpi
scf.if
scf.yield
```

No memory or storage lowering is permitted: no `memref`, `alloca`, globals, heap objects, stack slots, mutable storage dialects, or `scf.while`.

## Golden conformance suite

The minimum v0 quality bar is the exact-output golden suite in `tests/goldens`. Each `*.ins` source file must compile byte-for-byte to its sibling `*.mlir`; the unit test suite enforces this with unified diffs on mismatch.
