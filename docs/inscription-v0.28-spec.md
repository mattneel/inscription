# Inscription v0.28 byte and byte-string literal specification

Inscription v0.28 keeps the v0.27 language and tooling surface and adds byte-oriented literals. This is a source-ergonomics feature for `u8` data only: it does not introduce a `String` type, heap allocation, global string storage, pointers, C string ABI, implicit null termination, interpolation, concatenation, I/O, or a runtime string object.

## Byte scalar literals

```text
byte "A"
byte "\n"
byte "\r"
byte "\t"
byte "\0"
byte "\""
byte "\\"
byte "\x41"
```

Rules:

- `byte "..."` decodes the quoted bytes using the v0.28 byte-string decoder.
- The decoded byte sequence must contain exactly one byte.
- The expression type is `u8`.
- The expression is compile-time evaluable.
- It may appear anywhere a `u8` expression is valid, including constants, enum cases backed by `u8`, record/layout/union initializers, storage containing lists, stores, phrase arguments, match patterns, and return values.
- No implicit cast is added; write `byte "A" as i32` to use the value as another integer type.

Diagnostics are deterministic:

```text
byte literal must decode to exactly one byte, got 0
byte literal must decode to exactly one byte, got 2
```

## Byte-string literals and byte sequences

```text
bytes "hello"
bytes "hello\n"
bytes "\x48\x65\x6c\x6c\x6f"
```

Rules:

- `bytes "..."` decodes to a compile-time sequence of `u8` byte values.
- The sequence is not a scalar expression and is not a storage value by itself.
- It may appear only in byte-sequence contexts:
  - explicit `u8` buffer/array `containing` lists,
  - inferred `array of bytes "..."` bindings,
  - inferred `buffer of bytes "..."` bindings,
  - `length of bytes "..."` expressions.
- It cannot be assigned to a scalar `let`, passed directly as a phrase argument, returned, stored in records/unions, or used in arithmetic/comparison/boolean expressions.

Invalid value use reports:

```text
byte string literal cannot be used as a value; use `array of bytes` or `buffer of bytes`
```

## Decoding and escapes

Byte literals and byte-string literals share one decoder.

Supported escapes:

- `\\` backslash
- `\"` double quote
- `\n` newline byte 10
- `\r` carriage return byte 13
- `\t` tab byte 9
- `\0` zero byte 0
- `\xNN` exactly two hexadecimal digits, producing byte value 0..255

Non-escaped source characters are encoded as UTF-8 bytes. ASCII text maps one source character to one byte. Non-ASCII source text is allowed and encodes to its UTF-8 bytes, but conformance tests avoid normalization-sensitive examples.

Unsupported escapes fail deterministically:

```text
invalid escape sequence \q
hex escape must contain exactly two hexadecimal digits
hex escape contains non-hexadecimal digit
unterminated string literal
```

No Unicode escapes, octal escapes, named escapes, `nan`, `inf`, or source character type are added.

## Explicit `containing` splices

Existing buffer/array literal initialization accepts byte-sequence splices when the element type resolves exactly to `u8`:

```text
let bytes be array of 5 u8 containing bytes "hello"
let bytes be buffer of 6 u8 containing bytes "hello", 0
let bytes be array of 4 u8 containing byte "A", bytes "BC", byte "D"
type Byte be u8
let bytes be array of 5 Byte containing bytes "hello"
```

Rules:

- `bytes "..."` expands to zero or more `u8` elements in source order.
- `byte "A"` is an ordinary `u8` expression and counts as one element.
- Splices are valid only for storage whose element type resolves to canonical `u8`; enum types backed by `u8` are not accepted.
- After expansion, the element count must exactly match the declared length.
- Non-splice elements still type-check normally with the element type as expected type.

Diagnostics include:

```text
byte string literal can only initialize u8 arrays or buffers, got i32
array bytes expects 4 elements, got 5
```

## Inferred byte arrays and buffers

```text
let hello be array of bytes "hello"
let scratch be buffer of bytes "hello"
let line be array of bytes "GET / HTTP/1.1\r\n"
```

Rules:

- `array of bytes "..."` creates an immutable fixed-size local array of `u8`.
- `buffer of bytes "..."` creates a mutable fixed-size local buffer of `u8`.
- Length is inferred from the decoded byte count.
- Decoded length must be at least one; zero-length arrays and buffers remain unsupported.
- The forms are equivalent to `array/buffer of N u8 containing bytes "..."` where `N` is the decoded length.
- The resulting storage supports existing `at`, `length of`, `for each index`, and `view of` operations. Array immutability and buffer mutability are unchanged.

## `length of bytes`

```text
constant hello_length: i32 be length of bytes "hello"

main gives i32:
  length of bytes "A\n"
```

Rules:

- `length of bytes "..."` has type `i32`.
- It is compile-time evaluable.
- It counts decoded bytes, not source characters.
- It does not allocate storage.

## Match patterns

Byte literals may be used as match patterns when the scrutinee type is `u8`:

```text
classify byte b: u8 gives i32:
  match b:
    byte "A" gives 1
    byte "\n" gives 2
    otherwise gives 3
```

Duplicate pattern detection uses the decoded `u8` value, so `byte "A"` and `65` in the same `u8` match are duplicates.

## Layout, views, constants, and aliases

Byte literals and byte-string storage interact with existing features without new representation rules:

- `byte "..."` constants appear as ordinary `u8` constants in interface JSON.
- Local byte arrays/buffers do not appear in interface JSON.
- C headers are unchanged; `u8` exported signatures continue to follow existing header restrictions.
- Layout reads work from inferred byte arrays and byte buffers because they are ordinary `u8` storage.
- Layout writes still require writable `u8` buffers or writable `view of u8`; arrays remain immutable.
- Aliases resolving to `u8` may be used in explicit `containing bytes "..."` storage element positions.
- Inferred `array of bytes` and `buffer of bytes` always use canonical `u8`.

## MLIR lowering

No new MLIR dialects are introduced. v0.28 continues using `builtin.module`, `func`, `arith`, `scf`, `memref`, and `cf` when assertions are emitted.

- `byte "A"` lowers to an `arith.constant` of MLIR type `i8`.
- `length of bytes "abc"` lowers to an `arith.constant 3 : i32`.
- Byte arrays and byte buffers lower like existing `containing` storage: `memref.alloca` plus deterministic `memref.store` operations at indices `0..N-1`.
- No `memref.global`, string object, heap allocation, pointer, or runtime library is emitted.

## Non-goals

v0.28 does not add a `String` type, `char` type, heap strings, dynamic strings, string constants, byte-array constants, global string storage, interpolation, concatenation, Unicode escape syntax, C string ABI, null termination by default, command-line argument strings, file I/O, pointers/references, or custom MLIR dialects.
