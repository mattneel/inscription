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

For package builds, library-like emits include the root module and exposed modules from the manifest. `inscription build` reads `build.ins` and routes named Build API steps through the same package artifact emit modes, using deterministic outputs under the package `build/` directory.

## Release bundles

`inscription package release` assembles the common integration artifacts into a deterministic directory:

```sh
PYTHONPATH=src python -m inscription package release path/to/package
PYTHONPATH=src python -m inscription package release path/to/package --include-executable --clean
```

The bundle always includes `package.ins`, `release.json`, `interface.json`, `include/<Package>.h`, and `lib/lib<Package>.a`. `--include-executable` adds `bin/<Package>` when the root module has a runnable `main`; `--include-book` adds mdBook output under `docs/` when `book/book.toml` exists. The metadata uses relative paths only and intentionally omits timestamps, hostnames, git hashes, signatures, checksums, and upload/publishing data in v0.59.
