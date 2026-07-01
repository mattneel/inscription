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

Enums and matches make branching explicit. Exhaustive enum matches can omit `otherwise`:

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

Unions bind payloads only inside match arms:

```inscription,check
Union MaybeI32 has none; some value: i32.

To value or zero maybe: MaybeI32, giving i32.
Give match maybe:
MaybeI32.some with value gives value;
MaybeI32.none gives 0.

To main, giving i32.
Give value or zero MaybeI32.some with value be 7.
```

Use guarded arms when a payload value needs an extra condition. Guarded arms do not count as exhaustive coverage, so keep an unguarded fallback for the same variant when needed:

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

Use `field ignored` to match a union payload field without introducing a binding:

```inscription,check
Union Token has eof; operator symbol: u8 and precedence: u8.

To precedence token token: Token, giving i32.
Give match token:
Token.operator with symbol ignored and precedence as prec gives prec as i32;
anything gives 0.

To main, giving i32.
Give precedence token Token.operator with symbol be 43 and precedence be 10.
```
