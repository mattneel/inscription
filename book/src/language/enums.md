# Enums

Enums are nominal integer-backed values with explicit case values.

```inscription,check
Enum Mode backed by u8 has idle be 0; active be 1.

To main, giving i32.
Give 7 when Mode.active is equal to Mode.active; otherwise 0.
```

Enums support equality, constants, buffers, arrays, views, records, layout fields, and explicit casts to/from their underlying integer. They do not support arithmetic or extern/export ABI in v0.36.
