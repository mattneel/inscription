# Owned Buffers

Owned buffers are heap-backed local mutable storage. They deallocate automatically at lexical-scope exit.

```inscription,check
To owned sum n: i32, giving i32.
Let cells be owned buffer of n i32 filled with 1.
Let total be 0.
For each index i of cells: total becomes total plus cells at i.
Give total.

To main, giving i32.
Give owned sum 7.
```

Returning an owned buffer moves ownership to the caller. The caller must bind it before use.

```inscription,check
To make cells count: i32, giving owned buffer of i32.
Let cells be owned buffer of count i32 filled with 3.
Give cells.

To main, giving i32.
Let cells be make cells 4.
Give length of cells.
```

Reusable code can either borrow owned buffers through `view of TYPE` parameters or consume them through `owned buffer of TYPE` parameters. Consuming calls require explicit `move`, and the source binding cannot be used afterward. Owned buffers still cannot be copied, rebound, or exposed through extern/export ABI.


Consuming calls are useful when a helper should take responsibility for cleanup or return the buffer onward:

```inscription,check
To sum and drop cells cells: owned buffer of i32, giving i32.
Let total be 0.
For each index i of cells: total becomes total plus cells at i.
Give total.

To main, giving i32.
Let cells be owned buffer of 4 i32 filled with 3.
Give sum and drop cells move cells.
```
