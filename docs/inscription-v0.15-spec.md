# Inscription v0.15 specification

Inscription v0.15 keeps the v0.14 scalar, control-flow, buffer, view, record, layout-record, serialization, constants/checks, modules/imports, runtime `require`, optional checked-storage, record-return, and scalar extern phrase surface and adds scalar-only exported phrase definitions.

## Exported phrase definitions

Exported phrases are top-level phrase definitions with bodies and stable external MLIR symbols:

```text
export add left: i32 and right: i32 gives i32 as ins_add:
  left plus right

export notify code: i32 does as ins_notify:
  require code is greater than or equal to 0
```

The phrase-shaped source name remains the way Inscription calls the phrase. The symbol after `as` is used only for emitted MLIR. Exported phrases share the same phrase namespace as normal and extern phrases in the same module; no overloading is added.

An exported phrase definition requires a trailing colon and an indented body. Unlike v0.14 `extern` declarations, exported phrases define Inscription bodies rather than external declarations.

## Supported ABI types

Exported phrase signatures are scalar-only in v0.15. Parameter types may be:

```text
i1 i8 i16 i32 i64 u8 u16 u32 u64
```

`gives` return types may be the same scalar types. `does` exports return no value. Buffer parameters, view parameters, record parameters, layout-record parameters, record returns, buffer returns, and view returns are not supported at the exported ABI boundary.

The body of an exported phrase may still use normal Inscription features, including local records, local buffers, local views, constants, `require`, normal helper phrases, imported phrases, and extern calls, as long as the public exported signature is scalar-only.

## Source calls

Inside Inscription, exported phrases behave like normal phrases:

```text
export add left: i32 and right: i32 gives i32 as ins_add:
  left plus right

main gives i32:
  add 40 and 2
```

A `gives` export is a scalar expression call. A `does` export is a standalone step. Imported exported phrases must still be qualified using the module name, while calls lower to the exported symbol:

```text
import Math

main gives i32:
  Math.square of 9
```

If `Math.square` was exported as `ins_square`, the emitted call targets `@ins_square`, not a generated module-qualified symbol.

## Symbol rules

Exported symbols use the same unquoted external symbol syntax as v0.14 externs:

```text
ins_add
runtime.add_i32
math.square_i32
```

The symbol is case-sensitive and emitted deterministically as the MLIR function symbol. v0.15 rejects:

- duplicate exported symbols
- exported symbols named `main`
- exported symbols that conflict with generated normal phrase symbols
- exported symbols that conflict with extern symbols
- phrase-template duplicates across normal, extern, and exported phrases in the same module

## MLIR lowering

Exported phrases lower to public/default-visibility `func.func` definitions using the external symbol:

```mlir
func.func @ins_add(%left: i32, %right: i32) -> i32 {
  %0 = arith.addi %left, %right : i32
  return %0 : i32
}
```

Inscription calls to exported phrases lower to `func.call` operations targeting the same exported symbol:

```mlir
%result = func.call @ins_add(%left, %right) : (i32, i32) -> i32
```

Normal phrases keep their generated symbol names. Extern phrases continue to lower to private declarations. The emitter continues to use only standard dialects:

```text
builtin.module
func
arith
scf
memref
cf      # only when runtime assertions are emitted
```

No MLIR lowering pipeline change is required.

## Compile-time evaluation

Exported phrase calls are runtime calls and are not compile-time evaluable. A constant initializer or `check` expression that depends on an exported call is rejected as not compile-time evaluable.

## Non-goals

Inscription v0.15 does not add C ABI guarantees beyond scalar LLVM-level function signatures, object-file packaging, header generation, linker flags, library names, source string literals, pointer types, references, address-of, exported buffer/view/record parameters, exported record returns, varargs, callbacks, function pointers, dynamic loading, header imports, ABI structs, heap allocation, I/O syntax, macros, generics, overloading, custom dialects, implicit casts, short-circuit boolean semantics, or a general effect system.
