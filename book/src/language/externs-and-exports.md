# Externs and Exports

External phrases declare calls to host symbols:

```inscription,no-check
External population count of x: i32, giving i32, as llvm.ctpop.i32.
```

Exported phrases define public symbols:

```inscription,check
To add left: i32 and right: i32, giving i32, exported as ins_add.
Give left plus right.

To main, giving i32.
Give add 20 and 22.
```

Extern/export ABI is intentionally scalar-only. Records, unions, buffers, views, arrays, owned buffers, and enums are not exposed through the C/extern boundary in v0.34.
