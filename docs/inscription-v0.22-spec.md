# Inscription v0.22 fixed-size arrays and literal initialization specification

Inscription v0.22 keeps the v0.21 language and tooling surface and adds immutable local fixed-size arrays plus literal initialization for both buffers and arrays.

This is a source-language sprint. Existing programs, source MLIR goldens, modules, records, buffers, views, externs, exports, artifacts, interface JSON, and C headers remain compatible with v0.21 unless they opt into `array` or `containing` syntax.

## Buffers with literal contents

Existing filled buffers remain valid:

```text
let cells be buffer of 4 i32 filled with 0
```

v0.22 also accepts literal initialization:

```text
let cells be buffer of 4 i32 containing 1, 2, 3, 4
let weights be buffer of 3 f64 containing 0.25, 0.5, 0.25
```

Rules:

- `LENGTH` uses the existing compile-time buffer length rules: integer literal, top-level integer constant name, or parenthesized compile-time integer expression.
- The element type may be any current buffer element type: integer numeric types, `f32`, or `f64`; `i1` remains unsupported.
- `containing` must provide exactly `LENGTH` expressions.
- Each element is checked with the buffer element type as the expected type.
- No implicit casts are introduced.
- The resulting binding is a normal mutable buffer.
- Lowering allocates the same local memref as a filled buffer and emits deterministic stores in index order.

## Immutable local arrays

Arrays are immutable fixed-size local storage:

```text
let numbers be array of 4 i32 containing 1, 2, 3, 4
let zeros be array of 8 i32 filled with 0
let weights be array of 3 f64 containing 0.25, 0.5, 0.25
```

Rules:

- `LENGTH` uses the existing compile-time buffer length rules.
- Array element types may be integer numeric types, `f32`, or `f64`.
- `i1`, record, buffer, view, and array element types are not supported.
- `containing` requires exactly `LENGTH` elements.
- `filled with` initializes every element to the same value.
- Element expressions must match the element type exactly.
- Arrays are lexical local bindings and do not escape branch or loop scope.
- Arrays cannot be rebound with `becomes`.
- Array elements cannot be assigned with `array at index becomes ...`.
- Arrays cannot be used as scalar or record values.
- Arrays cannot be phrase parameters, return values, or `let` type annotations in v0.22.
- Arrays cannot be passed where a buffer parameter is expected.
- Arrays can be passed where a `view of TYPE` parameter is expected as a full read-only view.
- Arrays can be the source of a local view.

Arrays lower to local memref storage (`memref.alloca`, deterministic initialization stores, and `memref.load`). Immutability is enforced by semantic checks; v0.22 does not add special read-only MLIR storage.

## Array loads, length, and iteration

Array elements are read with the existing index syntax:

```text
numbers at 2
```

Rules:

- The index expression must be an integer numeric type, not `i1` and not a float.
- Compile-time index expressions are statically bounds-checked.
- Dynamic indices remain unchecked by default.
- `--runtime-checks` emits runtime assertions for dynamic array loads.

`length of array` returns an `i32` constant and is compile-time evaluable:

```text
length of numbers
```

`for each index` works over arrays:

```text
for each index i of numbers:
  total becomes total plus numbers at i
```

The loop index has type `i32` and is read-only/scoped like existing buffer and view index loops.

## Views over arrays

Views may borrow from buffers, arrays, or other views:

```text
let middle be view of numbers from 2 for 3
```

Rules:

- A view from an array is read-only.
- A view from a read-only source remains read-only.
- A view from a writable buffer/view remains writable.
- Existing static view range checks apply.
- `--runtime-checks` emits runtime assertions for dynamic views created from arrays.
- Same-root alias diagnostics treat arrays as root storage like buffers.

Arrays can be passed to `gives` view parameters:

```text
sum view cells: view of i32 gives i32:
  ...

main gives i32:
  let numbers be array of 4 i32 containing 3, 3, 3, 3
  sum view numbers
```

An array or array-derived view cannot be passed to an effectful `does` view parameter because it is read-only.

## Layout reads from arrays

Layout read sources may now be `u8` buffers, `view of u8`, or `u8` arrays:

```text
let bytes be array of 2 u8 containing 42, 0
let word be read Word from bytes at 0
```

Writing into arrays is invalid:

```text
write word into bytes at 0
```

for an array binding `bytes` fails because arrays are immutable. Layout write targets remain writable `u8` buffers or writable `view of u8` values.

## Runtime checks

With `--runtime-checks`, v0.22 extends checked storage assertions to:

- dynamic array loads
- dynamic views created from arrays
- dynamic layout reads from arrays

Static out-of-bounds array, view, and layout operations remain compile-time diagnostics with or without `--runtime-checks`.

## Interface JSON, C headers, and artifacts

Arrays are local-only in v0.22 and do not appear in interface JSON or C headers. Existing artifact modes (`mlir`, `lowered-mlir`, `llvm-ir`, `object`, `executable`, `static-library`, `interface-json`, and `c-header`) are unchanged, and array programs use the existing MLIR/LLVM pipeline.

## Non-goals

v0.22 does not add dynamic arrays, heap allocation, array parameters, array return values, arrays in records, arrays as buffer elements, arrays in constants, array assignment, string literals, pointer semantics, a separate slice syntax, or runtime bounds checks enabled by default.
