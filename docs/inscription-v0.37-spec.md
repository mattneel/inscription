# Inscription v0.37 owned temporary moves and consuming pipelines

Inscription v0.37 extends explicit owned-buffer moves with direct owned temporary moves. A phrase call returning `owned buffer of TYPE` may be moved directly into an owned-buffer parameter with `move (call)`, enabling consuming pipelines without implicit moves, temporary borrowing, copying, owned-buffer extern/export ABI, manual deallocation, or new MLIR dialects.

All previous owned-buffer behavior remains unchanged:

- locally allocated owned buffers are mutable heap-backed storage;
- owned buffers deallocate at lexical-scope exit;
- owned-buffer returns transfer ownership to the caller;
- borrowed `view of TYPE` parameters do not consume ownership;
- owned buffers are still non-copyable and non-rebindable.

## Owned-buffer parameter types

Normal `To` phrases may now declare holes with owned-buffer parameter types:

```inscription
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.
```

Parameter element types may be integer numeric types, `f32`, `f64`, or enum types. They may not be `i1`, records, layout records, unions, buffers, arrays, views, or nested owned buffers.

An owned-buffer parameter is an owned binding in the callee. It supports `length of`, indexing, stores, for-each iteration, views, layout read/write when the element type is `u8`, borrowing as `view of TYPE`, moving onward, and returning when the phrase return type matches.

Owned-buffer parameters are available only on normal phrases. They remain invalid on `External` phrases and exported phrases because the extern/C ABI remains primitive-scalar-only:

```inscription
To consume cells cells: owned buffer of i32, giving i32, exported as ins_consume.
Give length of cells.
```

```text
exported phrase parameters must be primitive scalar types, got owned buffer of i32
```

## Explicit `move` arguments

Passing an owned buffer to an owned-buffer parameter requires an explicit `move` actual:

```inscription
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To main, giving i32.
Let cells be owned buffer of 7 i32 filled with 1.
Give consume cells move cells.
```

Rules:

- `move name` is valid only as a phrase actual for a hole whose type is `owned buffer of TYPE`.
- `name` must be a visible live owned-buffer binding.
- The element type must match exactly.
- The caller binding is consumed after the move and cannot be used again.
- The caller skips lexical cleanup for the moved binding.
- The callee owns the buffer and deallocates it unless it moves it onward or returns it.
- No implicit moves are performed.

Borrowing remains unchanged. Passing an owned buffer to a `view of TYPE` parameter does not consume ownership and does not use `move`:

```inscription
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

A `move` actual sent to a view parameter is rejected:

```text
move may only be used as an argument to an owned buffer parameter
```

## Use-after-move

After `move cells`, later source uses of `cells` in that lexical scope are invalid:

```inscription
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To bad, giving i32.
Let cells be owned buffer of 4 i32 filled with 1.
Let n be consume cells move cells.
Give length of cells.
```

```text
owned buffer cells was moved and cannot be used
```

Double moves and stores through moved bindings produce the same use-after-move diagnostic.

## Returning and forwarding parameters

An owned-buffer parameter may be returned from an owned-buffer-returning phrase:

```inscription
To forward cells cells: owned buffer of i32, giving owned buffer of i32.
Give cells.

To main, giving i32.
Let cells be owned buffer of 4 i32 filled with 3.
Let forwarded be forward cells move cells.
Give length of forwarded.
```

The callee does not deallocate the returned parameter. The caller receives a fresh live owned binding and deallocates it at lexical-scope exit unless it moves it again.

Owned buffers can be moved through chains of consuming phrases:

```inscription
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

## Conservative nested-flow rule

v0.37 preserves the conservative v0.36 nested-flow rule and deliberately avoids branch-sensitive partial-move analysis. A binding declared in the same current lexical block may be moved. A binding from an outer lexical block may not be moved inside nested `When`/`Otherwise`, `While`, `For`, `For each`, or `Match` control.

Valid local move inside a branch:

```inscription
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To nested local move flag: i1, giving i32.
Let result be 0.
When flag: Let cells be owned buffer of 4 i32 filled with 1; result becomes consume cells move cells.
Otherwise: result becomes 1.
Give result.
```

Invalid partial move of an outer binding:

```inscription
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To bad flag: i1, giving i32.
Let cells be owned buffer of 4 i32 filled with 1.
Let result be 0.
When flag, result becomes consume cells move cells.
Otherwise, result becomes 0.
Give result.
```

```text
owned buffer cells may be moved only in unconditional flow in v0.36
```

This same rule rejects moving an outer owned buffer inside loops and match arms.

## Direct temporaries

Owned-buffer-returning phrase calls may be moved directly into consuming parameters when the call is parenthesized:

```inscription
To make cells count: i32, giving owned buffer of i32.
Let cells be owned buffer of count i32 filled with 1.
Give cells.

To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To main, giving i32.
Give consume cells move (make cells 4).
```

The callee receives the returned buffer as an owned parameter and deallocates or forwards it as usual. Without parentheses, the compiler rejects the move source with `owned buffer phrase call in move argument must be parenthesized`.

Direct temporaries remain narrow: they cannot be borrowed as views, used as scalar values, returned as `Give move (...)`, or moved from arbitrary expressions.

## Lowering

Owned-buffer parameters lower using the same representation as owned-buffer returns:

```text
memref<?xT>, i32
```

The memref is the dynamic allocation and the `i32` is the logical length. The callee binds the pair as owned storage. At callee lexical-scope exit, live owned parameters are deallocated with `memref.dealloc`. Parameters moved to another consuming call or returned are skipped by that cleanup. Caller cleanup likewise skips bindings moved to calls.

## Non-goals

v0.37 does not add implicit moves, copying, rebinding, direct temporary borrowing, owned-buffer extern/export ABI, owned-buffer fields, owned-buffer arrays, manual `free`, reference counting, branch-sensitive partial move analysis, moving outer bindings inside nested control, C headers for owned buffers, pointer/reference types, or custom MLIR dialects.
