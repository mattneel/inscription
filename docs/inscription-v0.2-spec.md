# Inscription v0.2 specification

Inscription v0.2 is a deterministic, phrase-shaped compiler. It is prose-like, but it is not natural-language interpretation: every accepted line matches the grammar exactly. v0.2 preserves v0 and v0.1 behavior and extends v0.1 with structured step-level control flow, nested while loops, and strict boolean operators.

## Execution model

- A program is a list of phrase definitions.
- A phrase definition introduces a callable phrase template with zero or more typed holes.
- Source-visible scalar types are `i1`, `i32`, and `i64`.
- Arithmetic operates on numeric values: `i32` and `i64`.
- Comparisons and boolean operators produce `i1` values.
- Each phrase body evaluates to a value; the final value block is the phrase result.
- Library compilation does not require `main`.
- If `main` exists, it must take no holes.
- v0.2 has no source I/O and no source-level storage.

## Toolchain contract

The CLI resolves LLVM tools from `MLIR_TOOLCHAIN` when set, otherwise `/usr/lib/llvm-22/bin`. It requires `mlir-opt`, `mlir-translate`, and `lli` to report LLVM/MLIR `22.x`.

The run pipeline verifies emitted MLIR before lowering, then uses:

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
- Phrase, `while`, `if`, and `otherwise` block headers end with `:`.
- Body lines are bare lines without statement terminators.
- Indented lines after a control-flow header form that block's step block.
- Identifiers match `[a-z][a-z0-9_]*` and cannot be reserved words.
- Integer literals are base-10 signed 64-bit literals and are typed by context; untyped integer-only arithmetic defaults to `i32`.
- `zero` is sugar for integer literal `0`.
- Boolean literals are `true` and `false` and have type `i1`.

## Phrase definitions

A phrase definition has a template and a body ending in a value block:

```text
max of a: i32 and b: i32 gives i32:
  a when a is greater than b
  otherwise b
```

The template's literal words define the callable surface. Typed holes define parameters. A call fills those holes with expressions:

```text
max of 7 and 3
```

Phrase names are generated from the leading literal words in a phrase definition. There is no overloading, so generated phrase names must be unique.

## Body items and value blocks

A phrase body is:

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
if condition:
  step
otherwise:
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
- A body item may not appear after the value block starts.
- A block with one unconditional expression evaluates to that expression.
- A block with `when` lines must end with exactly one `otherwise` line.
- `if condition:` is a step-level block, not a value block.
- There is no statement-level `return`.

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
- v0.2 supports nested `while` loops.
- A while body may contain lets, tracks, assignments, nested whiles, and if/otherwise blocks.
- Let and track bindings declared inside a while body are scoped to that loop iteration and do not escape.
- A track declared inside a loop body is initialized on each iteration.
- Tracked bindings declared before a while and assigned anywhere inside it, including in nested loops or branches, are loop-carried values.
- Tracked bindings declared inside the while body are not carried by that outer while, but can be carried by nested loops inside that body.

Lowering uses `scf.while` with deterministic loop-carried operands ordered by original visible `track` declaration order. The before region evaluates the condition and forwards current carried values through `scf.condition`; the after region emits body steps and yields final carried values through `scf.yield`.

## Step-level if/otherwise blocks

An if block is a step-level control-flow item:

```text
if condition:
  step
otherwise:
  step
```

Rules:

- The condition must type-check as `i1`.
- `otherwise` is required.
- Both branches must contain at least one step.
- Branches may contain lets, tracks, assignments, nested whiles, and nested if/otherwise blocks.
- Let and track bindings declared inside a branch do not escape that branch.
- Any tracked binding assigned in either branch is yielded from an `scf.if` result.
- If a tracked binding is assigned in one branch but not the other, the unassigned branch yields its pre-if value.
- Multiple tracked results are yielded in visible track declaration order.

Example:

```text
absolute using branch of n: i32 gives i32:
  track result: i32 from 0
  if n is less than zero:
    result becomes zero minus n
  otherwise:
    result becomes n
  result
```

## Expressions

Expressions are deterministic and statically typed:

- integer literal: `120`
- zero literal: `zero`
- boolean literal: `true`, `false`
- variable reference: `result`
- phrase call: `max of 7 and 3`
- unary boolean: `not value`
- binary arithmetic: `plus`, `minus`, `times`, `divided by`, `remainder`
- binary boolean: `and`, `or`
- parenthesized expression: `(a plus b) times 2`
- comparison expression: `x is equal to 0`

Precedence, strongest to weakest:

1. parenthesized expressions, phrase calls, literals, and names
2. unary `not`
3. `times`, `divided by`, `remainder`
4. `plus`, `minus`
5. comparisons
6. `and`
7. `or`

Arithmetic and boolean binary operators are left-associative. Boolean `and` and `or` are strict expression operators; v0.2 has no short-circuit semantics.

Comparisons return `i1`:

- `left is equal to right`
- `left is not equal to right`
- `left is less than right`
- `left is less than or equal to right`
- `left is greater than right`
- `left is greater than or equal to right`

## Semantic rules

- Generated phrase names are unique; there is no overloading.
- Parameter names are unique.
- Calls must match a known phrase template.
- Variables must be initialized by a phrase hole, prior `let`, or visible `track` before use.
- If `main` exists, it must take no holes.
- Types are exactly `i1`, `i32`, and `i64`.
- Phrase holes are immutable.
- `let` bindings are immutable.
- Assignment is valid only for tracked bindings.
- Track and let bindings may not shadow visible overlapping bindings.
- A binding name may be reused only after the previous lexical scope has ended.
- Track initializers must match their declared type.
- Assignment right-hand sides must match the tracked binding's declared type.
- While and if conditions must be `i1`.
- Branch-local and loop-local lets/tracks do not escape.
- Arithmetic requires matching numeric operand types (`i32` or `i64`).
- `remainder` requires matching numeric operands and lowers to signed `arith.remsi`.
- Comparisons require matching numeric operand types and return `i1`.
- `and`, `or`, and `not` require `i1` operands and return `i1`.
- Integer literals are coerced to the numeric type required by context when possible.
- Conditional value blocks require `otherwise` and lower through `scf.if` results.
- Unsupported `Function`, `End function`, `Set`, `Return`, `call ... with`, I/O, arrays, floats, pointers, memrefs, structs, proof prose, natural-language requests, custom dialect syntax, `break`, and `continue` are rejected.

## MLIR subset

The v0.2 emitter uses only:

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
arith.andi
arith.ori
arith.xori
arith.cmpi
scf.if
scf.while
scf.condition
scf.yield
```

No memory or storage lowering is permitted: no `memref`, `alloca`, globals, heap objects, stack slots, mutable storage dialects, or source-level state outside SSA values.

## Golden conformance suite

The minimum v0.2 quality bar is the exact-output golden suite in `tests/goldens`. Each `*.ins` source file must compile byte-for-byte to its sibling `*.mlir`; the unit test suite enforces this with unified diffs on mismatch.
