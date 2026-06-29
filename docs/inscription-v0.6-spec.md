# Inscription v0.6 specification

Inscription v0.6 is a deterministic, phrase-shaped compiler. It keeps the v0.5 scalar, control-flow, cast, local-buffer, buffer-parameter, and `does` phrase surface, and adds static buffer length expressions plus ergonomic counted iteration.

## Execution model

- A program is a list of phrase definitions.
- A phrase definition is either a `gives` phrase, which returns a scalar value, or a `does` phrase, which returns no value.
- Source-visible scalar types are `i1`, signed integers `i8`/`i16`/`i32`/`i64`, and unsigned integers `u8`/`u16`/`u32`/`u64`.
- Source-visible buffer parameter types are written `buffer of LENGTH TYPE`, where `LENGTH` is a positive decimal integer literal and `TYPE` is an integer numeric scalar type, not `i1`.
- All source integer types lower to MLIR signless integers of the same width; source signedness selects division, remainder, ordered comparison, widening cast, dynamic index conversion, and right-shift operations.
- Local fixed-size buffers lower to stack-local `memref.alloca`; buffer parameters lower to memref function arguments.
- Scalar rebinding lowers to SSA values, `scf.if` results, `scf.while` carried values, or `scf.for` iter_args.
- v0.6 has no heap allocation, pointer syntax, buffer return values, buffer aliasing beyond the v0.5 duplicate-argument check, slices, dynamic-size buffers, structs, floats, strings, I/O, source-level `return`, `break`, `continue`, overloading, inference, source-visible `index` type, or custom dialects.

## Buffer length

`length of buffer_name` is an expression:

```text
size of cells: buffer of 4 i32 gives i32:
  length of cells
```

Rules:

- `buffer_name` must resolve to a visible local buffer or buffer parameter.
- The result type is `i32`.
- The value is a compile-time constant equal to the buffer's static length.
- v0.6 emits `arith.constant LENGTH : i32`; it does not emit `memref.dim`.

## Counted loops

A counted loop iterates from an inclusive start to an exclusive end:

```text
for i from 0 up to 10:
  step
```

An explicit positive literal step can be supplied:

```text
for i from 0 up to 10 by 2:
  step
```

Rules:

- The loop iterates while the index is less than the end expression.
- Start and end expressions are evaluated once before the loop.
- Start and end must have the same integer numeric source type, not `i1`.
- The loop index has the same source type as the start and end expressions.
- The loop index is visible only inside the loop body.
- The loop index is read-only and cannot be rebound with `becomes`.
- The loop index cannot shadow any visible binding.
- The body must contain at least one step.
- Let and buffer bindings declared in the body are scoped to that iteration and do not escape.
- Assignments to scalar bindings declared outside the loop are reflected after the loop through loop-carried SSA values.
- Stores to visible buffers mutate memref-backed buffer storage.
- There is no `break` or `continue`.

Example:

```text
sum evens gives i32:
  let total be 0
  for i from 0 up to 10 by 2:
    total becomes total plus i
  total
```

## Buffer index loops

A buffer index loop iterates over valid static indices of a visible buffer:

```text
for each index i of cells:
  total becomes total plus cells at i
```

Rules:

- The buffer name must resolve to a visible local buffer or buffer parameter.
- The loop iterates from `0` up to the buffer's static length.
- The index binding has source type `i32`.
- The index binding is visible only inside the loop body.
- The index binding is read-only and cannot shadow any visible binding.
- The loop body must contain at least one step.

Example:

```text
fill each cells: buffer of 4 i32 with value: i32 does:
  for each index i of cells:
    cells at i becomes value
```

## Body items and value blocks

A `gives` body is:

```text
body_item*
value_block
```

A `does` body is:

```text
body_item+
```

Body items are:

```text
let name be expression
let name: type be expression
let name be buffer of LENGTH TYPE filled with expression
name becomes expression
name at index becomes expression
does_phrase_call
while condition:
  step
for name from start up to end:
  step
for name from start up to end by STEP:
  step
for each index name of buffer:
  step
if condition:
  step
otherwise:
  step
```

Value blocks remain:

```text
expression
expression when condition
otherwise expression
```

## Buffer parameters and effects

Buffer parameters keep the v0.5 rules:

- `gives` phrase buffer parameters are read-only.
- `does` phrase buffer parameters are writable.
- Local buffers declared inside any phrase are writable.
- A read-only buffer parameter cannot be passed to an effectful `does` phrase.
- A phrase call that passes multiple buffer arguments must pass distinct visible buffer bindings.
- Buffer parameters cannot be rebound, returned, stored in scalar bindings, or used as scalar values.

## Local buffers

Local buffers retain v0.4 syntax:

```text
let bytes be buffer of 4 u8 filled with 0
bytes at 0 becomes 255
let byte be bytes at 0
```

Literal indices are checked at compile time. Dynamic indices are not runtime-checked; dynamic out-of-bounds access is undefined behavior in v0.6.

## MLIR lowering

The emitter uses only standard dialects:

```text
builtin.module
func
arith
scf
memref
```

`length of buffer` lowers to a scalar constant:

```mlir
%size = arith.constant 4 : i32
```

Counted loops and buffer index loops lower to `scf.for`. Scalar bindings assigned inside a loop and declared outside the loop are carried with `iter_args` in deterministic binding order. Buffer contents are mutated through `memref.store` and are not SSA-carried.

A counted loop shape is:

```mlir
%result = scf.for %iv = %start to %end step %step iter_args(%total_iter = %total) -> (i32) {
  %i = arith.index_cast %iv : index to i32
  ...
  scf.yield %updated : i32
}
```

The memref-capable LLVM lowering pipeline remains valid:

```text
--convert-scf-to-cf
--convert-cf-to-llvm
--convert-arith-to-llvm
--expand-strided-metadata
--finalize-memref-to-llvm
--convert-func-to-llvm
--reconcile-unrealized-casts
```

## Golden conformance suite

The minimum v0.6 quality bar is the exact-output golden suite in `tests/goldens`. Each `*.ins` source file must compile byte-for-byte to its sibling `*.mlir`; the unit test suite enforces this with unified diffs on mismatch.
