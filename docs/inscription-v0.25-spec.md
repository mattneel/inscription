# Inscription v0.25 tagged union specification

Inscription v0.25 keeps the v0.24 language and tooling surface and adds nominal tagged union value types with payload-free variants and single-payload variants.

Unions are source-level value aggregates. They lower by value to flattened scalar SSA values: a deterministic internal `i32` tag plus payload slots for every payload variant in declaration order. They do not introduce LLVM structs, heap allocation, pointers, references, or addressable union storage.

## Union declarations

```text
union MaybeI32:
  none
  some value: i32

union ParseResult:
  value value: i32
  error code: u8
```

Rules:

- Union declarations are top-level items and may appear in root files or modules.
- Union names share the nominal type namespace with records, layout records, and enums.
- A union must declare at least one variant.
- Variant names are unique within a union.
- Variants receive deterministic internal tags in declaration order, starting at 0.
- A variant may have no payload or exactly one payload.
- Payload types may be primitive scalars, enums, value records, or layout records.
- Payload types may not be buffers, arrays, views, or unions.
- Recursive unions and multi-payload variants are not supported in v0.25.

## Constructors

```text
MaybeI32.none
MaybeI32.some with value be 42
Module.MaybeI32.some with value be 7
```

Payload-free variants are constructed as `Union.variant`. Payload variants use `Union.variant with payload_name be expression`; the payload name must match the declaration exactly and the payload expression must have the declared payload type. Constructors produce the union type and may be used in local bindings, whole-union rebinding, normal phrase arguments, normal phrase returns, guarded value blocks, and match expression results.

## Locals, parameters, and returns

Union values may be local bindings, normal phrase parameters, and normal phrase return values:

```text
make maybe flag: i1 gives MaybeI32:
  MaybeI32.some with value be 42 when flag
  otherwise MaybeI32.none

main gives i32:
  let maybe be MaybeI32.none
  maybe becomes MaybeI32.some with value be 5
  match maybe:
    MaybeI32.some with value gives value
    otherwise gives 0
```

Whole-union rebinding is SSA rebinding, not storage mutation. Union payloads are not fields and cannot be accessed with dot syntax; payload access is only through match arm binding.

`run` and executable emission continue to require a root no-hole `main` returning an integer scalar, so `main gives MaybeI32` is compile-only and rejected by `run`/executable emission.

## Matching unions

v0.24 match expressions and match step blocks now accept union scrutinees.

```text
value or zero maybe: MaybeI32 gives i32:
  match maybe:
    MaybeI32.some with value gives value
    MaybeI32.none gives 0
    otherwise gives 0
```

Union pattern forms:

- `Union.variant`
- `Union.variant with payload_name`
- `Module.Union.variant`
- `Module.Union.variant with payload_name`

Rules:

- Pattern union type must exactly match the scrutinee union type.
- Payload variants require the payload binding in the pattern.
- Payload-free variants must not specify a payload binding.
- The payload binding is visible only in that arm.
- Payload bindings may be scalar, enum, record, or layout-record values.
- Duplicate union variant patterns in one match are rejected.
- `otherwise` remains required and final in v0.25.
- Match expressions may return scalar, enum, union, value-record, or layout-record values.
- Match step blocks carry assigned outer scalar, record, and union bindings through nested `scf.if` lowering.

Unions do not add equality, ordering, casts, arithmetic, constants, wildcard patterns, payload destructuring outside match arms, or exhaustive matches without `otherwise`.

## Representation and lowering

A union lowers to:

1. an internal `i32` tag,
2. flattened payload slots for all payload variants in declaration order.

Inactive payload slots are initialized to deterministic zero/default values of their slot types and are not source-visible.

Example:

```text
union MaybePoint:
  none
  some point: Point
```

If `Point` has fields `x: i32` and `y: i32`, `MaybePoint` lowers to `tag: i32`, `some.point.x: i32`, and `some.point.y: i32`. Union parameters and returns flatten to those scalar operands/results. Union-valued `scf.if` and match expressions yield all slots.

## Modules

Unions are exported from modules like other top-level declarations. Imported constructors and types must be qualified:

```text
import Maybe

main gives i32:
  Maybe.value or zero Maybe.MaybeI32.some with value be 7
```

Nominal identity includes the module path; `Maybe.MaybeI32` and `Other.MaybeI32` are distinct types.

## Unsupported contexts

Unions are not supported in v0.25 as:

- top-level constants,
- record fields,
- layout record fields,
- buffer elements,
- array elements,
- view elements,
- extern phrase parameters or returns,
- exported phrase parameters or returns,
- C header declarations,
- casts, arithmetic, comparisons, boolean operators, or indices.

Use ordinary wrapper phrases with primitive scalar exports if host integration needs a union-derived result.

## Interface JSON

Interface manifests include union metadata:

```json
{
  "name": "MaybeI32",
  "kind": "union",
  "tag_type": "i32",
  "variants": [
    {"name": "none", "tag": 0, "payload": null},
    {"name": "some", "tag": 1, "payload": {"name": "value", "type": "i32"}}
  ]
}
```

Variants are emitted in declaration order with deterministic tag values. Record and layout-record payloads are reported by nominal type name. C header output is unchanged and does not emit unions.

## Non-goals

v0.25 does not add recursive unions, union payloads that are unions, multiple payload fields per variant, generic `Option<T>`/`Result<T,E>`, tagged-union constants, union equality, union casts, union buffers/arrays/views, union record/layout fields, extern/export union ABI, C header union generation, heap allocation, pointers/references, match guards, wildcard patterns, payload destructuring outside match arms, exhaustive matches without otherwise, macros, generics, overloading, or custom MLIR dialects.
