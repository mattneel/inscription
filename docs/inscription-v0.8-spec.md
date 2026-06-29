# Inscription v0.8 specification

Inscription v0.8 keeps the v0.7 scalar, control-flow, buffer, `does` phrase, counted-loop, and value-record surface, and adds layout-aware records plus explicit byte-buffer serialization.

## Execution model

- A program is a list of top-level `record`, `layout record`, `packed layout record`, and phrase definitions.
- Ordinary `record` declarations remain value-only records with no byte layout.
- Layout records are still value records in expression, control-flow, and function-call contexts. They lower by flattening fields to scalar SSA values and function operands, just like v0.7 records.
- Layout metadata is used only by `size of TypeName`, `alignment of TypeName`, `offset of field in TypeName`, `read TypeName from buffer at index`, and `write value into buffer at index`.
- v0.8 does not lower records to LLVM struct types and does not add pointers, address-of, references, record buffers, record returns, heap allocation, or runtime bounds checks.

## Layout record declarations

Natural layout records are declared with:

```text
layout record Header:
  tag: u8
  length: u16
  flags: u8
```

Packed layout records are declared with:

```text
packed layout record PackedHeader:
  tag: u8
  length: u16
  flags: u8
```

Rules:

- Record names and layout record names share one nominal type namespace.
- A layout record name must not collide with scalar type names or any other record name.
- A layout record must declare at least one field.
- Field names within a layout record must be unique.
- Layout record fields may only be integer scalar types: `i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, or `u64`.
- `i1`, buffer fields, record fields, nested records, dynamic fields, methods, and layout attributes beyond `layout record` and `packed layout record` are not supported.

## Layout algorithm

Scalar field sizes and alignments are:

```text
i8/u8   size 1, alignment 1
i16/u16 size 2, alignment 2
i32/u32 size 4, alignment 4
i64/u64 size 8, alignment 8
```

For natural `layout record` declarations:

1. Start offset at 0.
2. For each field in declaration order, round the current offset up to that field's alignment.
3. Assign that field offset.
4. Advance by the field size.
5. The record alignment is the maximum field alignment.
6. The record size is the final offset rounded up to the record alignment.

For `packed layout record` declarations:

- Field offsets are consecutive byte offsets.
- Alignment is 1.
- Size is the sum of field byte widths.

The physical layout is deterministic and Inscription-defined. It is not the platform C ABI.

## Ordinary record behavior

Layout records use the v0.7 record constructor, local binding, field access, field rebinding, whole-record rebinding, phrase parameter, and control-flow carrying rules:

```text
layout record Header:
  tag: u8
  length: u16
  flags: u8

main gives i32:
  let h be Header with tag be 7 and length be 9 and flags be 3
  h.tag as i32 plus h.length as i32 plus h.flags as i32
```

Layout record parameters are passed by value and flattened into scalar function operands. Rebinding a field of a layout record parameter is local to the callee. Layout records still cannot be returned or used as buffer element types.

## Layout introspection

Layout introspection expressions are compile-time `i32` constants:

```text
size of Header
alignment of Header
offset of flags in Header
```

Rules:

- The type name must refer to a `layout record` or `packed layout record`.
- These expressions are invalid for ordinary value-only `record` declarations.
- Each lowers to `arith.constant VALUE : i32`.

Example:

```text
layout record Header:
  tag: u8
  length: u16
  flags: u8

main gives i32:
  size of Header plus alignment of Header plus offset of flags in Header
```

The result is `6 + 2 + 4 = 12`.

## Reading layout records from u8 buffers

A layout read expression reconstructs a record value from bytes:

```text
let header be read Header from bytes at 0
let word be read Word from bytes at i
```

Rules:

- `TypeName` must refer to a layout record.
- The buffer must be a visible buffer binding or buffer parameter with element type `u8`.
- The index expression must be an integer numeric type, not `i1`.
- Static literal indices are checked at compile time: `index + size of TypeName` must fit within the buffer length.
- Dynamic indices are not runtime-checked in v0.8; dynamic out-of-bounds layout reads are undefined behavior.
- Multi-byte integer fields are decoded little-endian.
- Signed integer fields are reconstructed with the same bit pattern and interpreted according to source signedness.

Lowering uses `memref.load` of `u8` bytes, `arith.extui`, shifts, and `arith.ori`. No aggregate MLIR record value is emitted.

## Writing layout records to u8 buffers

A layout write step serializes a visible layout record value into bytes:

```text
write header into bytes at 0
write word into bytes at i
```

Rules:

- The source name must resolve to a visible layout record binding or parameter.
- Ordinary value-only records cannot be written.
- The target buffer must have element type `u8` and must be writable.
- Buffer parameters in `gives` phrases are read-only and cannot be layout-write targets.
- The index expression must be an integer numeric type, not `i1`.
- Static literal indices are checked at compile time: `index + size of record_type` must fit within the buffer length.
- Dynamic indices are not runtime-checked in v0.8; dynamic out-of-bounds layout writes are undefined behavior.
- Multi-byte integer fields are encoded little-endian.
- Padding bytes are written as zero.

Lowering uses logical right shift (`arith.shrui`) for byte extraction, `arith.trunci` to `i8`, and deterministic `memref.store` operations in byte-offset order.

## Body items and value blocks

A `gives` body remains:

```text
body_item*
value_block
```

A `does` body remains:

```text
body_item+
```

Body items are extended with layout writes:

```text
let name be expression
let name: type be expression
let name be buffer of LENGTH TYPE filled with expression
name becomes expression
name.field becomes expression
name at index becomes expression
write record_name into buffer_name at index
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

Value blocks remain scalar:

```text
expression
expression when condition
otherwise expression
```

Record return types are not supported in v0.8.

## MLIR lowering

The emitter uses only standard dialects:

```text
builtin.module
func
arith
scf
memref
```

Layout records produce no record-specific MLIR operation. Constructor and field access are compiler-environment operations over scalar SSA values. Layout reads and writes are explicit byte loads/stores on `memref<Nxi8>` buffers. The v0.7 memref-capable LLVM lowering pipeline remains valid.

## Golden conformance suite

The minimum v0.8 quality bar is the exact-output golden suite in `tests/goldens`. Each `*.ins` source file must compile byte-for-byte to its sibling `*.mlir`; the unit test suite enforces this with unified diffs on mismatch.
