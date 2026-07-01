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

Package builds route the same emit modes through `package.ins`:

```sh
PYTHONPATH=src python -m inscription package build path/to/package --emit llvm-ir -o package.ll
PYTHONPATH=src python -m inscription package build path/to/package --emit static-library -o libPackage.a
```

For package builds, library-like emits include the root module and exposed modules from the manifest.
