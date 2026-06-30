# Buffers

Fixed buffers are mutable stack-local storage. Their length is compile-time known.

```inscription,check
To main, giving i32.
Let cells be buffer of 4 i32 filled with 0.
cells at 2 becomes 7.
Give cells at 2.
```

Buffers can be initialized with `filled with` or `containing`. Numeric and enum elements are supported; `i1`, records, unions, arrays, and views are not buffer element types.
