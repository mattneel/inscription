# Inscription v0.1 specification

Inscription v0.1 is a deterministic, fixed-pattern, phrase-shaped compiler. It is prose-like, but it is not a natural-language system: every accepted source line matches one grammar production exactly. Unsupported prose is rejected with a diagnostic.

v0.1 extends v0 with source-level tracked mutable bindings, assignments, `while` loops lowered as loop-carried SSA values, boolean literals, and signed remainder. It does not introduce source-level storage or memory lowering.

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
- v0.1 has no source I/O.

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

## Lexical and layout rules

- Blank lines are ignored.
- Phrase headers and `while` headers end with `:`.
- Body lines are bare lines without statement terminators.
- Indented lines after a `while` header form that loop's step block.
- Identifiers match `[a-z][a-z0-9_]*` and cannot be reserved words.
- Integer literals are base-10 signed 64-bit literals and are typed by context; untyped integer-only arithmetic defaults to `i32`.
- `zero` is sugar for integer literal `0`.
- Boolean literals are `true` and `false` and have type `i1`.
- Keywords are fixed English words shown in the grammar.

## Phrase definitions

A phrase definition has a template and a body ending in a value block:

```text
max of a: i32 and b: i32 gives i32:
  a when a is greater than b
  otherwise b
```

The template's literal words define the callable surface. Typed holes (`a: i32`, `b: i32`) define parameters. A call fills those holes with expressions:

```text
max of 7 and 3
```

Phrase names are generated from the leading literal words in a phrase definition. v0.1 has no overloads, so generated phrase names must be unique.

## Body items and value blocks

An Inscription phrase body is:

```text
body_item*
value_block
```

Body items are evaluated sequentially and must appear before the value block:

```text
let name be expression
track name: type from expression
name becomes expression
while condition:
  step
```

A value block supports:

```text
expression
expression when condition
otherwise expression
```

Rules:

- A body may contain zero or more body items before its value block.
- A block with one unconditional expression evaluates to that expression.
- A block with `when` lines must end with exactly one `otherwise` line.
- `otherwise` is the fallback value.
- No body item may appear after the value block starts.
- There is no statement-level `return` in v0.1.

## Tracked bindings and assignment

A tracked binding introduces a mutable source-level name with a fixed type:

```text
track total: i32 from 0
track current: i64 from n
track done: i1 from false
```

Assignment updates the current compiler environment value for a tracked binding:

```text
total becomes total plus i
current becomes current minus 1
done becomes current is equal to zero
```

Assignments are sequential. In:

```text
a becomes b
b becomes a
```

the second assignment sees the updated value of `a`; swapping requires an explicit `let` temporary.

Tracked bindings lower to SSA values. Assignment emits the right-hand expression and updates the compiler's binding map; it emits no storage operation.

## While loops

A while loop has an `i1` condition and an indented step block:

```text
while i is less than or equal to n:
  total becomes total plus i
  i becomes i plus 1
```

Rules:

- The condition must type-check as `i1`.
- The body must contain at least one step.
- v0.1 while bodies support `let` bindings and assignments.
- Nested `while` loops are rejected until v0.2.
- `let` bindings inside a while body are scoped to that loop iteration and do not escape.
- Tracked bindings assigned inside a while are loop-carried values.

Lowering uses `scf.while` with deterministic loop-carried operands ordered by original `track` declaration order. The before region evaluates the condition and forwards the current carried values through `scf.condition`; the after region emits the body steps and yields the final carried values through `scf.yield`. The enclosing environment then maps each carried tracked binding to the corresponding `scf.while` result.

## Expressions

Expressions are deterministic and statically typed:

- integer literal: `120`
- zero literal: `zero`
- boolean literal: `true`, `false`
- variable reference: `result`
- phrase call: `max of 7 and 3`
- binary arithmetic: `plus`, `minus`, `times`, `divided by`, `remainder`
- parenthesized expression: `(a plus b) times 2`
- comparison expression: `x is equal to 0`

Precedence is `times`, `divided by`, and `remainder` before `plus` and `minus`; operators are left-associative. Parentheses override precedence.

Comparisons are expressions returning `i1` and are also used by `when` clauses and while conditions:

- `left is equal to right`
- `left is not equal to right`
- `left is less than right`
- `left is less than or equal to right`
- `left is greater than right`
- `left is greater than or equal to right`

## Semantic rules

- Generated phrase names are unique; v0.1 has no overloads.
- Parameter names are unique.
- Calls must match a known phrase template.
- Variables must be initialized by a phrase hole, prior `let`, or prior `track` before use.
- If `main` exists, it must take no holes.
- Types are exactly `i1`, `i32`, and `i64`.
- Phrase holes are immutable.
- `let` bindings are immutable.
- Assignment is valid only for tracked bindings.
- Track names may not shadow phrase holes, lets, or other tracks in the same function.
- Let names may not shadow visible phrase holes, tracks, or lets.
- Track initializers must match their declared type.
- Assignment right-hand sides must match the tracked binding's declared type.
- Arithmetic requires matching numeric operand types (`i32` or `i64`).
- `remainder` requires matching numeric operands and lowers to signed `arith.remsi`.
- Comparisons require matching numeric operand types and return `i1`.
- Integer literals are coerced to the numeric type required by their context when possible.
- Conditional value blocks require `otherwise` and lower through `scf.if` results.
- Unsupported `Function`, `End function`, `Set`, `Return`, `call ... with`, I/O, arrays, floats, pointers, memrefs, structs, proof prose, natural-language requests, custom dialect syntax, `break`, and `continue` are rejected.

## MLIR subset

The v0.1 emitter uses only:

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
arith.remsi
arith.cmpi
scf.if
scf.while
scf.condition
scf.yield
```

No memory or storage lowering is permitted: no `memref`, `alloca`, globals, heap objects, stack slots, mutable storage dialects, or `scf.while`-external state.

## Golden conformance suite

The minimum v0.1 quality bar is the exact-output golden suite in `tests/goldens`. Each `*.ins` source file must compile byte-for-byte to its sibling `*.mlir`; the unit test suite enforces this with unified diffs on mismatch.
