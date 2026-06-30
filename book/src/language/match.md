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

Patterns are constants, byte literals, enum cases, or union variants. `otherwise` is required and final.
