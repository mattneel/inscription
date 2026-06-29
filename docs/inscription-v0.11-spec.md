# Inscription v0.11 specification

Inscription v0.11 keeps the v0.10 scalar, control-flow, buffer, record, layout-record, serialization, constants/checks, and module/import surface and adds borrowed buffer views.

## Borrowed views

A view is a non-owning range over existing contiguous buffer storage:

```text
let window be view of cells from start for count
```

Rules:

- The source must be a visible buffer or view.
- `start` and `count` must have type `i32`.
- A view's element type is the source element type.
- A view inherits writability from its source.
- A view from a read-only source is read-only.
- A view from a writable source is writable.
- The count may be zero.
- If start/count are compile-time evaluable, the compiler rejects negative starts, negative counts, and ranges that exceed a statically known source length.
- Dynamic out-of-range view creation is undefined behavior in v0.11; no runtime checks are emitted.
- Views are scoped local bindings or phrase parameters. They cannot be rebound, returned, stored in buffers, placed in records, heap allocated, or used as scalar values.

Internally a view is represented as base memref, start `i32`, length `i32`, element type, writability, optional static length, and root storage identity for conservative alias diagnostics.

## View loads, stores, and length

The existing indexing syntax works for buffers and views:

```text
window at i
window at i becomes value
length of window
```

Rules:

- View loads read from `view.start + index`.
- View stores write to `view.start + index` and require a writable view.
- The index must be an integer numeric type, not `i1`.
- Store values must exactly match the view element type.
- If a view's length is statically known and the index is compile-time evaluable, out-of-bounds indices are rejected.
- Dynamic out-of-bounds view loads/stores are undefined behavior in v0.11.
- `length of view` returns `i32`; it is compile-time evaluable only when the view length is statically known.

## View parameters

A phrase hole may accept a view:

```text
sum view cells: view of i32 gives i32:
  let total be 0
  for each index i of cells:
    total becomes total plus cells at i
  total

fill view cells: view of i32 with value: i32 does:
  for each index i of cells:
    cells at i becomes value
```

Rules:

- View element types may be `i8/i16/i32/i64` or `u8/u16/u32/u64`; `i1` views are not supported.
- `gives` phrase view parameters are read-only.
- `does` phrase view parameters are writable.
- A buffer may be passed where `view of TYPE` is expected; this creates an implicit full-buffer view at the call boundary.
- A view may be passed where `view of TYPE` is expected.
- Element types must match exactly; no casts are inserted.
- Read-only views cannot be passed to effectful `does` phrase view parameters.

## For-each loops over views

`for each index i of name:` accepts either a buffer or a view. For views it iterates from `0` up to `length of view`, with a read-only `i32` index binding scoped to the loop body.

## Layout serialization through views

Layout record serialization works through `u8` buffers or `view of u8`:

```text
let word be read Word from bytes_view at 0
write word into bytes_view at 0
```

Rules:

- Layout reads require a `u8` buffer or `view of u8`.
- Layout writes require a writable `u8` buffer or writable `view of u8`.
- Static layout bounds checks use the view length when it is statically known.
- Dynamic layout read/write bounds remain unchecked in v0.11.
- Little-endian field encoding and zeroed padding bytes are unchanged from v0.8.

## Conservative alias rule

For any phrase call, if multiple buffer/view arguments are passed and the compiler can prove they share the same root storage, the call is rejected. This rejects passing the same buffer twice, the same view twice, a buffer and a view derived from it, or two views derived from the same root buffer, even when their ranges are statically disjoint.

## MLIR lowering

The emitter still uses only standard dialects:

```text
builtin.module
func
arith
scf
memref
```

A view parameter lowers to three operands:

```mlir
memref<?xT>, i32, i32
```

representing base, start, and length. Passing a fixed-size buffer to a view parameter emits `memref.cast` to the corresponding dynamic memref plus constants for start 0 and the static buffer length. View loads/stores convert start and index to `index`, add them, and use `memref.load`/`memref.store` on the base memref.

No heap allocation, pointers, references, address-of, view returns, view fields, buffers of views, runtime bounds checks, aliases beyond conservative same-root rejection, generics, macros, source-level I/O, `return`, `break`, `continue`, overloading, implicit scalar casts, or custom dialects are added in v0.11.

## Golden conformance suite

The minimum v0.11 quality bar is the exact-output golden suite in `tests/goldens`; existing v0 through v0.10 goldens remain byte-for-byte stable.
