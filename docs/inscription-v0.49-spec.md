# Inscription v0.49 `comptime` scalar evaluation

Inscription v0.49 exposes the v0.48 pure interpreter through a narrow source expression:

```inscription
comptime phrase call
```

A `comptime` expression evaluates a pure returning phrase call during compilation and replaces the expression with the resulting constant. No runtime call is emitted.

## Syntax

```inscription
To square x: i32, giving i32.
Give x times x.

Constant sixteen: i32 be comptime square 4.
```

`comptime` is a lowercase expression prefix. It must be followed by a normal phrase call, not an arbitrary expression or statement. Parentheses work through the ordinary expression grammar:

```inscription
Give (comptime square 6) plus 6.
```

## Supported values

v0.49 supports user-facing `comptime` arguments and results for:

- `i1`
- integer scalars (`i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, `u64`)
- `f32` and `f64`
- nominal enum values

Record, layout-record, union, buffer, array, view, and owned-buffer `comptime` arguments or results are intentionally unsupported in v0.49, even though the internal interpreter can represent some of those values.

## Where it can be used

A `comptime` expression may appear anywhere a compile-time scalar/enum value is already accepted, including:

- constant initializers
- `Check` expressions
- buffer/array and owned-buffer static length expressions
- enum case values
- match range endpoints
- ordinary runtime expressions, where the result lowers as a constant

Example enum case:

```inscription
To active value, giving u8.
Give 1.

Enum Mode backed by u8 has idle be 0; active be comptime active value.
```

Example array length:

```inscription
To cell count, giving i32.
Give 4.

To main, giving i32.
Let cells be array of (comptime cell count) i32 containing 1, 2, 3, 4.
Give length of cells.
```

## Purity and interpreter limits

The called phrase must be executable by the pure interpreter. Allowed behavior includes scalar arithmetic, boolean operations, bitwise operations, shifts, casts, comparisons, enum values, match expressions and step matches, guards, alternatives, integer ranges, pure phrase calls, `When`/`Otherwise`, counted `For`, and `While` with a deterministic step limit.

Rejected behavior includes storage, arrays, buffers, views, owned buffers, layout read/write, extern calls, does phrases, test-only `Expect`, and any unsupported interpreter feature.

Diagnostics are surfaced as compiler diagnostics, for example:

```text
comptime evaluation failed: interpreter does not support arrays in v0.49
comptime evaluation failed: interpreter does not support extern phrase calls in v0.49
comptime evaluation failed: interpreter step limit exceeded
```

The step limit is fixed in v0.49 and is not user-configurable.

## Lowering

Successful `comptime` expressions lower as ordinary constants such as `arith.constant`. The phrase used for compile-time evaluation remains an ordinary phrase definition if it is otherwise present in the module, but the `comptime` call itself does not lower to a runtime `func.call`.

## Non-goals

v0.49 does not add `build.ins`, package script evaluation, macros, reflection, generated declarations, generated functions, generated records/enums/unions, comptime arrays/buffers/owned buffers, compile-time I/O, filesystem/environment/network/process access, extern execution, a stable interpreter CLI, generic comptime parameters, or type-level programming.
