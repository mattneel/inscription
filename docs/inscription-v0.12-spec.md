# Inscription v0.12 specification

Inscription v0.12 keeps the v0.11 scalar, control-flow, buffer, view, record, layout-record, serialization, constants/checks, and module/import surface and adds runtime requirements plus an optional checked storage mode.

## Compile-time `check` versus runtime `require`

`check expression` remains a compile-time assertion. Its expression must have type `i1`, must be compile-time evaluable, and emits no MLIR.

`require expression` is a phrase-body step:

```text
require divisor is not equal to zero
require index is greater than or equal to 0
require index is less than length of cells
```

Rules:

- `require` may appear inside `gives` and `does` phrase bodies, including nested branches and loops.
- `require` may not appear at top level.
- `require` is a step, not an expression, and does not satisfy a `gives` phrase value block.
- The condition must have type `i1`.
- The condition may depend on runtime values.
- If the condition is compile-time evaluable and true, it emits no MLIR.
- If the condition is compile-time evaluable and false, compilation fails with `require condition is known to be false`.
- If the condition is dynamic, it lowers to a runtime assertion.

Dynamic requires lower to standard MLIR `cf.assert` with deterministic compiler-generated messages such as `require failed at line 2`. No source-level strings, exceptions, result types, panic values, stack traces, or recovery mechanisms are added in v0.12.

## Optional checked storage mode

The CLI accepts an opt-in checked-storage mode:

```text
inscription compile SOURCE --runtime-checks
inscription compile SOURCE --verify --runtime-checks
inscription run SOURCE --runtime-checks
```

The flag also works with `--module-root`.

Default compilation without `--runtime-checks` preserves v0.11 behavior and existing MLIR output. Dynamic buffer/view/layout bounds remain unchecked by default.

With `--runtime-checks`, the compiler emits runtime assertions for dynamic storage operations whose bounds cannot be checked at compile time:

- dynamic buffer loads and stores: `0 <= index < length`
- dynamic view creation: `start >= 0`, `count >= 0`, `start <= length`, `count <= length - start`
- dynamic view loads and stores: `0 <= index < length`
- dynamic layout reads and writes through `u8` buffers/views: `index >= 0` and `index <= length - size of Type`

For unsigned index expressions, lower-bound checks may be omitted. Static out-of-bounds expressions remain compile-time diagnostics with or without `--runtime-checks`.

Compiler-generated for-each loops may still contain local checked loads/stores when checked mode is enabled; v0.12 does not include a proof pass to remove redundant assertions.

## MLIR lowering

The emitter continues to use standard dialects:

```text
builtin.module
func
arith
scf
memref
cf      # only when runtime assertions are emitted
```

`require` and checked-storage assertions lower to `cf.assert`. The existing LLVM/MLIR 22 lowering pipeline remains unchanged:

```text
--convert-scf-to-cf
--convert-cf-to-llvm
--convert-arith-to-llvm
--expand-strided-metadata
--finalize-memref-to-llvm
--convert-func-to-llvm
--reconcile-unrealized-casts
```

No custom dialect, heap allocation, pointers, references, source strings, source-level I/O, `return`, `break`, `continue`, macros, generics, overloading, implicit scalar casts, short-circuit booleans, or general effect system are added in v0.12.

## Golden conformance suite

The normal exact-output golden suite in `tests/goldens` covers default compilation and keeps existing v0 through v0.11 output stable. Checked-mode goldens in `tests/goldens_checked` are compiled with `--runtime-checks` semantics.
