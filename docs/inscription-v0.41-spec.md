# Inscription v0.41 pattern alternatives and integer ranges

Inscription v0.41 improves match ergonomics without changing the lowering strategy. It adds pattern alternatives with lowercase `or` and inclusive integer scalar range patterns with lowercase `through`.

New behavior:

- Match expression and match step arms may combine non-binding patterns with `or`.
- Alternatives may include enum cases, boolean literals, integer literals, byte literals, integer ranges, and payload-free union variants.
- Alternatives may have one guard after the full pattern group.
- Inclusive `lower through upper` range patterns are valid for integer scalar scrutinees.
- Byte literals are valid endpoints for `u8` ranges.
- Enum/union/bool exhaustiveness counts unguarded alternatives.
- Integer matches still require `otherwise` or `anything` even when ranges appear complete.
- Overlapping unguarded integer literals/ranges are rejected deterministically.

No nested destructuring, record patterns, float patterns, enum ranges, union ranges, payload-binding alternatives, fallthrough, jump-table lowering, new ownership features, or custom MLIR dialects are added.

## Pattern alternatives

A match arm can combine alternatives with `or`:

```inscription
Enum Mode backed by u8 has idle be 0; active be 1; failed be 2.

To code for mode mode: Mode, giving i32.
Give match mode:
Mode.idle or Mode.failed gives 0;
Mode.active gives 7.
```

The arm matches when any alternative matches. A guard after the group applies to the whole group:

```inscription
Give match b:
byte "0" through byte "9" or byte "A" through byte "F" when enabled gives 7;
anything gives 1.
```

`otherwise` is not a pattern and cannot appear in alternatives. `anything` remains a standalone final catch-all and is rejected inside alternatives:

```text
anything cannot be used in a pattern alternative
```

Union alternatives are intentionally narrow in v0.41. Payload-free variants are allowed:

```inscription
Union Door has open; closed; locked code: u8.

Give match door:
Door.open or Door.closed gives 1;
Door.locked with code gives code as i32.
```

Variants that bind payloads cannot appear in alternatives:

```text
pattern alternatives cannot bind union payloads in v0.41
```

## Integer range patterns

Integer scalar matches can use inclusive ranges:

```inscription
To classify x: i32, giving i32.
Give match x:
0 through 9 gives 1;
10 through 19 gives 2;
anything gives 3.
```

Range endpoints must be compile-time evaluable integer expressions with the scrutinee type. The lower bound must be less than or equal to the upper bound according to the source type's signedness.

Byte ranges are ordinary `u8` ranges:

```inscription
To classify byte b: u8, giving i32.
Give match b:
byte "0" through byte "9" gives 1;
byte "A" through byte "F" gives 2;
byte "a" through byte "f" gives 2;
anything gives 0.
```

Range patterns are rejected for enum, union, boolean, float, record, and storage scrutinees:

```text
range patterns require integer scalar scrutinee, got Mode
```

## Duplicate and overlap diagnostics

The compiler rejects duplicate alternatives and unreachable overlaps after an earlier unguarded pattern:

```text
match has duplicate pattern 1
match pattern 5 is unreachable because an earlier range already matches it
match range 5 through 15 overlaps earlier range 0 through 9
```

Guarded arms do not make later identical or overlapping arms unreachable because the guard may fail:

```inscription
To ok x: i32 and enabled: i1, giving i32.
Give match x:
0 through 9 when enabled gives 1;
5 gives 2;
anything gives 0.
```

## Exhaustiveness

Unguarded alternatives count toward enum, union, and boolean exhaustiveness:

```inscription
Give match mode:
Mode.idle or Mode.failed gives 0;
Mode.active gives 7.
```

`true or false` is exhaustive for `i1` when unguarded. Payload-free union alternatives count for their variants; payload variants still use ordinary variant arms.

Guarded arms do not prove exhaustiveness. Integer literal/range coverage never proves integer exhaustiveness in v0.41, even for `u8`:

```text
match over u8 requires otherwise or anything
```

## Lowering

Alternatives lower to OR-combined pattern tests. Integer ranges lower to lower-bound and upper-bound comparisons combined with `arith.andi`; signed integer ranges use signed comparisons and unsigned integer ranges use unsigned comparisons. Guards retain the v0.40 source-order nested conditional lowering.

## Formatter and highlighter

The formatter preserves single spaces around `or` and `through` and keeps guards after the full pattern group. The highlighter recognizes `through` as a pattern keyword; `or` already exists as the boolean/operator word.
