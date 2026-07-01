# Constants and Checks

Top-level constants are compile-time scalar values:

```inscription,check
Constant answer: i32 be 42.

Check answer is equal to 42.

To main, giving i32.
Give answer.
```

`Check` can also appear in phrase bodies when the expression is compile-time evaluable. Checks emit no MLIR. They are for source invariants, not runtime validation.

`comptime` phrase calls can produce scalar and enum constant values by executing pure phrases during compilation:

```inscription,check
To double x: i32, giving i32.
Give x plus x.

Constant eight: i32 be comptime double 4.

Check eight is equal to 8.
```

See [Comptime](comptime.md) for the supported pure subset and non-goals.
