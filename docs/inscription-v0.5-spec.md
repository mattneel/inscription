# Inscription v0.5 specification

Inscription v0.5 is a deterministic, phrase-shaped compiler. It keeps the v0.4 scalar, control-flow, cast, and local-buffer surface, and adds fixed-size buffer parameters plus side-effect-only `does` phrases.

## Execution model

- A program is a list of phrase definitions.
- A phrase definition is either a `gives` phrase, which returns a scalar value, or a `does` phrase, which returns no value.
- Source-visible scalar types are `i1`, signed integers `i8`/`i16`/`i32`/`i64`, and unsigned integers `u8`/`u16`/`u32`/`u64`.
- Source-visible buffer parameter types are written `buffer of LENGTH TYPE`, where `LENGTH` is a positive decimal integer literal and `TYPE` is an integer numeric scalar type, not `i1`.
- All source integer types lower to MLIR signless integers of the same width; source signedness selects division, remainder, ordered comparison, widening cast, dynamic index conversion, and right-shift operations.
- Local fixed-size buffers lower to stack-local `memref.alloca`; buffer parameters lower to memref function arguments.
- v0.5 has no heap allocation, pointer syntax, buffer return values, buffer aliasing, slices, dynamic-size buffers, structs, floats, strings, I/O, source-level `return`, `break`, `continue`, overloading, inference, or custom dialects.

## Phrase definitions

A `gives` phrase ends with a value block and returns a scalar:

```text
sum buffer cells: buffer of 4 i32 gives i32:
  let total be 0
  let i be 0
  while i is less than 4:
    total becomes total plus cells at i
    i becomes i plus 1
  total
```

A `does` phrase contains only steps and returns no value:

```text
fill buffer cells: buffer of 4 i32 with value: i32 does:
  let i be 0
  while i is less than 4:
    cells at i becomes value
    i becomes i plus 1
```

There is no `void`, `unit`, or `nothing` source type.

## Buffer parameters

Buffer holes use fixed-size buffer types:

```text
cells: buffer of 4 i32
bytes: buffer of 4 u8
```

Rules:

- Length must be at least `1`.
- Element type must be `i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, or `u64`.
- `i1` buffer parameters are not supported.
- Actual buffer arguments must exactly match length and element type.
- There are no implicit buffer casts, dynamic-size buffers, slices, or buffer return values.
- A buffer parameter is visible for the duration of the phrase body.
- Buffer parameters cannot be rebound with `becomes`, returned, stored in scalar bindings, or used as scalar values.
- Buffer parameters can be indexed with `name at index` and passed to other phrase calls subject to effect and alias rules.

## Effects and phrase calls

`gives` phrases may accept buffer parameters, but those buffer parameters are read-only inside the `gives` phrase. Loads are allowed; stores are rejected. Local buffers declared inside a `gives` phrase remain writable.

`does` phrases may accept scalar and buffer parameters. Buffer parameters in `does` phrases are writable. `does` phrases may load from and store to buffers, declare local scalars and local buffers, use `while` and `if`/`otherwise`, call other `does` phrases as steps, and call `gives` phrases in scalar expression positions.

Standalone phrase calls are body items only when the call resolves to a `does` phrase:

```text
main gives i32:
  let cells be buffer of 4 i32 filled with 0
  fill buffer cells with 7
  sum buffer cells
```

A `gives` phrase call used as a standalone step is invalid. A `does` phrase call used as an expression is invalid.

A read-only buffer parameter cannot be passed to an effectful `does` phrase. Writable local buffers and writable `does` buffer parameters can be passed to `does` phrases. Read-only or writable buffers can be passed to `gives` phrases.

## Alias rule

If a phrase call passes more than one buffer argument, all buffer actuals must refer to distinct visible buffer bindings. Passing the same buffer to multiple buffer holes in one call is rejected. v0.5 performs no alias analysis beyond this syntactic rule.

## Local buffers

Local buffers retain v0.4 syntax:

```text
let bytes be buffer of 4 u8 filled with 0
bytes at 0 becomes 255
let byte be bytes at 0
```

Literal indices are checked at compile time. Dynamic indices are not runtime-checked; dynamic out-of-bounds access is undefined behavior in v0.5.

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

## MLIR lowering

The emitter uses only standard dialects:

```text
builtin.module
func
arith
scf
memref
```

A `gives` phrase with a buffer parameter lowers to a memref argument and scalar result:

```mlir
func.func @sum_buffer(%cells: memref<4xi32>) -> i32 {
  ...
  %value = memref.load %cells[%idx] : memref<4xi32>
  ...
  return %result : i32
}
```

A `does` phrase lowers to a function with no result:

```mlir
func.func @fill_buffer(%cells: memref<4xi32>, %value: i32) {
  ...
  memref.store %value, %cells[%idx] : memref<4xi32>
  return
}
```

A `does` call lowers as:

```mlir
func.call @fill_buffer(%cells, %value) : (memref<4xi32>, i32) -> ()
```

The v0.4 memref-capable LLVM lowering pipeline remains valid:

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

The minimum v0.5 quality bar is the exact-output golden suite in `tests/goldens`. Each `*.ins` source file must compile byte-for-byte to its sibling `*.mlir`; the unit test suite enforces this with unified diffs on mismatch.
