# Constants and Checks

Top-level constants are compile-time scalar values:

```inscription,check
Constant answer: i32 be 42.

Check answer is equal to 42.

To main, giving i32.
Give answer.
```

`Check` can also appear in phrase bodies when the expression is compile-time evaluable. Checks emit no MLIR. They are for source invariants, not runtime validation.
