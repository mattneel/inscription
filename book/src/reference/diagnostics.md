# Diagnostics

Inscription diagnostics are deterministic and intentionally direct. They report parser errors, type errors, unsupported ABI usage, storage misuse, ownership misuse, and toolchain failures.

Common categories:

- Missing punctuation, such as a sentence without a final period.
- Unknown bindings or types.
- Type mismatches with no implicit casts.
- Unsupported storage/value contexts, such as using an owned buffer as a scalar.
- Extern/export ABI rejections for non-primitive scalar types.
- LLVM/MLIR toolchain discovery errors.

Negative tests in `tests/test_inscription.py` are the best executable catalog of exact diagnostic wording.
