# Inscription v0.42 owned buffer literal and copy initialization

Inscription v0.42 makes heap-backed owned data easier to construct while preserving explicit ownership. It adds owned-buffer `containing` initialization, byte-string owned buffers, and explicit copy initialization from existing storage.

New behavior:

- Local owned buffers may be initialized with explicit elements:
  `Let cells be owned buffer of 4 i32 containing 1, 2, 3, 4.`
- Mutable owned `u8` buffers may be initialized directly from non-empty byte strings:
  `Let bytes be owned buffer of bytes "hello".`
- A fresh owned buffer may be copied explicitly from a fixed buffer, array, view, or owned buffer:
  `Let copy be owned buffer copied from source.`
- Byte-string splices such as `bytes "hello"` may appear in `containing` lists for owned `u8` buffers.
- Copying an owned buffer is explicit and non-consuming; `move` remains the only ownership transfer syntax.

No owned buffer constants, implicit copies, zero-length owned buffers, resizing, heap strings, manual deallocation, pointer/reference types, owned fields, extern/export ABI changes, or custom MLIR dialects are added.

## Owned buffer `containing`

The new local binding form is:

```inscription
Let cells be owned buffer of 4 i32 containing 1, 2, 3, 4.
```

The length follows the existing owned-buffer length rules and must be an integer numeric value of at least one. The element type may be an integer numeric type, `f32`, `f64`, or an enum type. It may not be `i1`, record, layout record, union, buffer, array, view, or owned buffer.

The expanded element count must exactly equal the declared length, and each element must type-check as the element type. Integer, float, and byte literals use the element type as their expected type. The resulting binding is a normal mutable owned buffer with lexical cleanup, move, return, and consuming-parameter behavior.

Diagnostics include:

```text
owned buffer cells expects 4 elements, got 3
owned buffer cells element 1 must have type i32, got i1
owned buffer element type may not be a union type in v0.42
```

## Owned byte-string buffers

The new byte-string form is:

```inscription
Let bytes be owned buffer of bytes "hello".
```

It decodes the string with the existing byte-string decoder and creates a mutable owned `u8` buffer whose length is the decoded byte count. No null terminator is added. The decoded length must be at least one:

```text
owned byte buffer literal must contain at least one byte
```

This is byte storage, not a string type, pointer, global, or constant.

## Byte-string splices in owned `containing`

Owned `u8` buffers can splice byte strings into an element list:

```inscription
Let bytes be owned buffer of 5 u8 containing bytes "hello".
Let mixed be owned buffer of 4 u8 containing byte "A", bytes "BC", byte "D".
```

Splices are valid only when the owned buffer element type resolves to `u8`:

```text
byte string literal can only initialize u8 arrays, buffers, or owned buffers, got i32
```

## Explicit owned-buffer copy initialization

The new copy form is:

```inscription
Let copy be owned buffer copied from source.
```

`source` must name a visible live fixed buffer, immutable array, view, or owned buffer. The copy gets a fresh dynamic owned allocation, the same element type, and `length of source`. The source is not consumed and remains usable after the copy. The new binding is mutable even when the source is an immutable array or read-only view.

```inscription
To copy array, giving i32.
Let numbers be array of 4 i32 containing 1, 2, 3, 4.
Let copy be owned buffer copied from numbers.
copy at 0 becomes 10.
Give copy at 0 plus numbers at 0.
```

Copy sources must have owned-buffer-compatible element types. Static zero-length sources are rejected. Dynamic zero-length sources are undefined behavior unless runtime checks are enabled; with `--runtime-checks`, the compiler emits a check that the source length is at least one before allocating.

Diagnostics include:

```text
owned buffer copy source value must be buffer, array, view, or owned buffer, got i32
owned buffer copy source must have length at least 1
owned buffer cells was moved and cannot be used
owned buffer copy source must be a storage binding
```

## Lowering

Owned `containing` and owned byte-string bindings allocate the normal dynamic `memref<?xT>` representation and emit deterministic stores for each element in index order. They do not use a fill loop.

`owned buffer copied from source` computes the source length, allocates a fresh destination memref, and emits an element-wise loop from `0` to `length of source`. The destination has a distinct root storage identity from the source.

## Formatter and highlighter

The canonical formatter preserves:

```inscription
Let cells be owned buffer of 4 i32 containing 1, 2, 3, 4.
Let bytes be owned buffer of bytes "hello".
Let copy be owned buffer copied from source.
```

The highlighter recognizes `copied` along with the existing `owned`, `buffer`, `containing`, `bytes`, and `from` words.
