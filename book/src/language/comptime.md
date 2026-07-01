# Comptime

`comptime` evaluates a pure phrase call during compilation:

```inscription,check
To square x: i32, giving i32.
Give x times x.

Constant sixteen: i32 be comptime square 4.

Check sixteen is equal to 16.

To main, giving i32.
Give sixteen.
```

The syntax is lowercase `comptime` followed by a normal phrase call. The call is executed by Inscription's pure interpreter while the program is compiled, and the result lowers as an ordinary constant. No runtime `func.call` is emitted for the `comptime` call.

`comptime` may be used wherever a compile-time scalar or enum value is accepted, including constants, checks, buffer/array length expressions, enum case values, match range endpoints, and normal runtime expressions:

```inscription,check
To cell count, giving i32.
Give 4.

To main, giving i32.
Let cells be array of (comptime cell count) i32 containing 1, 2, 3, 4.
Give length of cells.
```

v0.49 supports user-facing `comptime` arguments and results for `i1`, integer scalars, `f32`, `f64`, and enums. Records, unions, buffers, arrays, views, and owned buffers are intentionally not supported as `comptime` arguments or results yet.

A `comptime` phrase must be pure enough for the interpreter. Scalar arithmetic, comparisons, casts, boolean and bitwise operators, matches, guards, alternatives, ranges, `When`/`Otherwise`, counted `For`, and bounded `While` are supported. Storage, owned buffers, views, layout read/write, extern calls, does phrases, test `Expect`, I/O, filesystem access, and package/build scripting are rejected.

This is not a macro system. It cannot generate declarations, inspect packages, execute externs, or access the environment. `package.ins` remains declarative. v0.63 `build.ins` uses the interpreter groundwork through a separate restricted Build API, not through `comptime`.
