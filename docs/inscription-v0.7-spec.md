# Inscription v0.7 specification

Inscription v0.7 is a deterministic, phrase-shaped compiler. It keeps the v0.6 scalar, control-flow, cast, local-buffer, buffer-parameter, `does` phrase, counted-loop, and buffer-length surface, and adds source-level value records.

## Execution model

- A program is a list of top-level record declarations and phrase definitions.
- A phrase definition is either a `gives` phrase, which returns a scalar value, or a `does` phrase, which returns no value.
- Source-visible scalar types are `i1`, signed integers `i8`/`i16`/`i32`/`i64`, and unsigned integers `u8`/`u16`/`u32`/`u64`.
- Source-visible buffer parameter types are written `buffer of LENGTH TYPE`, where `LENGTH` is a positive decimal integer literal and `TYPE` is an integer numeric scalar type, not `i1`.
- Record types are nominal top-level declarations with scalar fields only.
- Records are value aggregates. They lower by flattening their fields into existing scalar SSA values and function operands; v0.7 does not emit LLVM struct types or record storage.
- Local fixed-size buffers lower to stack-local `memref.alloca`; buffer parameters lower to memref function arguments.
- Scalar rebinding and record-field rebinding lower to SSA values, `scf.if` results, `scf.while` carried values, or `scf.for` iter_args.
- v0.7 has no heap allocation, pointer syntax, record returns, record buffers, nested records, record fields containing buffers, ABI/layout structs, padding, alignment, source-visible references, source-level `return`, `break`, `continue`, overloading, inference, or custom dialects.

## Record declarations

Records are top-level items:

```text
record Point:
  x: i32
  y: i32
```

Rules:

- Record names are case-sensitive and must be unique.
- Record names must not collide with scalar type names.
- A record must declare at least one field.
- Field names within a record must be unique.
- Fields may only use scalar source types: `i1`, signed integers, or unsigned integers.
- Buffer fields, nested record fields, dynamic fields, methods, layout attributes, packed structs, padding, and alignment are not supported.
- Record declarations may appear before or after phrases; semantic checking collects declarations before phrase bodies.

## Record construction, copying, and binding

A constructor initializes every field in declaration order:

```text
let p be Point with x be 3 and y be 4
let q: Point be Point with x be 1 and y be 2
let copy be p
```

Rules:

- The record type name must be declared.
- Fields must appear exactly once and in declaration order.
- Each initializer must type-check exactly as the declared field type; integer literals use the field type as the expected type.
- A local record binding is scoped like scalar `let` bindings. Branch-local and loop-local records do not escape.
- `let copy be p` copies the current field SSA values; later rebindings of `p` and `copy` are independent.

## Record parameters

Phrase holes may use record types:

```text
sum point p: Point gives i32:
  p.x plus p.y
```

Rules:

- Record actual arguments must be visible record bindings of the exact same nominal type.
- Inline record constructors are not phrase-call actuals in v0.7.
- No implicit record casts or structural typing exist.
- Record parameters are passed by value. Rebinding a field of a record parameter is local to the callee and does not mutate the caller.
- Record parameters may appear in `gives` and `does` phrases.
- Record parameters flatten in phrase-hole order, with each record expanded in declaration field order.

Example lowering shape:

```text
sum point p: Point gives i32:
  p.x plus p.y
```

```mlir
func.func @sum_point(%p_x: i32, %p_y: i32) -> i32 {
  %0 = arith.addi %p_x, %p_y : i32
  return %0 : i32
}
```

## Field access and rebinding

Fields are read with dot syntax and rebound with `becomes`:

```text
p.x
p.y becomes p.y plus 1
p becomes Point with x be 0 and y be 0
p becomes q
```

Rules:

- The left side of field access or field assignment must be a visible record binding.
- The field must exist on the record type.
- Field access has the field's scalar type and can be used anywhere a scalar expression is valid.
- Field rebinding updates the current SSA value for that local field; it is not memory mutation.
- Whole-record rebinding requires a record expression of the same nominal type and updates all fields in declaration order.
- Records themselves are not scalar expressions. Use a field such as `p.x` in scalar contexts.

## Records and control flow

Assigned record fields participate in existing SSA control-flow lowering:

- Step-level `if` emits one `scf.if` result for each assigned visible scalar binding and assigned visible record field.
- `while` and counted `for` loops carry assigned visible scalar bindings and assigned visible record fields.
- Deterministic order is visible scalar binding order first, then visible record binding order with fields in declaration order.
- A field assigned in only one branch yields the pre-branch value from the other branch.
- Records declared inside a branch or loop body do not escape that lexical block.

## Records and buffers

Records interoperate with buffers only through scalar fields:

```text
record Offset:
  index: i32
  value: i32

write offset offset: Offset into cells: buffer of 4 i32 does:
  cells at offset.index becomes offset.value
```

Rules:

- Record fields can be used as scalar buffer indices or scalar store values subject to existing type rules.
- Buffers may not have record element types.
- Records may not contain buffer fields.
- Record values cannot be stored in buffers, returned, addressed, or aliased.

## Body items and value blocks

A `gives` body is:

```text
body_item*
value_block
```

A `does` body is:

```text
body_item+
```

Body items are:

```text
let name be expression
let name: type be expression
let name be buffer of LENGTH TYPE filled with expression
name becomes expression
name.field becomes expression
name at index becomes expression
does_phrase_call
while condition:
  step
for name from start up to end:
  step
for name from start up to end by STEP:
  step
for each index name of buffer:
  step
if condition:
  step
otherwise:
  step
```

Value blocks remain scalar:

```text
expression
expression when condition
otherwise expression
```

Record return types are not supported in v0.7.

## MLIR lowering

The emitter uses only standard dialects:

```text
builtin.module
func
arith
scf
memref
```

Records produce no record-specific MLIR operations. Local construction binds field values in the compiler environment; field access returns the current field SSA value; field rebinding replaces that field's current SSA value. Record parameters and record arguments flatten to scalar function operands and scalar call operands.

The memref-capable LLVM lowering pipeline from v0.6 remains valid.

## Golden conformance suite

The minimum v0.7 quality bar is the exact-output golden suite in `tests/goldens`. Each `*.ins` source file must compile byte-for-byte to its sibling `*.mlir`; the unit test suite enforces this with unified diffs on mismatch.
