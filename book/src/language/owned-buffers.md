# Owned Buffers

Owned buffers are dynamic heap-backed mutable storage. They are storage objects, not scalar values.

```inscription,check
To main, giving i32.
Let cells be owned buffer of 4 i32 filled with 1.
cells at 0 becomes 4.
Give cells at 0 plus length of cells.
```

Owned buffers deallocate at lexical scope exit. Nested declarations deallocate before the branch, loop body, or match arm yields. Returning `owned buffer of TYPE` moves the allocation to the caller, and the caller owns cleanup after binding the result.

```inscription,check
To make cells count: i32, giving owned buffer of i32.
Let cells be owned buffer of count i32 filled with 3.
Give cells.

To main, giving i32.
Let cells be make cells 4.
Give length of cells.
```

## Consuming parameters and `move`

Normal phrases can take ownership of owned buffers with an owned-buffer parameter. The caller must pass the argument with explicit `move`; no implicit moves or copies are performed.

```inscription,check
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To main, giving i32.
Let cells be owned buffer of 7 i32 filled with 1.
Give consume cells move cells.
```

After `move cells`, the caller binding is consumed and cannot be used again. The callee owns the buffer and deallocates it at lexical-scope exit unless it returns it or moves it onward.

An owned-buffer parameter can be returned to forward ownership:

```inscription,check
To forward cells cells: owned buffer of i32, giving owned buffer of i32.
Give cells.

To main, giving i32.
Let cells be owned buffer of 4 i32 filled with 3.
Let forwarded be forward cells move cells.
Give length of forwarded.
```

Owned buffers can also be moved through a chain of consuming phrases.

```inscription,check
To fill cells cells: owned buffer of i32 with value: i32, giving owned buffer of i32.
For each index i of cells: cells at i becomes value.
Give cells.

To sum and drop cells cells: owned buffer of i32, giving i32.
Let total be 0.
For each index i of cells: total becomes total plus cells at i.
Give total.

To main, giving i32.
Let cells be owned buffer of 4 i32 filled with 0.
Let changed be fill cells move cells with 7.
Give sum and drop cells move changed.
```

v0.37 also supports owned temporary moves. A phrase call returning `owned buffer of TYPE` can be moved directly into a consuming parameter by writing `move (call)`.

```inscription,check
To make cells count: i32, giving owned buffer of i32.
Let cells be owned buffer of count i32 filled with 1.
Give cells.

To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To main, giving i32.
Give consume cells move (make cells 7).
```

The parentheses are required so the temporary ownership transfer is explicit. Direct temporaries are consumed immediately: they cannot be borrowed as views, used as scalar values, or moved from arbitrary expressions. Bind the returned buffer first when you need to inspect, borrow, or reuse it.

Consuming pipelines can nest these moves:

```inscription,check
To make cells count: i32, giving owned buffer of i32.
Let cells be owned buffer of count i32 filled with 0.
Give cells.

To fill cells cells: owned buffer of i32 with value: i32, giving owned buffer of i32.
For each index i of cells: cells at i becomes value.
Give cells.

To sum and drop cells cells: owned buffer of i32, giving i32.
Let total be 0.
For each index i of cells: total becomes total plus cells at i.
Give total.

To main, giving i32.
Give sum and drop cells move (fill cells move (make cells 4) with 7).
```

## Borrowing is still non-consuming

Passing an owned buffer to a `view of TYPE` parameter borrows the storage and does not require `move`.

```inscription,check
To sum view cells: view of i32, giving i32.
Let total be 0.
For each index i of cells: total becomes total plus cells at i.
Give total.

To main, giving i32.
Let cells be owned buffer of 4 i32 filled with 3.
Let total be sum view cells.
cells at 0 becomes 9.
Give total plus cells at 0.
```

## Move-aware branch and match control flow

Non-loop control flow may consume an outer owned buffer when every path leaves the binding in the same ownership state. If all branches move it, the binding is moved after the control-flow construct and the parent scope skips cleanup. If no branch moves it, it remains live.

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

Mixed branches are rejected because the caller would not know whether it still owns the buffer. Step-level `Match` uses the same all-arms rule. Loops stay conservative: moving an outer-scope owned buffer inside `While`, `For`, or `For each` is still rejected, but moving a loop-local owned buffer remains valid.

## Current restrictions

Owned buffers cannot be copied, rebound, stored in records or unions, exposed through extern/export ABI, or moved from fixed buffers, arrays, or views. Direct temporary moves are allowed only as `move (owned-buffer-returning call)` actuals to consuming parameters. All-path moves of outer-scope owned buffers are allowed through `When`/`Otherwise` and step-level `Match`. Mixed move/live branches are rejected. Loops still reject moving an outer-scope owned buffer; move a loop-local binding instead.
