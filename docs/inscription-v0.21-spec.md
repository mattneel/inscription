# Inscription v0.21 floating-point scalar specification

Inscription v0.21 keeps the v0.20 tooling surface and adds `f32` and `f64` as first-class scalar numeric types.

This is a source-language sprint. Existing integer-only programs, source MLIR goldens, modules, records, buffers/views, externs, exports, artifacts, interface JSON, and C headers remain compatible with v0.20 unless they opt into floating-point types.

## Scalar types

The scalar type set is now:

```text
i1
i8 i16 i32 i64
u8 u16 u32 u64
f32 f64
```

`f32` and `f64` are numeric scalar types, but not integer types. They are valid for:

- phrase parameters and `gives` return types
- `let` annotations and scalar rebinding
- top-level constants and compile-time checks
- runtime `require` expressions through float comparisons
- value-record fields and record returns
- local buffer element types, buffer parameters, view parameters, and view elements
- scalar-only extern phrase parameters/returns
- scalar-only exported phrase parameters/returns
- interface JSON metadata
- C header prototypes, where `f32` maps to `float` and `f64` maps to `double`

They are not valid for:

- buffer/view indices
- buffer lengths
- layout record fields
- layout read/write serialization fields
- bitwise operations
- shifts
- integer remainder
- `run` or executable `main` return types

`main gives f32` and `main gives f64` may be compiled as library-style functions, but `run` and `compile --emit executable` require a root no-hole `main` returning an integer scalar.

## Floating-point literals and `zero`

Decimal floating-point literals are supported:

```text
0.0
1.0
3.5
42.25
1e3
1.5e2
1.5e-2
0.25
```

A literal containing `.` or an exponent marker is a floating literal. v0.21 does not add hexadecimal floats, NaN/infinity literals, unary minus, fast-math syntax, rounding-mode syntax, or math builtins. Negative float values are still expressed with subtraction, for example `zero minus 1.5` in a float context.

A floating literal uses the expected type when a surrounding annotation, phrase call, record constructor, buffer fill, store, or return context provides one. Without an expected type, a floating literal defaults deterministically to `f64`.

`zero` uses the expected numeric type. In a float context it is a float zero; without an expected type it preserves the existing integer default behavior.

## Arithmetic and comparisons

`plus`, `minus`, `times`, and `divided by` support matching float operands:

```text
f32 op f32 -> f32
f64 op f64 -> f64
```

Mixed integer/float arithmetic and mixed `f32`/`f64` arithmetic are rejected. No implicit casts are introduced.

Lowering:

```text
plus       -> arith.addf
minus      -> arith.subf
times      -> arith.mulf
divided by -> arith.divf
```

`remainder` remains integer-only in v0.21.

Comparisons support matching float operands and return `i1`. Lowering uses ordered predicates:

```text
is equal to                  -> arith.cmpf oeq
is not equal to              -> arith.cmpf one
is less than                 -> arith.cmpf olt
is less than or equal to     -> arith.cmpf ole
is greater than              -> arith.cmpf ogt
is greater than or equal to  -> arith.cmpf oge
```

The source language does not add unordered, NaN, or finite predicates in v0.21.

## Casts

Postfix `as` supports explicit casts involving floats:

- signed integer to float: `arith.sitofp`
- unsigned integer to float: `arith.uitofp`
- float to signed integer: `arith.fptosi`
- float to unsigned integer: `arith.fptoui`
- `f32` to `f64`: `arith.extf`
- `f64` to `f32`: `arith.truncf`
- same float width: no-op

Casts between `i1` and `f32`/`f64` are not supported. Float-to-integer runtime behavior follows the MLIR/backend operation semantics; v0.21 does not add runtime range checks.

## Constants, checks, and requires

Top-level constants may have type `f32` or `f64`:

```text
constant half: f64 be 0.5
constant whole: f64 be half plus half
check whole is equal to 1.0
```

The compile-time evaluator supports finite float literals, `zero` in float context, earlier float constants, casts, float arithmetic, float comparisons, and parentheses. `f32` constants are rounded to `f32` precision; `f64` constants use `f64` precision. Constant float division by zero is rejected with the existing deterministic division-by-zero diagnostic. NaN and infinity constants are not introduced.

Runtime `require` can depend on float comparisons:

```text
divide floats x: f64 by divisor: f64 gives f64:
  require divisor is not equal to 0.0
  x divided by divisor
```

## Buffers, views, and records

Buffers and views may store `f32` or `f64` elements:

```text
let cells be buffer of 4 f32 filled with 1.5
sum float view cells: view of f32 gives f32:
  let total: f32 be 0.0
  for each index i of cells:
    total becomes total plus cells at i
  total
```

Buffer/view indices remain integer numeric expressions. Existing fixed-size and borrowed-view lowering continues to use `memref`, with `memref<...xf32>` or `memref<...xf64>` element types as needed.

Value records may contain float fields and be returned by value:

```text
record Vec2:
  x: f64
  y: f64
```

Layout records and packed layout records remain integer-only. `f32` and `f64` layout fields are rejected, and layout read/write serialization does not encode float fields in v0.21.

## Externs, exports, C headers, and interface JSON

Scalar-only extern and exported phrase signatures now include `f32` and `f64`:

```text
extern square root of x: f64 gives f64 as llvm.sqrt.f64

export multiply x: f64 by y: f64 gives f64 as ins_multiply_f64:
  x times y
```

C header emission supports exported ABI types:

```text
i32 u32 i64 u64 f32 f64
```

C type mapping:

```text
f32 -> float
f64 -> double
```

C header emission continues to reject `i1`, `i8`/`u8`, and `i16`/`u16`, and continues to require exported symbols to be valid C identifiers. Interface JSON emits `f32` and `f64` type names wherever they appear, including constants, records, externs, and exports.

## MLIR lowering

v0.21 continues to use only standard MLIR dialects already in the compiler pipeline:

- `builtin.module`
- `func`
- `arith`
- `scf`
- `memref`
- `cf` when runtime assertions are emitted

Added float lowering operations include:

- `arith.constant` for `f32`/`f64`
- `arith.addf`, `arith.subf`, `arith.mulf`, `arith.divf`
- `arith.cmpf`
- `arith.sitofp`, `arith.uitofp`, `arith.fptosi`, `arith.fptoui`
- `arith.extf`, `arith.truncf`

No MLIR pipeline change is required.

## Non-goals

v0.21 does not add:

- `f16` or `bf16`
- decimal or arbitrary-precision floats
- complex numbers
- vector/SIMD types
- NaN or infinity literals
- fast-math annotations
- rounding-mode annotations
- math builtins such as sqrt/sin/cos
- implicit numeric promotion
- implicit integer/float casts
- float buffer/view indices
- float buffer lengths
- float layout record fields
- float binary layout serialization
- float `main` for `run` or executable emission
- new source strings, pointers, references, heap allocation, generics, overloading, or custom MLIR dialects
