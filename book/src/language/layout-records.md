# Layout Records

Layout records are value records with deterministic byte metadata. They support `size of`, `alignment of`, `offset of`, `read`, and `write`.

```inscription,check
Packed layout record Word has value: u16.

To main, giving i32.
Let bytes be buffer of 2 u8 filled with 0.
Let word be Word with value be 42.
Write word into bytes at 0.
Let copy be read Word from bytes at 0.
Give copy.value as i32.
```

Serialization is little-endian. Natural layout records include padding; packed layout records have alignment 1 and consecutive fields.
