# Inscription v0.40 match guards and ignored union payload fields

Inscription v0.40 improves match expressiveness without changing the core lowering strategy or adding new pattern forms beyond guards and payload-field ignoring.

New behavior:

- Match expression arms may add lowercase `when` guards.
- Match step arms may add lowercase `when` guards.
- Guard conditions must have type `i1` and may use payload bindings introduced by the arm pattern.
- Guarded arms are tested in source order; if the base pattern matches but the guard is false, matching continues to the next arm.
- Guarded arms do not count toward exhaustiveness.
- Repeated base patterns are allowed when earlier repeated arms are guarded.
- An unguarded base pattern covers all remaining values for that base pattern; later same-base arms are unreachable.
- Union payload patterns may write `field ignored` to match a payload field without introducing a binding.

No range patterns, OR patterns, nested destructuring, record patterns, float patterns, guarded `otherwise`, guarded `anything`, fallthrough, jump-table lowering, new ownership features, or custom MLIR dialects are added.

## Match expression guards

A match expression arm can insert `when condition` between the pattern and `gives`:

```inscription
Union MaybeI32 has none; some value: i32.

To positive or zero maybe: MaybeI32, giving i32.
Give match maybe:
MaybeI32.some with value when value is greater than zero gives value;
MaybeI32.some with value gives 0;
MaybeI32.none gives 0.
```

The guard is evaluated only after the base pattern matches. Payload bindings are in scope for the guard. The guard must have type `i1`:

```text
match guard must have type i1, got i32
```

Guards may appear on enum, union, integer, and `i1` patterns. `otherwise` and `anything` remain unguarded catch-all forms in v0.40.

## Match step guards

A step-level `Match` arm can insert `when condition` between the pattern and the arm colon:

```inscription
Match token:
Token.integer with value when value is greater than 10: total becomes total plus (value as i32);
Token.integer with value: total becomes total;
anything: total becomes total.
```

Step-match guards use the same typing and scoping rules as expression guards. Existing ownership merging still applies to all possible runtime arms. If some guarded/fallback paths move an owned buffer and others leave it live, compilation fails with the existing partial-move diagnostic.

## Duplicate base patterns with guards

The base pattern identity ignores payload aliases, ignored payload fields, and guard expressions. For a union pattern, the base identity is the union variant; for an enum pattern, it is the enum case; for integer and boolean patterns, it is the literal value.

Multiple guarded arms with the same base pattern are allowed:

```inscription
Give match maybe:
MaybeI32.some with value when value is greater than 10 gives 10;
MaybeI32.some with value when value is greater than zero gives value;
MaybeI32.some with value gives 0;
MaybeI32.none gives 0.
```

An unguarded arm makes later same-base arms unreachable:

```text
match pattern MaybeI32.some is unreachable because an earlier unguarded arm already matches it
match has duplicate pattern MaybeI32.some
```

## Exhaustiveness and guards

Guarded arms do not prove exhaustiveness. Only unguarded direct enum cases, unguarded direct union variants, unguarded boolean literals, `anything`, and `otherwise` satisfy coverage.

```inscription
Enum Mode backed by u8 has idle be 0; active be 1.

To bad mode: Mode, giving i32.
Give match mode:
Mode.idle gives 0;
Mode.active when true gives 7.
```

This fails because `Mode.active` is guarded:

```text
match over Mode is missing case Mode.active
```

Integer matches still require `otherwise` or `anything`.

## Ignored union payload fields

Union payload patterns can ignore a field in declaration order:

```inscription
Union Token has eof; operator symbol: u8 and precedence: u8.

To precedence token token: Token, giving i32.
Give match token:
Token.operator with symbol ignored and precedence as prec gives prec as i32;
anything gives 0.
```

`field ignored` counts as matching the field but introduces no binding. This avoids shadowing visible names or binding unused values.

Rules:

- Ignored fields are valid only in union payload patterns.
- Ignored fields must appear in the declared payload order, like bound fields.
- `ignored` is not a value and is not a top-level wildcard pattern.
- `anything` remains the match wildcard for whole scrutinee values.
- Aliasing a payload field to `ignored` is rejected.

Diagnostics include:

```text
ignored may only be used in union payload patterns
ignored is reserved in union payload patterns
unknown binding symbol
```

## Guards with ignored fields

Guards may refer only to bindings that were actually introduced:

```inscription
Token.operator with symbol ignored and precedence as prec when prec is greater than 5 gives prec as i32
```

A guard cannot refer to an ignored field unless that name is otherwise visible in the enclosing scope.

## Lowering

No new MLIR dialects or operations are required. Guarded arms lower as source-order nested conditionals:

1. Test the base pattern.
2. If the pattern matches, evaluate the guard.
3. If the guard is true, take the arm.
4. Otherwise continue to the remaining arms.

This preserves the rule that a guard is evaluated only when its base pattern matches. `anything` and `otherwise` continue to lower as catch-all fallback arms.

## Non-goals

v0.40 does not add range patterns, OR patterns, nested destructuring, record patterns, float patterns, guarded catch-all arms, guard clauses outside match arms, fallthrough, switch/jump-table lowering, decision-tree optimization, new ownership features, or custom MLIR dialects.
