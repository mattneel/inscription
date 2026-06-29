# Inscription v0.9 specification

Inscription v0.9 keeps the v0.8 scalar, control-flow, buffer, phrase, record, layout-record, and byte-serialization surface and adds compile-time scalar constants, compile-time checks, and compile-time expressions for buffer lengths.

## Execution model

- A program is a list of top-level constants, checks, record declarations, layout record declarations, packed layout record declarations, and phrase definitions.
- Constants are compile-time scalar values. They emit no globals and lower as ordinary `arith.constant` operations at each use site.
- Checks are compile-time assertions. Passing checks emit no MLIR; failing checks stop compilation.
- Buffer lengths are still fixed at compile time, but may now be decimal literals, constant names, or parenthesized compile-time integer expressions.
- v0.9 does not add macros, imports, generics, type aliases, global storage, runtime assertions, dynamic buffers, heap allocation, pointers, references, strings, floats, source-level `return`, `break`, `continue`, overloading, inference, implicit casts, or a custom dialect.

## Top-level constants

Constants are declared with:

```text
constant name: type be expression
```

Examples:

```text
constant header_size: i32 be size of Header
constant byte_count: i32 be 8
constant mask: u8 be 240
constant low_mask: u8 be bitwise not mask
constant header_is_six: i1 be size of Header is equal to 6
```

Rules:

- Constant names are unique and cannot collide with scalar type names or record/layout-record names.
- Constants may have only scalar types: `i1`, signed integers `i8`/`i16`/`i32`/`i64`, or unsigned integers `u8`/`u16`/`u32`/`u64`.
- Constants are evaluated in source order after record and layout-record declarations are collected.
- A constant may refer only to constants declared earlier in the file.
- A constant initializer must be compile-time evaluable and must type-check exactly as the declared type.
- Constants are visible in phrase bodies as immutable scalar bindings.
- Local bindings and phrase holes may not shadow constants.
- Constants cannot be rebound with `becomes`, passed where buffers or records are expected, or used as assignment targets.

A use of a constant emits an inline MLIR constant at the use site; no global storage is introduced.

## Compile-time checks

Checks are written as:

```text
check expression
```

They may appear at top level or as a step inside `gives` and `does` bodies.

Rules:

- The check expression must type-check as `i1`.
- The check expression must be compile-time evaluable.
- A true check emits no MLIR.
- A false check is a deterministic compile-time error.
- Phrase-body checks may refer to top-level constants, layout introspection expressions, `length of` visible statically sized buffers, and literal scalar expressions.
- Phrase-body checks may not depend on runtime phrase holes, runtime lets, record fields, or buffer element loads.
- `check` is a step, not an expression, and does not satisfy a `gives` value block.

Example:

```text
layout record Header:
  tag: u8
  length: u16
  flags: u8

check size of Header is equal to 6

parse header bytes: buffer of (size of Header) u8 gives i32:
  check length of bytes is equal to size of Header
  length of bytes
```

## Compile-time expression subset

The compile-time evaluator supports scalar expressions over:

- integer literals, `zero`, `true`, and `false`
- earlier top-level constants
- `size of TypeName`, `alignment of TypeName`, and `offset of field in TypeName`
- `length of buffer` for visible fixed-size buffers or buffer parameters
- parentheses and casts with `as`
- arithmetic: `plus`, `minus`, `times`, `divided by`, and `remainder`
- comparisons
- boolean `and`, `or`, and `not`
- bitwise `bitwise and`, `bitwise or`, `bitwise xor`, and `bitwise not`
- shifts: `shifted left by` and `shifted right by`

Compile-time evaluation uses the same source typing rules as runtime expressions. Integer operations use fixed-width source-type semantics. Casts match runtime casts. Signed and unsigned comparisons use source signedness. Compile-time division or remainder by zero is rejected. Compile-time shift amounts must be in range for the source width. Boolean `and` and `or` remain strict.

## Compile-time buffer lengths

Buffer lengths may be:

```text
buffer of 4 i32
buffer of cell_count i32
buffer of (size of Header) u8
buffer of (size of Header plus 2) u8
```

Rules:

- A buffer length expression must be compile-time evaluable.
- The evaluated length must be an integer numeric type, not `i1`.
- The evaluated length must be at least 1.
- Buffer type identity is based on the evaluated length and element type, not spelling.
- `buffer of 4 i32`, `buffer of cell_count i32` where `cell_count` is 4, and `buffer of (2 plus 2) i32` are the same buffer type.

Static layout read/write bounds checks now use any compile-time evaluable index expression. Dynamic indices remain unchecked at runtime.

## MLIR lowering

The emitter uses only standard dialects:

```text
builtin.module
func
arith
scf
memref
```

Constants and layout/length introspection lower to `arith.constant` operations at use sites. Checks emit no operations. Buffer length expressions are evaluated before MLIR emission and used in `memref<NxT>` types. The v0.8 LLVM/MLIR lowering pipeline remains valid.

## Golden conformance suite

The minimum v0.9 quality bar is the exact-output golden suite in `tests/goldens`. Each `*.ins` source file must compile byte-for-byte to its sibling `*.mlir`; the unit test suite enforces this with unified diffs on mismatch.
