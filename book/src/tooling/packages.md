# Packages

Inscription v0.45 adds a declarative package manifest named `package.ins`. It is metadata, not executable build logic: think `build.zig.zon`, not `build.zig`. A future `build.ins` could be an executable build surface, but v0.45 deliberately does not add scripts, dependencies, registries, lockfiles, variables, or conditionals.

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
