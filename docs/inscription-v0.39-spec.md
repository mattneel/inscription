# Inscription v0.39 exhaustive match and wildcard patterns

Inscription v0.39 improves match ergonomics and safety without changing lowering strategy or adding new runtime behavior.

New behavior:

- `anything` is a wildcard match pattern.
- Enum matches may omit `otherwise` when every enum case is covered.
- Union matches may omit `otherwise` when every union variant is covered.
- Boolean matches may omit `otherwise` when both `true` and `false` are covered.
- Integer matches still require `otherwise` or `anything`.
- The compiler reports deterministic diagnostics for missing enum cases, missing union variants, missing boolean cases, and unreachable arms after catch-all patterns.

No range patterns, OR patterns, nested destructuring, record patterns, guard clauses, fallthrough, switch lowering, jump tables, or custom MLIR dialects are added.

## Wildcard pattern

`anything` matches any value of the scrutinee type and introduces no bindings.

```inscription
Enum Mode backed by u8 has idle be 0; active be 1; failed be 2.

To code for mode mode: Mode, giving i32.
Give match mode:
Mode.active gives 7;
anything gives 1.
```

`anything` is valid in match expressions and step-level `Match` blocks over the existing supported scrutinee types: `i1`, integer scalars, enums, and unions.

Rules:

- `anything` must be the final arm.
- `anything` and `otherwise` are alternatives; a single match cannot contain both.
- `anything` behaves like `otherwise` for lowering and ownership merging.
- `anything` is not an expression and may only appear in match pattern position.

Diagnostics include:

```text
anything must be the final match arm
match cannot contain both anything and otherwise
anything may only be used as a match pattern
```

## Exhaustive enum matches

An enum match may omit `otherwise` when every declared case is matched directly.

```inscription
Enum Mode backed by u8 has idle be 0; active be 1; failed be 2.

To code for mode mode: Mode, giving i32.
Give match mode:
Mode.idle gives 0;
Mode.active gives 7;
Mode.failed gives 255.
```

If a case is missing and no catch-all arm exists, compilation fails in declaration order:

```text
match over Mode is missing case Mode.failed
match over Mode is missing cases Mode.active, Mode.failed
```

`otherwise` and `anything` still satisfy exhaustiveness. Duplicate pattern diagnostics remain unchanged.

## Exhaustive union matches

A union match may omit `otherwise` when every declared variant is matched directly.

```inscription
Union MaybeI32 has none; some value: i32.

To value or zero maybe: MaybeI32, giving i32.
Give match maybe:
MaybeI32.none gives 0;
MaybeI32.some with value gives value.
```

Payload variants keep the existing payload-pattern rules. If a variant is missing and no catch-all arm exists, compilation fails:

```text
match over MaybeI32 is missing variant MaybeI32.none
```

## Boolean matches

A match over `i1` may omit `otherwise` when both boolean literals are present:

```inscription
To bool code flag: i1, giving i32.
Give match flag:
true gives 7;
false gives 3.
```

If one case is missing and no catch-all arm exists, compilation fails:

```text
match over i1 is missing case false
```

## Integer matches still need a catch-all

Inscription v0.39 does not implement integer-domain exhaustiveness, even for small integer types. Integer matches require `otherwise` or `anything`.

```text
match over i32 requires otherwise or anything
```

## Lowering and invalid representations

No new lowering strategy is required. Exhaustive matches without a catch-all still lower through the existing nested `scf.if` shape. The final explicit arm is used as the fallback branch.

If an enum value has an invalid underlying representation and an exhaustive enum match has no `otherwise` or `anything`, behavior is undefined in v0.39. This can matter for enum values read from raw layout bytes. Use `anything` or `otherwise` when invalid external representations must be handled explicitly.

## Match step ownership

Step-level `Match` blocks without `otherwise` participate in the v0.38 move-state merge when they are exhaustive. If every explicit arm moves an outer owned buffer, that binding is moved after the match. If some exhaustive arms move the buffer and others leave it live, the existing partial-move diagnostic applies.

`anything` behaves like `otherwise` for ownership merging.

## Non-goals

v0.39 does not add range patterns, OR patterns, nested destructuring, record patterns, float patterns, guard clauses, fallthrough, decision-tree optimization, switch/jump-table lowering, runtime unreachable traps, new ownership features, or custom MLIR dialects.
