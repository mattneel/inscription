# C Headers

`compile --emit c-header` emits prototypes for exported scalar phrases.

```sh
PYTHONPATH=src python -m inscription compile source.ins --emit c-header -o source.h
```

Supported C header ABI types are `i32`, `u32`, `i64`, `u64`, `f32`, and `f64`. The generator rejects unsupported exported types and dotted/non-C exported symbols. It does not emit enum declarations, records, unions, buffers, views, owned buffers, or typedefs.
