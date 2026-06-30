# Inscription v0.23 nominal enum specification

Inscription v0.23 keeps the v0.22 language and tooling surface and adds nominal integer-backed enum types with named cases.

Enums are source-level nominal values. They lower to their underlying integer MLIR type, but they are not integers in source syntax: arithmetic, ordering, indexing, extern/export ABI use, and interop require explicit casts where supported.

## Enum declarations

Enums are top-level declarations:

```text
enum Mode: u8:
  idle be 0
  active be 1
  failed be 2
```

Rules:

- The enum name shares the nominal type namespace with value records and layout records.
- The enum name must not collide with scalar type names, record names, layout record names, other enum names, or constants.
- The underlying type must be one of `i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, or `u64`.
- `i1`, `f32`, `f64`, records, buffers, arrays, and views are not enum underlying types.
- Each enum must declare at least one case.
- Case names are unique within the enum.
- Case values are compile-time evaluable expressions checked as the underlying integer type.
- Case values must be unique in v0.23.
- Cases are not auto-numbered in v0.23.

## Enum case expressions

Cases are referenced through the enum type name:

```text
Mode.idle
Mode.active
Protocol.Mode.active
```

A local case expression has the enum type. An imported case expression is module-qualified. Case expressions are compile-time evaluable and lower to the underlying integer constant.

## Enum values and nominal typing

Enum values are allowed in:

- `let` bindings and `let` annotations
- top-level constants
- phrase parameters and phrase return types for normal `gives`/`does` phrases
- value record fields and record returns
- buffer, immutable array, and borrowed view element types
- layout record and packed layout record fields
- equality comparisons, `check`, and `require`
- guarded value expressions and phrase calls

Enums are nominal. `Mode`, `Status`, `Protocol.Mode`, and `Other.Mode` are distinct types even if they share the same underlying integer type and case values.

No implicit enum/integer conversion is added. Use `as` for explicit casts.

## Comparisons

Enums support equality comparisons when both operands have the exact same enum type:

```text
mode is equal to Mode.active
mode is not equal to Mode.failed
```

These lower to integer `arith.cmpi eq` and `arith.cmpi ne` on the underlying MLIR type.

Ordered comparisons are not supported directly. Cast to the underlying integer first:

```text
mode as u8 is greater than 1
```

## Casts

Supported casts:

- enum to its underlying integer type: no MLIR op, semantic relabel
- enum to another integer type: underlying integer cast using the existing integer cast rules
- enum to the same enum type: no-op
- exact underlying integer type to enum
- integer literal to enum, checked using the enum underlying type

Rejected casts:

- enum to a different enum without first casting through the underlying integer
- non-underlying integer variables to enum without an explicit intermediate cast
- enum to/from `i1`
- enum to/from `f32` or `f64`

## Constants and checks

Enum constants are compile-time values:

```text
constant default_mode: Mode be Mode.active
constant default_value: u8 be default_mode as u8
check default_mode is equal to Mode.active
```

Enum cases, enum constants, enum equality, and supported enum casts are compile-time evaluable.

## Buffers, arrays, and views

Buffers, arrays, and views can use enum element types:

```text
let modes be array of 3 Mode containing Mode.idle, Mode.active, Mode.failed
let mutable be buffer of 2 Mode filled with Mode.idle
mutable at 1 becomes Mode.active
```

Storage lowers to the enum underlying integer type, for example `Mode: u8` lowers as `i8` storage. Element initialization, stores, and view parameter passing require the exact enum type. Enum values cannot be used as storage indices without an explicit cast.

## Records and layout records

Value records can contain enum fields, and record-returning phrases flatten enum fields as underlying integer scalar results.

Layout and packed layout records can contain enum fields. Enum layout fields use the underlying integer type's size, alignment, byte offsets, and little-endian serialization. Reading a layout record may produce an enum value whose underlying integer does not match a declared case; v0.23 does not add runtime enum validity checks.

## Normal phrases

Normal `gives` and `does` phrases may use enum parameter and return types:

```text
choose mode mode: Mode gives i32:
  7 when mode is equal to Mode.active
  otherwise 3

make mode active: i1 gives Mode:
  Mode.active when active
  otherwise Mode.idle
```

Imported enum types and cases remain module-qualified and nominal.

## Externs, exports, C headers, and interface JSON

Extern and exported phrase ABIs remain primitive-scalar-only in v0.23. Enum parameters and enum returns are rejected for `extern` and `export` declarations; write an ordinary wrapper that casts to or from the underlying integer when host interop is needed.

C header emission does not generate C enum definitions in v0.23. Headers remain based on exported primitive scalar phrases.

Interface JSON adds an `enums` array per module:

```json
{
  "name": "Mode",
  "kind": "enum",
  "underlying_type": "u8",
  "cases": [
    {"name": "idle", "value": 0},
    {"name": "active", "value": 1}
  ]
}
```

Enum cases are emitted in declaration order. Record and layout fields that use enum types report the enum type name.

## Non-goals

v0.23 does not add tagged unions, payload variants, pattern matching, exhaustive switch/case syntax, enum methods, auto-numbered cases, bitflag syntax, enum arithmetic, enum ordering without explicit casts, enum C header generation, enum extern/export ABI support, enum validation for layout reads, enum arrays as constants, generics, overloading, macros, or custom MLIR dialects.
