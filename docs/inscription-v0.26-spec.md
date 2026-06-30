# Inscription v0.26 multi-payload union specification

Inscription v0.26 keeps the v0.25 language and tooling surface and lifts the single-payload restriction on tagged union variants. Union variants may now have zero, one, or more named payload fields. Match patterns may bind payload fields under their declared names or under explicit arm-local aliases.

Unions remain source-level value aggregates. They lower by value to flattened scalar SSA values: a deterministic internal `i32` tag plus payload slots for every payload field of every payload variant, in variant declaration order and then payload field declaration order. They do not introduce LLVM structs, heap allocation, pointers, references, or addressable union storage.

## Union declarations

```text
union Token:
  eof
  integer value: i64
  operator symbol: u8 and precedence: u8
  span start: i32 and end: i32
```

Rules:

- Union declarations are top-level items and may appear in root files or modules.
- Union names share the nominal type namespace with records, layout records, and enums.
- A union must declare at least one variant.
- Variant names are unique within a union.
- Variants receive deterministic internal tags in declaration order, starting at 0.
- A variant may have zero, one, or more payload fields.
- Payload fields are named `field: type` and multiple fields are joined with `and`.
- Payload field names are unique within a variant and may repeat across variants.
- Payload types may be primitive scalars, enums, value records, or layout records.
- Payload types may not be buffers, arrays, views, or unions.
- Recursive unions are not supported in v0.26.

## Constructors

```text
Token.eof
Token.operator with symbol be 43 and precedence be 10
Module.Token.operator with symbol be 10 and precedence be 5
```

Payload-free variants are constructed as `Union.variant`. Payload variants use `Union.variant with field be expression` and repeat `and field be expression` for additional fields. Constructor field initializers must appear exactly in declaration order in v0.26. Every payload field must be initialized exactly once; extra fields are rejected. Constructors produce the union type and may be used in local bindings, whole-union rebinding, normal phrase arguments, normal phrase returns, guarded value blocks, and match expression results.

## Matching and aliases

v0.24 match expressions and match step blocks accept union scrutinees.

```text
token score token: Token gives i32:
  match token:
    Token.operator with symbol as op and precedence as prec gives (op as i32) plus (prec as i32)
    Token.integer with value gives value as i32
    otherwise gives 0
```

Union pattern forms:

- `Union.variant`
- `Union.variant with field`
- `Union.variant with field as alias`
- `Union.variant with field and other_field`
- `Module.Union.variant with field as alias`

Rules:

- Pattern union type must exactly match the scrutinee union type.
- Payload-free variants must not specify payload bindings.
- Payload variants must list every payload field exactly once, in declaration order.
- Without an alias, each payload field introduces an arm-local binding with the field name.
- With `field as local_name`, only the alias is bound; the original field name is not bound.
- Payload aliases are scoped only to that match arm.
- Payload binding names must be unique within the pattern and must not shadow visible bindings.
- Payload bindings may be scalar, enum, record, or layout-record values.
- Duplicate union variant patterns in one match are rejected.
- `otherwise` remains required and final in v0.26.
- Match expressions may return scalar, enum, union, value-record, or layout-record values.
- Match step blocks carry assigned outer scalar, record, and union bindings through nested `scf.if` lowering.

Unions do not add equality, ordering, casts, arithmetic, constants, wildcard patterns, payload destructuring outside match arms, or exhaustive matches without `otherwise`.

## Representation and lowering

A union lowers to:

1. an internal `i32` tag,
2. flattened payload slots for all payload fields of all payload variants in declaration order.

Inactive payload slots are initialized to deterministic zero/default values of their slot types and are not source-visible.

Example:

```text
record Point:
  x: i32
  y: i32

union Event:
  none
  click point: Point and button: u8
```

`Event` lowers to `tag: i32`, `click.point.x: i32`, `click.point.y: i32`, and `click.button: u8`. Union parameters and returns flatten to those scalar operands/results. Union-valued `scf.if` and match expressions yield all slots.

## Modules

Unions are exported from modules like other top-level declarations. Imported constructors and types must be qualified:

```text
import Tokens

main gives i32:
  Tokens.score token Tokens.Token.operator with symbol be 10 and precedence be 5
```

Nominal identity includes the module-qualified union type name.

## Interface JSON

Interface JSON includes loaded union metadata using `payloads` lists:

```json
{
  "name": "Token",
  "kind": "union",
  "tag_type": "i32",
  "variants": [
    {"name": "eof", "tag": 0, "payloads": []},
    {
      "name": "operator",
      "tag": 1,
      "payloads": [
        {"name": "symbol", "type": "u8"},
        {"name": "precedence", "type": "u8"}
      ]
    }
  ]
}
```

Payloads are emitted in declaration order. Interface format remains `inscription-interface-v1`.

## Still not supported

v0.26 does not add recursive unions, union payloads of union type, positional payload syntax, tuple syntax, union buffers/arrays/views, union record fields, union layout fields, union constants, union equality, union casts, pattern aliases outside union payload patterns, wildcard patterns, exhaustiveness without `otherwise`, extern/export union ABI, C header union support, generic Option/Result, heap allocation, pointers/references, or custom MLIR dialects.
