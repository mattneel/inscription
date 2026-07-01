# C Headers

`compile --emit c-header` emits prototypes for exported scalar phrases.

```sh
PYTHONPATH=src python -m inscription compile source.ins --emit c-header -o source.h
```

Supported C header ABI types are `i32`, `u32`, `i64`, `u64`, `f32`, and `f64`. The generator rejects unsupported exported types and dotted/non-C exported symbols. It does not emit enum declarations, records, unions, buffers, views, owned buffers, or typedefs.

Documentation comments on exported phrases are emitted as plain C block comments before prototypes:

```inscription,format
/// Adds two counts.
/// Returns the sum.
To add counts left: i32 and right: i32, giving i32, exported as ins_add_counts.
Give left plus right.
```

```c
/*
 * Adds two counts.
 * Returns the sum.
 */
int32_t ins_add_counts(int32_t arg0, int32_t arg1);
```

Ordinary comments and extern documentation are not emitted in C headers. Documentation text is not parsed as Markdown; it is copied deterministically and made safe for C comments.

For package builds, the root package header intentionally omits dependency exports. Build each dependency package separately when you need that dependency's C header.
