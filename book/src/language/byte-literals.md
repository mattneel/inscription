# Byte Literals

`byte "A"` is a `u8` expression. `bytes "hello"` is a compile-time byte sequence used in byte storage contexts.

```inscription,check
To main, giving i32.
Let text be array of bytes "A\n".
Give (text at 0 as i32) plus (text at 1 as i32).
```

Supported escapes are `\\`, `\"`, `\n`, `\r`, `\t`, `\0`, and `\xNN`. Byte strings are not heap strings, pointers, globals, or null-terminated C strings.
