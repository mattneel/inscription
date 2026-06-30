# Artifacts

`compile --emit` controls output:

- `mlir`: frontend source MLIR, used by exact goldens.
- `lowered-mlir`: MLIR after the lowering pipeline.
- `llvm-ir`: LLVM IR from `mlir-translate`.
- `object`: one native object from LLVM 22 `llc`.
- `executable`: object plus clang link.
- `static-library`: deterministic archive from LLVM 22 `llvm-ar`.
- `interface-json`: deterministic integration metadata.
- `c-header`: conservative C prototypes for exported scalar phrases.

`--save-temps DIR` writes deterministic intermediate files for the selected pipeline.
