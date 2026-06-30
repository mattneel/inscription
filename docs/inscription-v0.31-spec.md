# Inscription v0.31 owned buffer return and transfer specification

Inscription v0.31 keeps the v0.30 nested-scope owned-buffer cleanup model and adds ordinary `gives` phrases that return owned dynamic buffers by value. Returned owned buffers transfer ownership from callee to caller: the callee returns the allocation without deallocating it, and the caller deallocates the returned binding at its lexical-scope exit.

The feature is intentionally narrow. Owned buffers remain non-copyable, non-rebindable storage values. They are not phrase parameters, cannot be stored in records/unions/buffers/arrays/views, cannot cross extern/export ABI boundaries, and cannot be returned from `main` for `run`.

## Owned buffer return types

```text
make cells count: i32 gives owned buffer of i32:
  let cells be owned buffer of count i32 filled with 1
  cells

make bytes count: i32 gives owned buffer of u8:
  let bytes be owned buffer of count u8 filled with 0
  bytes
```

Rules:

- The return type form is `owned buffer of TYPE`.
- The return type records only the element type; returned owned buffers are dynamically sized.
- A returned owned buffer carries a dynamic memref plus an `i32` logical length.
- Return element types may be integer numeric types, `f32`/`f64`, or enum types.
- Return element types may not be `i1`, records, layout records, unions, buffers, arrays, views, or owned buffers.
- Aliases may be used when they resolve to a valid owned-buffer element type.
- `run` rejects a root `main` that returns an owned buffer because executable `main` must return an integer scalar.

Deterministic diagnostics include:

```text
owned buffer element type must be numeric or enum, got i1
owned buffer element type may not be a union type in v0.31
program main must return an integer scalar, got owned buffer of i32
```

## Returning local owned buffers

The final value of an owned-buffer-returning phrase may be a visible owned buffer binding whose element type matches the phrase return type:

```text
make ones count: i32 gives owned buffer of i32:
  let cells be owned buffer of count i32 filled with 1
  cells
```

Rules:

- Returning a visible owned buffer moves it out of the callee.
- The returned owned buffer is marked consumed for cleanup purposes and is not deallocated by the callee.
- Other live owned buffers in the callee are still deallocated before return in reverse lexical declaration order.
- The final value may not be a scalar expression, fixed buffer, array, view, record, union, guarded value block, or match expression.
- The returned owned buffer must be visible at the final value site; normal lexical scope rules prevent branch-, loop-, and match-arm-local buffers from escaping.

Example cleanup behavior:

```text
make selected count: i32 gives owned buffer of i32:
  let scratch be owned buffer of count i32 filled with 9
  let cells be owned buffer of count i32 filled with 1
  cells at 0 becomes scratch at 0
  cells
```

`scratch` is deallocated in the callee. `cells` is returned and deallocated by the caller.

## Forwarding owned-buffer returns

The final value may also be a direct call to another owned-buffer-returning phrase:

```text
make ones count: i32 gives owned buffer of i32:
  let cells be owned buffer of count i32 filled with 1
  cells

forward ones count: i32 gives owned buffer of i32:
  make ones count
```

Rules:

- The called phrase's owned-buffer element type must match the enclosing phrase return type exactly.
- Ownership is forwarded to the caller without an extra allocation or copy.
- Any local owned buffers in the forwarding phrase are deallocated before returning the forwarded buffer.

## Binding returned owned buffers

Owned-buffer-returning calls may be bound with `let`:

```text
main gives i32:
  let cells be make ones 7
  length of cells
```

Rules:

- The `let` binding becomes a local owned buffer binding.
- The caller owns the returned buffer and deallocates it at the binding's lexical-scope exit.
- The binding supports `length of`, indexing, stores, `for each index`, `view of`, layout read/write when the element type is `u8`, and passing to `view of TYPE` parameters.
- Returned owned buffers can be bound in nested step scopes; v0.30 lexical cleanup deallocates them at the end of that scope.
- Owned-buffer-returning calls may not be used as standalone steps.
- Owned-buffer-returning calls may not be used as ordinary scalar/record/union expressions.
- Owned-buffer-returning calls may not be passed directly as view arguments in v0.31; bind them first so ownership has a lexical scope.

Deterministic diagnostics include:

```text
phrase `make cells _` returns owned buffer of i32 and cannot be used as a step
owned buffer result from `make cells _` must be bound before it can be passed as a view
owned buffer cells cannot be used as a value
```

## Unsupported owned-buffer return forms

v0.31 keeps ownership transfer through control-flow expressions out of scope.

Unsupported final values for `gives owned buffer of TYPE` include:

```text
make small when flag
otherwise make large
```

and:

```text
match mode:
  Mode.small gives make small
  otherwise gives make large
```

Required diagnostics:

```text
guarded owned buffer returns are not supported in v0.31
match expressions returning owned buffers are not supported in v0.31
```

Users can write helper phrases or branch outside the owned-buffer-returning phrase until explicit move paths through conditional multi-result control flow are designed.

## Existing owned buffer behavior

All v0.30 owned-buffer binding and cleanup rules remain active:

```text
let cells be owned buffer of n i32 filled with 0
let bytes be owned buffer of count u8 filled with byte "\0"
let weights be owned buffer of n f64 filled with 1.5
let modes be owned buffer of n Mode filled with Mode.idle
```

Rules:

- The length expression must have type `i32`; compile-time lengths must be at least `1`.
- With `--runtime-checks`, dynamic lengths are checked to be at least `1`.
- Element types may be integer numeric types, `f32`/`f64`, or enums, and may not be `i1`, records, layout records, unions, buffers, arrays, or views.
- Owned buffers may be declared in phrase bodies, branches, loops, for-each bodies, match step arms, and nested combinations of those blocks.
- Owned buffers are deallocated at lexical-scope exit in reverse declaration order.
- Views derived from owned buffers are non-owning and share the owned root storage identity.
- Cleanup is not guaranteed if a runtime assertion aborts.

## Borrowing returned owned buffers

Returned owned buffers can be borrowed after binding:

```text
sum view cells: view of i32 gives i32:
  let total be 0
  for each index i of cells:
    total becomes total plus cells at i
  total

main gives i32:
  let cells be make ones 4
  sum view cells
```

Rules:

- Passing a bound owned buffer to `view of TYPE` creates a full writable view when the receiving phrase can write views and the element type matches exactly.
- Same-root alias rejection applies to returned owned buffers and views derived from them.
- Passing a returned owned buffer to a fixed-size `buffer of N TYPE` parameter is invalid.
- Owned buffer parameters are not supported in v0.31.

## Runtime checks

The existing `--runtime-checks` behavior applies to returned owned buffers after binding:

- dynamic owned-buffer lengths in the allocating phrase,
- dynamic loads and stores through the returned buffer,
- dynamic views over the returned buffer,
- dynamic layout reads/writes through returned `u8` buffers.

Static errors remain compile-time diagnostics.

## MLIR lowering

No new MLIR dialects are introduced. v0.31 continues using `builtin.module`, `func`, `arith`, `scf`, `memref`, and `cf` when assertions are emitted.

A phrase returning `owned buffer of T` lowers to two function results:

```text
func.func @make_cells(%count: i32) -> (memref<?xi32>, i32) {
  %count_index = arith.index_cast %count : i32 to index
  %cells = memref.alloc(%count_index) : memref<?xi32>
  ...
  return %cells, %count : memref<?xi32>, i32
}
```

Rules:

- The memref result owns the heap allocation.
- The `i32` result is the logical length.
- A caller binding receives both results and records them as a live owned buffer.
- Caller lexical cleanup emits `memref.dealloc` for the returned memref.
- Callee lexical cleanup skips the owned buffer marked as moved-to-return and deallocates all other live owned buffers.
- Direct forwarding returns the callee call results after local cleanup.

## Extern/export, interface JSON, and C headers

Owned buffers remain unsupported in extern/export ABI:

```text
export make cells count: i32 gives owned buffer of i32 as ins_make_cells:
  ...

extern host make cells count: i32 gives owned buffer of i32 as host_make_cells
```

Required diagnostics:

```text
exported phrase return types must be primitive scalar types, got owned buffer of i32
extern phrase return types must be primitive scalar types, got owned buffer of i32
```

Interface JSON and C headers do not expose owned-buffer return metadata because exported phrases cannot use owned buffers.

## Non-goals

v0.31 does not add owned buffer parameters, owned buffer exports/externs, owned buffer C ABI, copying, rebinding, ownership transfer between local variables, manual deallocation, move syntax, guarded owned-buffer returns, match-expression owned-buffer returns, owned buffer fields in records/unions, owned buffer arrays, owned buffer constants, C headers for owned buffers, pointer/reference types, or custom MLIR dialects.
