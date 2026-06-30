# Inscription v0.30 nested-scope owned buffer specification

Inscription v0.30 keeps the v0.29 language and tooling surface and lifts the phrase-body-only restriction on owned dynamic buffers. Owned buffers remain local storage, are passed to reusable code through borrowed views, and are automatically deallocated at deterministic lexical-scope exits. They do not add ownership transfer, manual free syntax, resizing, buffer ABI, heap strings, pointers, or dynamic arrays as a separate type.

## Owned buffer bindings

```text
let cells be owned buffer of n i32 filled with 0
let bytes be owned buffer of count u8 filled with byte "\0"
let weights be owned buffer of n f64 filled with 1.5
let modes be owned buffer of n Mode filled with Mode.idle
```

Rules:

- The length expression must have type `i32`.
- A compile-time length must be at least `1`.
- A dynamic length less than `1` is unchecked by default; with `--runtime-checks`, v0.30 emits a runtime assertion that the length is at least `1`.
- Element types may be integer numeric types, `f32`/`f64`, or enum types.
- Element types may not be `i1`, records, layout records, unions, buffers, arrays, or views.
- Aliases may be used in the element type position when they resolve to a valid element type.
- The fill expression must exactly match the element type and is evaluated once, then stored into every element.
- Owned buffers are mutable lexical storage bindings.
- Owned buffers may be declared in any step block where ordinary local storage can be declared: phrase bodies, `if`/`otherwise` branches, `while` bodies, counted `for` bodies, `for each` bodies, match step arms, and nested combinations of those blocks.
- Owned buffers cannot be copied, rebound, returned, used as phrase parameters, stored in records or unions, used as extern/export ABI values, or used as scalar expressions.
- Views derived from owned buffers are valid only within the owned buffer's lexical scope and cannot escape through normal binding scope rules.

Deterministic diagnostics include:

```text
owned buffer length must be at least 1
owned buffer length must have type i32, got i64
owned buffer element type must be numeric or enum, got i1
owned buffer element type may not be a union type in v0.30
unknown binding cells
```

## Lexical cleanup and nested scopes

Owned buffers may be declared inside nested step scopes:

```text
if flag:
  let cells be owned buffer of 4 i32 filled with 0
  cells at 0 becomes 7
otherwise:
  let ignored be 0

for i from 0 up to 4:
  let cells be owned buffer of 2 i32 filled with i
  ...

match mode:
  Mode.active:
    let cells be owned buffer of 4 i32 filled with 1
  otherwise:
    let ignored be 0
```

Rules:

- Owned buffers declared directly in a lexical step block are deallocated at the end of that block.
- Multiple owned buffers in the same block are deallocated in reverse declaration order.
- A branch allocates only the owned buffers in the selected branch.
- A loop allocates and deallocates loop-body owned buffers each iteration.
- A match step allocates and deallocates only the selected arm's owned buffers.
- Nested blocks clean up their owned buffers before the enclosing block cleans up its own.
- Owned buffers and views declared inside a branch, loop body, or match arm do not escape that scope; references after the block are reported as unknown bindings.


## Indexing, stores, length, and iteration

Owned buffers use existing storage syntax:

```text
cells at i
cells at i becomes value
length of cells
for each index i of cells:
  ...
```

Rules:

- A load has the owned buffer element type.
- A store value must exactly match the element type.
- Index expressions use the existing storage index rule: integer numeric, not `i1`, not float, and not enum.
- If the index and owned buffer length are both compile-time known, bounds are checked statically.
- Dynamic indices are unchecked by default. With `--runtime-checks`, v0.30 checks `0 <= index < length` for dynamic owned-buffer loads and stores.
- `length of owned_buffer` returns the stored `i32` length. It is compile-time evaluable only when the owned buffer length is compile-time known.
- `for each index` over an owned buffer iterates from `0` up to the stored runtime length and keeps the existing `i32` loop-index type.

## Borrowed views and phrase calls

Owned buffers can be borrowed as views:

```text
let window be view of cells from start for count
sum view cells
```

Rules:

- A view derived from an owned buffer is writable when the source owned buffer is writable.
- The view is non-owning; only the owned root buffer is deallocated.
- `view of TYPE` parameters accept owned buffers as full views when the element type matches exactly.
- Passing an owned buffer to a fixed-size `buffer of N TYPE` parameter is rejected.
- Same-root alias rejection applies to owned buffers and views derived from them.
- Under `--runtime-checks`, dynamic views over owned buffers check `start >= 0`, `count >= 0`, `start <= length`, and `count <= length - start`.

## Layout read/write

Layout serialization accepts owned `u8` buffers in the same places as writable `u8` buffers:

```text
packed layout record Word:
  value: u16

let bytes be owned buffer of 2 u8 filled with 0
let word be Word with value be 42
write word into bytes at 0
let copy be read Word from bytes at 0
```

Rules:

- `read Type from source at index` accepts `u8` fixed buffers, owned buffers, arrays, and views.
- `write value into target at index` accepts writable `u8` fixed buffers, owned buffers, and views.
- Arrays remain read-only and cannot be layout write targets.
- Static layout bounds are checked when the owned buffer length is compile-time known.
- With `--runtime-checks`, dynamic layout read/write bounds through owned buffers are checked against the runtime length.

## Byte literals and aliases

Owned buffers do not add a byte-string constructor in v0.30:

```text
let bytes be owned buffer of bytes "hello"  # invalid
```

Use fixed `array of bytes "..."` or `buffer of bytes "..."` for byte-string literals. Owned `u8` buffers may still be filled with byte scalar literals, and aliases resolving to valid element types work normally:

```text
type Byte be u8
let bytes be owned buffer of 4 Byte filled with byte "A"
```

Owned buffer storage aliases are not added in v0.30; `type DynBytes be owned buffer of u8` is not a type-expression form.

## MLIR lowering

No new MLIR dialects are introduced. v0.30 continues using `builtin.module`, `func`, `arith`, `scf`, `memref`, and `cf` when assertions are emitted.

Owned buffers lower to dynamic memrefs:

```text
%n_index = arith.index_cast %n : i32 to index
%cells = memref.alloc(%n_index) : memref<?xi32>
scf.for %i = %c0 to %n_index step %c1 {
  memref.store %fill, %cells[%i] : memref<?xi32>
}
...
memref.dealloc %cells : memref<?xi32>
```

Rules:

- The source `i32` length value is kept for `length of`, iteration, views, and runtime checks.
- Owned buffers are deallocated at lexical-scope exit in reverse declaration order for the scope.
- Phrase-body owned buffers are deallocated before function return.
- Branch-local owned buffers are deallocated before the branch `scf.yield`.
- Loop-body owned buffers are allocated and deallocated on each iteration before the body `scf.yield` or region close.
- Match-arm owned buffers are deallocated before the selected arm yields.
- `gives` phrases compute the final scalar/flattened result values first, deallocate live phrase-body owned buffers, then return those values.
- `does` phrases deallocate live phrase-body owned buffers before their empty return.
- Cleanup is not guaranteed if a runtime assertion aborts.
- Views are never deallocated.

## Interface JSON and C headers

Owned buffers are local-only and do not appear in interface JSON. They are not valid extern/export ABI types, and C header output is unchanged.

## Non-goals

v0.30 does not add owned buffer parameters, owned buffer returns, ownership transfer, move semantics, manual deallocation syntax, resizing/reallocation, dynamic arrays separate from owned buffers, byte-string owned-buffer constructors, owned storage aliases, heap records, heap strings, pointer/reference types, C ABI for buffers, deallocation on assertion abort, try/finally or defer syntax, or custom MLIR dialects.
