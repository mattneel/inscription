# Inscription v0.13 specification

Inscription v0.13 keeps the v0.12 scalar, control-flow, buffer, view, record, layout-record, serialization, constants/checks, modules/imports, runtime `require`, and optional checked-storage surface and adds record return values.

## Record return values

`gives` phrase return types may now be scalar types or nominal record types:

```text
record Point:
  x: i32
  y: i32

make point x: i32 and y: i32 gives Point:
  Point with x be x and y be y
```

The return type may name a local value record, local layout record, or a qualified imported record such as `Geometry.Point`. Buffer and view return types remain unsupported. `does` phrases still return no value.

A record-valued value block may return:

- a record constructor
- a visible record binding
- a layout read expression of the matching layout-record type
- a phrase call returning the exact same nominal record type

The final value type must match the phrase return type exactly. Nominal identity is strict: `Geometry.Point`, `Other.Point`, and local `Point` are different types even when their fields match. No implicit casts, structural record typing, record subtyping, buffer/view returns, or source-level multiple-return syntax are added.

## Guarded record value blocks

Guarded value blocks support record expressions:

```text
choose point flag: i1 gives Point:
  Point with x be 7 and y be 0 when flag
  otherwise Point with x be 0 and y be 3
```

Both branches must return the same nominal record type. They lower to `scf.if` with one scalar result per field, in declaration order.

## Record-returning calls

Record-returning phrase calls are valid in record contexts:

```text
main gives i32:
  let p be make point 10 and 20
  p.x plus p.y
```

A record-returning call can initialize a `let`, satisfy a matching typed `let`, or be the right-hand side of whole-record rebinding:

```text
p becomes make point 1 and 2
```

Record-returning calls remain invalid in scalar expression contexts, and any `gives` phrase call remains invalid as a standalone step.

## Modules

Imported record-returning phrases return qualified nominal record types. A phrase in module `Geometry` that returns `Point` is seen by importers as returning `Geometry.Point` and lowers to the existing stable module-qualified MLIR symbol scheme.

```text
import Geometry

main gives i32:
  let p be Geometry.make point 10 and 20
  p.x plus p.y
```

## `main` and execution

Compiling a library-style file with a record-returning `main` is allowed. `run` still requires the root no-hole `main` to return an integer scalar suitable for a process exit status. `main gives i1` and `main gives Point` are rejected by `run` with a deterministic diagnostic.

## MLIR lowering

Records remain source-level value aggregates. They are not addressable and do not lower to LLVM structs. Record-returning phrases lower to flattened scalar MLIR function results:

```mlir
func.func @make_point(%x: i32, %y: i32) -> (i32, i32) {
  return %x, %y : i32, i32
}
```

Call results are bound back to source record fields in declaration order. Layout records return their scalar fields in layout declaration order but still do not lower to LLVM/C ABI structs.

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

No LLVM struct lowering, ABI records, record buffers, buffer/view returns, nested record fields, pointers, references, address-of, heap allocation, dynamic dispatch, generics, overloading, destructuring, tuple syntax, source-level multiple scalar returns, source-level `return`, `break`, `continue`, custom dialects, structural typing, implicit casts, or general effect system are added in v0.13.
