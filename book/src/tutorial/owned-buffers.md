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

Owned buffers can also start with explicit data. `containing` stores each element in order, while `owned buffer of bytes "..."` creates mutable heap-backed byte storage.

```inscription,check
To main, giving i32.
Let cells be owned buffer of 4 i32 containing 1, 2, 3, 4.
Let text be owned buffer of bytes "hello".
text at 0 becomes byte "H".
Give cells at 0 plus length of text.
```

Use an explicit copy when you want mutable owned storage initialized from an array, buffer, view, or another owned buffer:

```inscription,check
To main, giving i32.
Let numbers be array of 4 i32 containing 1, 2, 3, 4.
Let copy be owned buffer copied from numbers.
copy at 0 becomes 9.
Give copy at 0 plus numbers at 0.
```

The source remains live after the copy. This is the only copy operation for owned buffers; assignment and phrase arguments still do not copy automatically.

Reusable code can either borrow owned buffers through `view of TYPE` parameters or consume them through `owned buffer of TYPE` parameters. Consuming calls require explicit `move`, and the source binding cannot be used afterward. Owned buffers still cannot be implicitly copied, rebound, or exposed through extern/export ABI.


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

If a helper returns an owned buffer that is consumed immediately, move the parenthesized call directly instead of creating a temporary binding:

```inscription,check
To make cells count: i32, giving owned buffer of i32.
Let cells be owned buffer of count i32 filled with 3.
Give cells.

To sum and drop cells cells: owned buffer of i32, giving i32.
Let total be 0.
For each index i of cells: total becomes total plus cells at i.
Give total.

To main, giving i32.
Give sum and drop cells move (make cells 4).
```


Branch and match steps are move-aware. This is valid because both branches move `cells`:

```inscription,check
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To branch move all flag: i1, giving i32.
Let cells be owned buffer of 4 i32 filled with 1.
Let result be 0.
When flag, result becomes consume cells move cells.
Otherwise, result becomes consume cells move cells.
Give result.

To main, giving i32.
Give branch move all true.
```

A branch that moves `cells` on only some paths is rejected. Loops still cannot move outer-scope owned buffers, although loop-local buffers can be moved inside each iteration.
