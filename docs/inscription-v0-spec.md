# Inscription v0 specification

Inscription v0 is a deterministic, fixed-pattern, plain-text compiler. It is prose-shaped, but it is not a natural-language system: every accepted source line matches one grammar production exactly. Unsupported prose is rejected with a diagnostic.

## Execution model

- A program is a list of function definitions.
- All user-visible values are signed `i32` integers.
- Comparisons produce internal `i1` values used only by `if` and `while`.
- Every function returns `i32`.
- `main` must exist, take no parameters, and lower to `func.func @main() -> i32`.
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
- Every nonblank source line ends with `.`.
- Identifiers match `[a-z][a-z0-9_]*` and cannot be reserved words.
- Integer literals are base-10 signed i32 literals.
- Keywords are fixed English words shown in the grammar.

## Statements

- `Function name takes no parameters.`
- `Function name takes a and b.`
- `Function name takes a, b, and c.`
- `End function.`
- `Set name to expression.`
- `If comparison then.` ... `Otherwise.` ... `End if.`
- `While comparison do.` ... `End while.`
- `Return expression.`

`Return` is a tail statement for the function body in v0. Branching return-code programs use `Set result ...` in branches and a single final `Return result.`.

## Expressions

Expressions are deterministic and have only integer results:

- integer literal: `120`
- variable reference: `result`
- function call: `call add with 2 and 3`
- three-or-more names and call arguments use comma-separated or Oxford-comma forms, not repeated bare `and`
- function call with no arguments: `call main with no arguments`
- binary arithmetic: `plus`, `minus`, `times`

Precedence is `times` before `plus`/`minus`; operators are left-associative. Parentheses are not part of v0.

Comparisons are used only by `if` and `while`:

- `left is equal to right`
- `left is not equal to right`
- `left is less than right`
- `left is less than or equal to right`
- `left is greater than right`
- `left is greater than or equal to right`

## Semantic rules

- Function names are unique.
- Parameter names are unique.
- Calls must target known functions with the exact arity.
- Variables must be initialized before use.
- `if` requires `Otherwise` and joins variables through `scf.if` results.
- Variables assigned inside `while` must be initialized before the loop and lower as loop-carried SSA values through `scf.while`.
- New variables cannot be introduced only inside a loop.
- v0 has no block-local scope and no early `Return` inside `if`, `otherwise`, or `while` blocks.
- Unsupported I/O, arrays, floats, pointers, memrefs, structs, proof prose, natural-language requests, and custom dialect syntax are rejected.

## MLIR subset

The emitter uses only:

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
scf.while
scf.condition
scf.yield
```

No memory or storage lowering is permitted: no `memref`, `alloca`, globals, heap objects, stack slots, or mutable storage dialects.
