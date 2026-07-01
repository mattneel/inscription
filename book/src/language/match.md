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

Integer matches still require `otherwise` or `anything`; Inscription v0.39 does not try to prove integer-domain exhaustiveness.

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

`anything` must be the final arm and cannot appear in the same match as `otherwise`. It introduces no payload bindings.

Exhaustive enum and union matches without a catch-all assume valid enum representations and valid union tags. Add `otherwise` or `anything` when matching externally sourced values where invalid representations must be handled explicitly.
