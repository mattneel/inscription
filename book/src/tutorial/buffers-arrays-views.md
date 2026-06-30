# Buffers, Arrays, and Views

Fixed buffers are mutable local stack storage. Arrays are immutable local storage. Views borrow storage without taking ownership.

```inscription,check
To main, giving i32.
Let cells be buffer of 4 i32 containing 1, 2, 3, 4.
cells at 0 becomes 9.
Give cells at 0 plus cells at 1.
```

Arrays can be iterated and passed to view parameters:

```inscription,check
To sum cells cells: view of i32, giving i32.
Let total be 0.
For each index i of cells: total becomes total plus cells at i.
Give total.

To main, giving i32.
Let cells be array of 4 i32 containing 3, 3, 3, 3.
Give sum cells cells.
```

Byte literals make byte-oriented storage readable:

```inscription,check
To main, giving i32.
Let text be array of bytes "hello".
Give text at 1 as i32.
```
