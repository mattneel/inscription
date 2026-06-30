# Phrases

A returning phrase has typed holes and a return type:

```inscription,check
To add left: i32 and right: i32, giving i32.
Give left plus right.

To main, giving i32.
Give add 20 and 22.
```

A does phrase has no return type and is used as a step:

```inscription,check
To fill cell cells: buffer of 1 i32 with value: i32.
cells at 0 becomes value.

To main, giving i32.
Let cells be buffer of 1 i32 filled with 0.
fill cell cells with 7.
Give cells at 0.
```

Phrase calls mirror phrase headers. Holes are filled by the source words around them, which keeps call sites readable while preserving deterministic parsing.
