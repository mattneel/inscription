# Enums

Enums are nominal integer-backed values with explicit case values.

```inscription,check
Enum Mode backed by u8 has idle be 0; active be 1.

To main, giving i32.
Give 7 when Mode.active is equal to Mode.active; otherwise 0.
```

Enums support equality, constants, buffers, arrays, views, records, layout fields, and explicit casts to/from their underlying integer. They do not support arithmetic or extern/export ABI.

Enum matches can omit `otherwise` when every declared case is covered:

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

Use `anything` or `otherwise` when matching externally sourced enum values that may have invalid underlying representations.
