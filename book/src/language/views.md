# Views

Views borrow existing storage. A view tracks a base, a start offset, and a length.

```inscription,check
To main, giving i32.
Let values be array of 5 i32 containing 1, 2, 3, 4, 5.
Let middle be view of values from 1 for 3.
Give middle at 0 plus middle at 2.
```

Views derived from arrays are read-only. Views derived from buffers or owned buffers are writable. Views do not own storage and cannot be returned.
