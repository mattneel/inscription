# Records, Enums, and Unions

Records are nominal value aggregates. Enums are nominal integer-backed values. Unions are tagged values with named payloads.

```inscription,check
Record Point has x: i32; y: i32.

To score point p: Point, giving i32.
Give p.x plus p.y.

To main, giving i32.
Let p be Point with x be 3 and y be 4.
Give score point p.
```

Enums and matches make branching explicit:

```inscription,check
Enum Mode backed by u8 has idle be 0; active be 1; failed be 2.

To code for mode mode: Mode, giving i32.
Give match mode:
Mode.idle gives 0;
Mode.active gives 7;
Mode.failed gives 255;
otherwise gives 1.

To main, giving i32.
Give code for mode Mode.active.
```

Unions bind payloads only inside match arms:

```inscription,check
Union MaybeI32 has none; some value: i32.

To value or zero maybe: MaybeI32, giving i32.
Give match maybe:
MaybeI32.some with value gives value;
otherwise gives 0.

To main, giving i32.
Give value or zero MaybeI32.some with value be 7.
```
