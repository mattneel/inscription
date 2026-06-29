# Inscription v0 specification

Inscription v0 is a deterministic, fixed-pattern, phrase-shaped compiler. It is prose-like, but it is not a natural-language system: every accepted source line matches one grammar production exactly. Unsupported prose is rejected with a diagnostic.

## Execution model

- A program is a list of phrase definitions.
- A phrase definition introduces a callable phrase template with zero or more typed holes.
- All user-visible values are signed `i32` integers.
- Comparisons produce internal `i1` values used by conditional value blocks.
- Every phrase definition returns `i32`.
- `main gives i32:` must exist, take no holes, and lower to `func.func @main() -> i32`.
- v0 has no source I/O. For executable fixtures, the only observable result is the LLVM `lli` process exit status.
- Fixture expected exits must be in `0..255`.

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
- Integer literals are base-10 signed i32 literals.
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

The compiler lowers the example above to a `func.func @max(%..., %...) -> i32` and an `scf.if` result expression.

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

Expressions are deterministic and have only integer results:

- integer literal: `120`
- zero literal: `zero`
- variable reference: `result`
- phrase call: `max of 7 and 3`
- binary arithmetic: `plus`, `minus`, `times`

Precedence is `times` before `plus`/`minus`; operators are left-associative. Parentheses are not part of v0.

Comparisons are used by `when` clauses:

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
- `main` must exist and take no holes.
- All holes and return values must be `i32`.
- Conditional value blocks require `otherwise` and lower through `scf.if` results.
- Unsupported `Function`, `End function`, `Set`, `Return`, `call ... with`, I/O, arrays, floats, pointers, memrefs, structs, proof prose, natural-language requests, and custom dialect syntax are rejected.

## MLIR subset

The phrase-only v0 emitter uses only:

```text
builtin.module
func.func
func.call
func.return
arith.constant
arith.addi
arith.subi
arith.muli
arith.cmpi
scf.if
scf.yield
```

No memory or storage lowering is permitted: no `memref`, `alloca`, globals, heap objects, stack slots, mutable storage dialects, or `scf.while`.
