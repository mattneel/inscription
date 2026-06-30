# Owned Buffer Builder

Owned-buffer-returning phrases transfer allocation ownership to the caller.

```inscription,check
To make indices count: i32, giving owned buffer of i32.
Let cells be owned buffer of count i32 filled with 0.
For each index i of cells: cells at i becomes i plus 1.
Give cells.

To main, giving i32.
Let cells be make indices 4.
Give (cells at 0) plus (cells at 1) plus (cells at 2) plus (cells at 3).
```
