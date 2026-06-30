# Owned Buffers

Owned buffers are dynamic heap-backed mutable storage. They are local storage objects, not scalar values.

```inscription,check
To main, giving i32.
Let cells be owned buffer of 4 i32 filled with 1.
cells at 0 becomes 4.
Give cells at 0 plus length of cells.
```

They deallocate at lexical scope exit. Nested-scope declarations deallocate before the branch, loop body, or match arm yields. Returning `owned buffer of TYPE` moves the allocation to the caller.
