# Inscription v0.38 move-aware control flow for owned buffers

Inscription v0.38 extends the owned-buffer ownership checker. It keeps the v0.37 syntax and lowering model, but allows safe moves of outer-scope owned buffers inside non-loop control flow when every path through the construct leaves the buffer in the same ownership state.

No new syntax, MLIR dialects, runtime behavior, extern/export ABI, copying, rebinding, implicit moves, manual deallocation, or loop-sensitive move analysis are added.

## Ownership states

Each visible owned buffer is either `live` or `moved`.

- A live owned buffer is deallocated at lexical-scope exit unless it is later moved or returned.
- A moved owned buffer cannot be used, moved again, viewed, indexed, stored through, returned by name, or deallocated by the old owner.
- Scope cleanup skips moved buffers.
- `move name` and `move (owned-buffer-returning call)` keep their v0.36/v0.37 meanings.

## When/Otherwise merge rule

For a `When`/`Otherwise` step, every owned buffer visible before the construct must have the same state at the end of both branches.

Valid: both branches move `cells`, so `cells` is moved after the branch and the parent scope does not deallocate it.

```inscription
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To branch move all flag: i1, giving i32.
Let cells be owned buffer of 4 i32 filled with 1.
Let result be 0.
When flag, result becomes consume cells move cells.
Otherwise, result becomes consume cells move cells.
Give result.
```

Invalid: only one branch moves `cells`.

```text
owned buffer cells is moved in some branches but not all
```

If neither branch moves the buffer, it remains live and is cleaned up normally.

## Match step merge rule

Step-level `Match` uses the same rule across every pattern arm and the required `otherwise` arm.

```inscription
Enum Mode backed by u8 has left be 0; right be 1.

To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To match move all mode: Mode, giving i32.
Let cells be owned buffer of 5 i32 filled with 1.
Let result be 0.
Match mode:
Mode.left: result becomes consume cells move cells;
Mode.right: result becomes consume cells move cells;
otherwise: result becomes consume cells move cells.
Give result.
```

Invalid mixed match arms diagnose:

```text
owned buffer cells is moved in some match arms but not all
```

Arm-local owned buffers remain local to their arm and do not participate in parent ownership merging.

## Nested non-loop control flow

Nested `When`/`Otherwise` and step-level `Match` constructs compose. An outer branch sees the merged ownership state of nested branch-like constructs. If every complete path moves an outer buffer, that buffer is moved after the outer construct.

```inscription
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To nested branch move left: i1 and right: i1, giving i32.
Let cells be owned buffer of 6 i32 filled with 1.
Let result be 0.
When left: When right: result becomes consume cells move cells; Otherwise: result becomes consume cells move cells.
Otherwise: result becomes consume cells move cells.
Give result.
```

Mixed nested paths still reject with the branch partial-move diagnostic.

## Loops remain conservative

Moving an owned buffer declared outside a `While`, `For`, or `For each` loop remains invalid in v0.38:

```text
owned buffer cells may not be moved from an outer scope inside a loop in v0.38
```

This avoids consuming the same binding during the first iteration and using it again in later iterations. Loop-sensitive move analysis is future work.

Loop-local owned buffers can still be moved because each iteration owns a fresh binding:

```inscription
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To loop local move still, giving i32.
Let total be 0.
For i from 0 up to 3: Let cells be owned buffer of 2 i32 filled with i; total becomes total plus consume cells move cells.
Give total.
```

## Use after all-path move

After all branches or match arms move a binding, later use is rejected:

```text
owned buffer cells was moved and cannot be used
```

This includes `length of cells`, `cells at i`, stores, view creation, a second `move cells`, and owned-buffer return by name.

## Lowering and artifacts

No MLIR shape changes are required beyond cleanup decisions. Branches that move a buffer already pass the memref/length pair to the consuming callee. v0.38 updates ownership state so parent lexical cleanup skips buffers that every control-flow path moved. Live buffers continue to be deallocated normally.

## Non-goals

v0.38 does not add implicit moves, copying, rebinding, moving outer bindings inside loops, loop-sensitive dataflow, early returns, partial move/reinitialization, owned-buffer extern/export ABI, manual deallocation, C headers for owned buffers, pointers/references, or custom MLIR dialects.
