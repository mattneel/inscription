# Checksum

A checksum over byte views is a small example of array borrowing and explicit casts.

```inscription,check
To checksum bytes: view of u8, giving i32.
Let total be 0.
For each index i of bytes: total becomes total plus (bytes at i as i32).
Give total.

To main, giving i32.
Let payload be array of bytes "ABC".
Give checksum payload.
```
