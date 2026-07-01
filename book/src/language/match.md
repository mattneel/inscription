# Match

Match expressions produce values:

```inscription,check
Enum Mode backed by u8 has idle be 0; active be 1.

To code mode: Mode, giving i32.
Give match mode:
Mode.idle gives 0;
Mode.active gives 7;
otherwise gives 1.

To main, giving i32.
Give code Mode.active.
```

Match step blocks execute steps and carry assignments:

```inscription,check
Enum Mode backed by u8 has idle be 0; active be 1.

To count modes modes: view of Mode, giving i32.
Let active be 0.
For each index i of modes:
Match modes at i:
Mode.active: active becomes active plus 1;
otherwise: active becomes active.
Give active.

To main, giving i32.
Let modes be array of 2 Mode containing Mode.idle, Mode.active.
Give count modes modes.
```

Patterns are constants, byte literals, enum cases, union variants, or the wildcard `anything`.

## Exhaustive matches

Enum, union, and boolean matches can omit `otherwise` when all cases are covered:

```inscription,check
Enum Mode backed by u8 has idle be 0; active be 1; failed be 2.

To code for mode mode: Mode, giving i32.
Give match mode:
Mode.idle gives 0;
Mode.active gives 7;
Mode.failed gives 255.

To main, giving i32.
Give code for mode Mode.active.
```

```inscription,check
Union MaybeI32 has none; some value: i32.

To value or zero maybe: MaybeI32, giving i32.
Give match maybe:
MaybeI32.none gives 0;
MaybeI32.some with value gives value.

To main, giving i32.
Give value or zero MaybeI32.some with value be 42.
```

Integer matches still require `otherwise` or `anything`; Inscription does not try to prove integer-domain exhaustiveness.

## Wildcard pattern

Use `anything` as an explicit catch-all:

```inscription,check
Enum Mode backed by u8 has idle be 0; active be 1; failed be 2.

To fallback code mode: Mode, giving i32.
Give match mode:
Mode.active gives 7;
anything gives 1.

To main, giving i32.
Give fallback code Mode.failed.
```

`anything` must be the final arm and cannot appear in the same match as `otherwise`. It introduces no payload bindings and cannot have a guard.

Exhaustive enum and union matches without a catch-all assume valid enum representations and valid union tags. Add `otherwise` or `anything` when matching externally sourced values where invalid representations must be handled explicitly.

## Match guards

Match arms can use lowercase `when` between the pattern and the result/body:

```inscription,check
Union MaybeI32 has none; some value: i32.

To positive or zero maybe: MaybeI32, giving i32.
Give match maybe:
MaybeI32.some with value when value is greater than zero gives value;
MaybeI32.some with value gives 0;
MaybeI32.none gives 0.

To main, giving i32.
Give positive or zero MaybeI32.some with value be 7.
```

A guard is evaluated only after the base pattern matches. It must have type `i1`, may use payload bindings from the pattern, and may use other visible bindings.

Guarded arms do not count toward exhaustiveness. This match still needs an unguarded `Mode.active`, `anything`, or `otherwise` arm:

```inscription,format
Enum Mode backed by u8 has idle be 0; active be 1.

To guarded mode mode: Mode and enabled: i1, giving i32.
Give match mode:
Mode.active when enabled gives 7;
Mode.active gives 3;
Mode.idle gives 0.
```

Repeated base patterns are allowed when earlier repeated arms are guarded. Once an unguarded arm for a base pattern appears, later arms for the same base pattern are unreachable.

Step matches support the same guard form:

```inscription,check
Union MaybeI32 has none; some value: i32.

To choose maybe maybe: MaybeI32, giving i32.
Let result be 0.
Match maybe:
MaybeI32.some with value when value is greater than zero: result becomes value;
MaybeI32.some with value: result becomes 0;
MaybeI32.none: result becomes 0.
Give result.

To main, giving i32.
Give choose maybe MaybeI32.some with value be 5.
```

Step-match ownership merging still applies across all possible guarded and unguarded paths.

## Pattern alternatives

Use lowercase `or` to share one result/body across several non-binding patterns:

```inscription,check
Enum Mode backed by u8 has idle be 0; active be 1; failed be 2.

To code for mode mode: Mode, giving i32.
Give match mode:
Mode.idle or Mode.failed gives 0;
Mode.active gives 7.

To main, giving i32.
Give code for mode Mode.active.
```

Alternatives can cover enum cases, booleans, integer literals, byte literals, integer ranges, and payload-free union variants. A guard after alternatives applies to the whole group.

Alternatives do not bind payloads in v0.41. Use separate arms for payload variants:

```inscription,check
Union Door has open; closed; locked code: u8.

To door code door: Door, giving i32.
Give match door:
Door.open or Door.closed gives 1;
Door.locked with code gives code as i32.

To main, giving i32.
Give door code Door.closed.
```

`anything` remains a standalone final catch-all and cannot appear inside an `or` group.

## Integer ranges

Use lowercase `through` for inclusive integer scalar ranges:

```inscription,check
To classify x: i32, giving i32.
Give match x:
0 through 9 gives 1;
10 through 19 gives 2;
anything gives 3.

To main, giving i32.
Give classify 12.
```

Byte ranges are `u8` ranges:

```inscription,check
To classify byte b: u8, giving i32.
Give match b:
byte "0" through byte "9" gives 1;
byte "A" through byte "F" gives 2;
byte "a" through byte "f" gives 2;
anything gives 0.

To main, giving i32.
Give classify byte byte "C".
```

Ranges can be alternatives and can be guarded:

```inscription,check
To classify byte b: u8 and enabled: i1, giving i32.
Give match b:
byte "0" through byte "9" or byte "A" through byte "F" when enabled gives 7;
anything gives 1.

To main, giving i32.
Give classify byte byte "8" and true.
```

Range endpoints must be compile-time evaluable and have the scrutinee type. Integer ranges do not make integer matches exhaustive; keep `anything` or `otherwise` for integer scrutinees.
