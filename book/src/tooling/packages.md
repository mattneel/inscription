# Packages

Inscription v0.45 added a declarative package manifest named `package.ins`; v0.46 added package-aware artifact builds; v0.47 added local path dependencies; v0.50 added optional `build.ins` scripts, v0.51 added check/test steps, and v0.52 added groups/default steps; v0.53 added mdBook documentation steps, v0.54 added package-aware build defaults, v0.55 added standard package workflows, and v0.56 adds package init/new skeleton generation. The manifest is metadata, not executable build logic: think `build.zig.zon`, not `build.zig`. `build.ins` is the intentionally narrow interpreted build surface for named package workflow and artifact steps.

A package root contains `package.ins`, a source directory, and optionally a test directory:

```text
package.ins
src/ProtocolTools.ins
src/ProtocolTools/Checksum.ins
tests/checksum.ins
```

Create a starter package with the v0.56 skeleton generator:

```sh
PYTHONPATH=src python -m inscription package new hello --name Hello
PYTHONPATH=src python -m inscription package new protocol-tools --name ProtocolTools --with-book
PYTHONPATH=src python -m inscription package init . --name ExistingPkg
```

`package new PATH` creates a directory and initializes it. `package init [ROOT]` initializes an existing directory, creating it if needed. Generated packages contain formatter-clean `package.ins`, `build.ins`, `src/<RootModule>.ins`, and `tests/basic.ins`; `--with-book` also creates a minimal mdBook skeleton. The default template is a library with an exported `ins_add` sample phrase. `--executable` instead generates a root module with `main` returning `42` and a matching test. `--force` overwrites only files owned by the skeleton generator.

When `--name` is omitted, the package name is inferred from the path basename: `protocol-tools` becomes `ProtocolTools`, `hello_world` becomes `HelloWorld`, and invalid basenames require `--name`.

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

Depend on Checksums from path "../checksums".
```

Rules:

- `Package NAME.` is required and must be the first non-comment declaration.
- `Sources are in "src".` is required and sets the package module root.
- `Root module is ProtocolTools.` is required and must resolve under the sources directory.
- `Version "0.1.0".` is optional and must be `MAJOR.MINOR.PATCH`.
- `Tests are in "tests".` is optional.
- `Expose module ... .` is optional, repeatable package metadata.
- `Depend on Name from path "../package".` declares a local package dependency.
- Source and test paths are relative to the package root; absolute paths and `..` components are rejected for those layout paths. Dependency paths are also relative but may contain `..`.
- Manifests do not support `Import`, `To`, `Let`, `Test`, records, enums, unions, or arbitrary expressions.

Run a package check from the package root or pass the package path:

```sh
PYTHONPATH=src python -m inscription package check
PYTHONPATH=src python -m inscription package check path/to/package
PYTHONPATH=src python -m inscription package check path/to/package --verify
```

`package check` validates the manifest, dependency graph, source/test directories, root module, exposed modules, and type-checks the checked modules using `Sources` as the local module root. `--verify` also verifies source MLIR with the LLVM/MLIR toolchain.

Run package tests with:

```sh
PYTHONPATH=src python -m inscription package test path/to/package
PYTHONPATH=src python -m inscription package test path/to/package --list
PYTHONPATH=src python -m inscription package test path/to/package --filter checksum
PYTHONPATH=src python -m inscription package test path/to/package --include-dependencies
```

`package test` discovers `.ins` files under the declared tests directory and runs their `Test ... .` declarations. Test files can import source modules because the package command supplies the manifest source directory as the module root. Direct dependency root/exposed modules are also importable; dependency package tests run only when `--include-dependencies` is passed:

```inscription,no-check
Import ProtocolTools.Checksum.

Test checksum works.
Expect ProtocolTools.Checksum.identity 42 is equal to 42.
```

If a package has no test directory or no test files, the runner prints `no tests found` and exits successfully.

## Path dependencies

Path dependencies point at another local package root:

```inscription,manifest
Package App.

Sources are in "src".
Tests are in "tests".

Root module is App.

Expose module App.

Depend on Checksums from path "../checksums".
```

The target package must have a matching `Package Checksums.` declaration. Dependency cycles, duplicate dependency names, and the same path declared under different names are rejected deterministically. A dependent package may import only a direct dependency's root module and `Expose module ... .` entries. Transitive dependencies are not automatically visible; declare them directly if source imports them directly.


## Build scripts

A package may also contain an optional `build.ins` script:

```inscription
Import Build.

To build package package: Build.Package.
Build.standard package workflow.
```

Use `inscription build path/to/package --list` to list the script's expanded steps and default, `inscription build path/to/package release` to run the standard release group, `inscription build path/to/package library` to build one artifact step, or `inscription build path/to/package` to run the declared default step. v0.56 build scripts call only the built-in `Build` API for standard workflows, package check/test/build/group/book requests, and package-aware defaults; they cannot run shell commands, access arbitrary files, import package source modules, or customize output paths.

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

Library-like emits (`mlir`, `lowered-mlir`, `llvm-ir`, `object`, `static-library`, `interface-json`, and `c-header`) include the root module plus every `Expose module ... .` entry, even if an exposed module is not imported by the root. Imported dependency modules are compiled as needed. Executable emits compile the root module normally and require a runnable `main`.

Package interface JSON includes a top-level `package` object with manifest metadata and direct dependency metadata. Package C headers include exported scalar phrases from the root package root/exposed modules and preserve exported phrase documentation comments; dependency exports are intentionally omitted from the root package header. Build the dependency package separately when you need its header. `--save-temps DIR` writes deterministic package intermediates such as `ProtocolTools.mlir`, `ProtocolTools.lowered.mlir`, `ProtocolTools.ll`, and `ProtocolTools.o`.

Remote dependencies, registries, lockfiles, version solving, target triples, build profiles, custom output paths, arbitrary filesystem/process/network access, and general build graph scripting remain future work. See [Build Scripts](build-scripts.md) for the v0.56 package/build surface.
