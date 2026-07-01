# Build Scripts

Inscription v0.50 added an optional package build script named `build.ins`; v0.51 added package check and test steps; v0.52 added build step groups and a default step; v0.53 added dedicated mdBook documentation steps; v0.54 adds package-aware defaults for common artifact and documentation steps.

`package.ins` stays declarative package metadata, similar to `build.zig.zon`. `build.ins` is interpreted build logic, similar to a deliberately narrow first version of `build.zig`.

A compact workflow script can derive common artifact names from the package manifest while still using explicit check/test/group steps:

```inscription
Import Build.

To build package package: Build.Package.
Build.check package named "check".
Build.tests named "tests".
Build.static library for package.
Build.c header for package.
Build.interface json for package.
Build.book checked for package.
Build.group named "ci" with steps "check" and "tests" and "book-check".
Build.group named "release" with steps "ci" and "library" and "header" and "interface".
Build.default step is "ci".
```

A package with a runnable `main` can include an executable step:

```inscription
Import Build.

To build package package: Build.Package.
Build.check package named "check".
Build.tests named "tests".
Build.executable for package.
Build.book for package.
Build.group named "ci" with steps "check" and "tests" and "book".
Build.default step is "ci".
```

The required build phrase is a does phrase:

```inscription
To build package package: Build.Package.
```

The `Build.Package` value is opaque in v0.54. It is passed by the build driver, but scripts cannot inspect package fields yet. Package-aware `for package` steps use only the package name already known to the driver.

## Build API

The v0.54 Build API records named validation/test steps, package-aware artifact/documentation steps, aggregate groups, a default step, and the older named artifact/documentation forms:

```inscription,no-check
Build.check package named "check".
Build.tests named "tests".
Build.tests including dependencies named "all-tests".
Build.static library for package.
Build.executable for package.
Build.c header for package.
Build.interface json for package.
Build.llvm ir for package.
Build.object for package.
Build.mlir for package.
Build.lowered mlir for package.
Build.book for package.
Build.book checked for package.
Build.group named "ci" with steps "check" and "tests" and "book-check".
Build.default step is "ci".
Build.static library named "library".
Build.executable named "app".
Build.c header named "header".
Build.interface json named "interface".
Build.book checked named "docs".
```

Step names and group dependency names are metadata string literals, not normal source strings. They must be simple names: ASCII letters, digits, `_`, and `-`, starting with a letter or `_`. They cannot contain path separators.

Package-aware forms derive fixed step names. For example, `Build.static library for package.` creates a step named `library`; `Build.book checked for package.` creates a step named `book-check`. These names share the same namespace as named steps, so declaring both `Build.static library for package.` and `Build.static library named "library".` is a duplicate.

The script records steps during interpretation. The driver then calls the existing package check, package test, package build, or dedicated mdBook pipeline for each ordinary step. `Build.tests` runs root package tests; `Build.tests including dependencies` also runs dependency package tests. Group steps run their named dependencies in order, de-duplicate already successful dependencies during one invocation, and reject unknown dependencies or cycles before execution.

## Package-aware outputs

Package-aware artifact steps use the final segment of the package name for output files. `Package Acme.ProtocolTools.` uses `ProtocolTools`.

| Build API form | Step name | Output |
| --- | --- | --- |
| `Build.static library for package.` | `library` | `build/lib<PackageFinalName>.a` |
| `Build.executable for package.` | `app` | `build/<PackageFinalName>` |
| `Build.c header for package.` | `header` | `build/<PackageFinalName>.h` |
| `Build.interface json for package.` | `interface` | `build/<PackageFinalName>.json` |
| `Build.llvm ir for package.` | `llvm-ir` | `build/<PackageFinalName>.ll` |
| `Build.object for package.` | `object` | `build/<PackageFinalName>.o` |
| `Build.mlir for package.` | `mlir` | `build/<PackageFinalName>.mlir` |
| `Build.lowered mlir for package.` | `lowered-mlir` | `build/<PackageFinalName>.lowered.mlir` |
| `Build.book for package.` | `book` | `build/book/` |
| `Build.book checked for package.` | `book-check` | `build/book-check/` |

Named forms still use the literal step name for output files. For example, `Build.static library named "library".` writes `build/liblibrary.a`, and `Build.book checked named "docs".` writes `build/docs/`.

## Commands

List steps:

```sh
PYTHONPATH=src python -m inscription build path/to/package --list
```

Run one step or group:

```sh
PYTHONPATH=src python -m inscription build path/to/package ci
```

Run the default step, or all ordinary steps when no default exists:

```sh
PYTHONPATH=src python -m inscription build path/to/package
```

Artifact and documentation outputs go under `build/`; groups produce no artifact.

Book steps require `mdbook`; checked book steps also require `book/tools/check_book_examples.py`. They do not deploy documentation and do not use arbitrary commands. `--runtime-checks`, `--opt-level`, `-O0`, `-O1`, `-O2`, `--verify`, and `--save-temps DIR` are forwarded where applicable. Test and artifact save temps are grouped by dependency step name, for example `temps/tests/...` or `temps/library/Package.mlir`; group steps do not create their own temp directory. Check steps run package validation and only require MLIR tools when `--verify` is supplied.

## Boundaries

v0.54 build scripts are intentionally narrow. They cannot import package source modules, inspect arbitrary package metadata, call externs, spawn processes, read arbitrary files, use the network, generate source, choose custom output paths, deploy docs, choose alternate documentation generators, or define general build graphs. `package.ins` remains parse-only, and dependency resolution is unchanged.
