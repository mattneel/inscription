# Packages

Inscription v0.45 added a declarative package manifest named `package.ins`; v0.46 adds package-aware artifact builds from that manifest. It is metadata, not executable build logic: think `build.zig.zon`, not `build.zig`. A future `build.ins` could be an executable build surface, but these package sprints deliberately do not add scripts, dependencies, registries, lockfiles, variables, or conditionals.

A package root contains `package.ins`, a source directory, and optionally a test directory:

```text
package.ins
src/ProtocolTools.ins
src/ProtocolTools/Checksum.ins
tests/checksum.ins
```

A manifest uses Inscription prose-punctuation syntax with a restricted grammar:

```inscription,manifest
//! Package manifest for ProtocolTools.

Package ProtocolTools.

Version "0.1.0".

Sources are in "src".
Tests are in "tests".

Root module is ProtocolTools.

Expose module ProtocolTools.
Expose module ProtocolTools.Checksum.
```

Rules:

- `Package NAME.` is required and must be the first non-comment declaration.
- `Sources are in "src".` is required and sets the package module root.
- `Root module is ProtocolTools.` is required and must resolve under the sources directory.
- `Version "0.1.0".` is optional and must be `MAJOR.MINOR.PATCH` in v0.45.
- `Tests are in "tests".` is optional.
- `Expose module ... .` is optional, repeatable package metadata.
- Paths are relative to the package root; absolute paths and `..` components are rejected.
- Manifests do not support `Import`, `To`, `Let`, `Test`, records, enums, unions, or arbitrary expressions.

Run a package check from the package root or pass the package path:

```sh
PYTHONPATH=src python -m inscription package check
PYTHONPATH=src python -m inscription package check path/to/package
PYTHONPATH=src python -m inscription package check path/to/package --verify
```

`package check` validates the manifest, source/test directories, root module, exposed modules, and type-checks the checked modules using `Sources` as the module root. `--verify` also verifies source MLIR with the LLVM/MLIR toolchain.

Run package tests with:

```sh
PYTHONPATH=src python -m inscription package test path/to/package
PYTHONPATH=src python -m inscription package test path/to/package --list
PYTHONPATH=src python -m inscription package test path/to/package --filter checksum
```

`package test` discovers `.ins` files under the declared tests directory and runs their `Test ... .` declarations. Test files can import source modules because the package command supplies the manifest source directory as the module root:

```inscription,no-check
Import ProtocolTools.Checksum.

Test checksum works.
Expect ProtocolTools.Checksum.identity 42 is equal to 42.
```

If a package has no test directory or no test files, the runner prints `no tests found` and exits successfully.


## Package builds

Build package artifacts with:

```sh
PYTHONPATH=src python -m inscription package build path/to/package
PYTHONPATH=src python -m inscription package build path/to/package --emit static-library -o build/libProtocolTools.a
PYTHONPATH=src python -m inscription package build path/to/package --emit c-header -o build/ProtocolTools.h
PYTHONPATH=src python -m inscription package build path/to/package --emit interface-json -o build/ProtocolTools.json
PYTHONPATH=src python -m inscription package build path/to/package --emit executable -o build/app
```

The default package build emits a static library at `build/lib<Package>.a`, using the final segment of a dotted package name and preserving casing. `package build` validates `package.ins`, uses `Sources are in ...` as the module root, and builds the manifest `Root module`.

Library-like emits (`mlir`, `lowered-mlir`, `llvm-ir`, `object`, `static-library`, `interface-json`, and `c-header`) include the root module plus every `Expose module ... .` entry, even if an exposed module is not imported by the root. Executable emits compile the root module normally and require a runnable `main`.

Package interface JSON includes a top-level `package` object with manifest metadata. Package C headers include exported scalar phrases from root/exposed modules and preserve exported phrase documentation comments. `--save-temps DIR` writes deterministic package intermediates such as `ProtocolTools.mlir`, `ProtocolTools.lowered.mlir`, `ProtocolTools.ll`, and `ProtocolTools.o`.

`build.ins`, dependencies, registries, lockfiles, target triples, build profiles, and arbitrary package scripts remain future work.
