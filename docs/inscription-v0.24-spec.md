# Inscription v0.24 match specification

Inscription v0.24 keeps the v0.23 language and tooling surface and adds deterministic multi-way branching over booleans, integer scalars, and nominal enum values.

There are two forms:

```text
match expression:
  pattern gives expression
  otherwise gives expression
```

and

```text
match expression:
  pattern:
    step
  otherwise:
    step
```

Both forms evaluate the scrutinee once, test arms in source order, and select the first matching arm. `otherwise` is required in v0.24 and must be the final arm.

## Match expressions

A match expression produces a value:

```text
enum Mode: u8:
  idle be 0
  active be 1
  failed be 2

code for mode mode: Mode gives i32:
  match mode:
    Mode.idle gives 0
    Mode.active gives 7
    Mode.failed gives 255
    otherwise gives 1
```

Rules:

- The scrutinee type must be `i1`, an integer scalar type, or an enum type.
- Floating-point, record, buffer, array, and view scrutinees are rejected.
- Every pattern must have exactly the scrutinee type.
- Every arm result must have exactly the same type; no implicit casts are added.
- Result values may be scalar, enum, value record, or layout record values.
- Buffer, array, and view results are not supported.
- Record-valued match expressions use the existing flattened record-value lowering.

## Match step blocks

A match step block executes steps and does not produce a value:

```text
match mode:
  Mode.active:
    active becomes active plus 1
  Mode.failed:
    failed becomes failed plus 1
  otherwise:
    active becomes active
```

Rules:

- Step match scrutinee and pattern rules are the same as match expressions.
- Each arm body must contain at least one step.
- Bindings declared inside an arm are scoped to that arm and do not escape.
- Assignments to outer scalar bindings and record fields are carried through the generated control flow, like `if`/`otherwise` blocks.
- Match step blocks do not satisfy the final value expression required by a `gives` phrase.

## Patterns

Supported patterns are compile-time constants:

- enum cases such as `Mode.idle` and `Protocol.Mode.active`
- integer literals such as `0` or `255`
- integer constants such as `ping` or `Protocol.ping`
- boolean literals `true` and `false`
- enum constants such as `default_mode` or `Protocol.default_mode`

Duplicate patterns in one match are rejected when their compile-time values are statically identical. Float, record, buffer, array, view, range, wildcard, alternative, destructuring, and guarded patterns are not supported in v0.24.

## Enum matches

Enum scrutinees compare using the enum's underlying integer MLIR type. Duplicate enum case patterns are rejected. `otherwise` remains required even if all cases are listed; v0.24 does not add exhaustive matches without otherwise and does not warn about redundant otherwise arms.

## Compile-time evaluation

Match expressions are compile-time evaluable when the scrutinee and patterns are compile-time evaluable and the selected arm expression is compile-time evaluable. Unselected arms must type-check but do not need to be compile-time evaluable.

```text
constant code: i32 be match Mode.active:
  Mode.idle gives 0
  Mode.active gives 7
  otherwise gives 1

check code is equal to 7
```

Match step blocks are statements and are not compile-time evaluable.

## Lowering

Match expressions and step blocks lower to nested `scf.if` operations in source arm order. Comparisons use `arith.cmpi eq` over the scrutinee type; enum comparisons use the enum's underlying integer MLIR type. No switch dialect, jump table, custom dialect, or fallthrough semantics are added.

## Non-goals

v0.24 does not add tagged unions, payload variants, pattern destructuring, wildcard `_`, range patterns, OR patterns, guarded match arms, exhaustive matches without otherwise, fallthrough, switch/jump-table lowering, float matching, record matching, buffer/view/array matching, C header changes, interface JSON changes, macros, generics, overloading, or custom MLIR dialects.
