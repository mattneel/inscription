# Inscription v0.14 specification

Inscription v0.14 keeps the v0.13 scalar, control-flow, buffer, view, record, layout-record, serialization, constants/checks, modules/imports, runtime `require`, optional checked-storage, and record-return surface and adds scalar-only extern phrase declarations.

## Extern phrase declarations

Extern phrase declarations are top-level items with phrase-shaped headers and no bodies:

```text
extern population count of x: i32 gives i32 as llvm.ctpop.i32
extern host notify code: i32 does as host_notify
```

An extern declaration may appear in root files or imported modules. It shares the phrase namespace with normal phrases in the same module, so a module cannot define both a normal phrase and an extern phrase with the same phrase template. Extern declarations are exported from modules like normal top-level declarations.

`gives` extern phrases are expression calls that return a scalar. `does` extern phrases return no value and may only be used as standalone steps. Extern phrases never have an indented body; a trailing colon and body are invalid.

## External symbols

The external symbol after `as` is not a source string literal. It is written as identifier components separated by dots:

```text
abs
host_notify
llvm.ctpop.i32
runtime.fill_buffer
```

The symbol text is emitted as the MLIR function symbol target, subject only to the emitter's deterministic MLIR symbol printing. Inscription v0.14 does not add library names, linker flags, target triples, calling-convention annotations, dynamic loading, source strings, or C ABI guarantees. The compiler does not check that the external symbol exists at compile time.

## Supported types

Extern phrases are scalar-only in v0.14. Parameter types may be:

```text
i1 i8 i16 i32 i64 u8 u16 u32 u64
```

`gives` return types may be the same scalar types. `does` extern phrases return no value. Buffer parameters, view parameters, record parameters, layout-record parameters, record returns, buffer returns, and view returns are not supported for extern phrases.

Extern calls use the same source scalar typing rules as normal phrase calls: arguments must match exactly and no implicit casts are introduced. Signedness remains source-semantic while MLIR integer types remain signless. The external symbol ABI is the programmer's responsibility.

## Modules and qualification

Extern declarations inside imported modules are called with the normal qualified phrase syntax:

```text
import Intrinsics

main gives i32:
  Intrinsics.population count of 15
```

The source call is qualified for name resolution, but the emitted call targets the declared external symbol, not a generated module-qualified Inscription symbol. For example, an imported declaration

```text
extern population count of x: i32 gives i32 as llvm.ctpop.i32
```

still calls `@llvm.ctpop.i32`. Imported extern phrases are not made available as unqualified calls.

If multiple imported modules declare the same external symbol with identical scalar function types, the emitter produces one declaration. If the function types are incompatible, compilation fails deterministically.

## MLIR lowering

Extern declarations lower to private `func.func` declarations without bodies:

```mlir
func.func private @llvm.ctpop.i32(i32) -> i32
func.func private @host_notify(i32)
```

Calls lower through ordinary `func.call` operations to the external symbol:

```mlir
%result = func.call @llvm.ctpop.i32(%value) : (i32) -> i32
func.call @host_notify(%code) : (i32) -> ()
```

Normal Inscription phrase definitions keep using generated symbols. A normal generated function symbol cannot conflict with an extern symbol; in particular an extern symbol named `main` conflicts with generated root `main`.

The emitter continues to use only standard dialects:

```text
builtin.module
func
arith
scf
memref
cf      # only when runtime assertions are emitted
```

The v0.12 LLVM/MLIR 22 lowering pipeline remains unchanged.

## Compile-time evaluation

Extern calls are runtime calls and are not compile-time evaluable. A constant initializer or `check` expression that depends on an extern call is rejected as not compile-time evaluable.

## Non-goals

Inscription v0.14 does not add C ABI declarations, calling-convention annotations, linker flags, library names, source string literals, pointer types, references, address-of, extern buffer/view/record parameters, extern record returns, varargs, callbacks, function pointers, dynamic loading, header imports, ABI structs, heap allocation, I/O syntax, macros, generics, overloading, custom dialects, implicit casts, short-circuit boolean semantics, or a general effect system.
