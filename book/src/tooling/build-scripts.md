# Build Scripts

Inscription v0.50 added an optional package build script named `build.ins`; v0.51 added package check and test steps; v0.52 added build step groups and a default step; v0.53 added dedicated mdBook documentation steps; v0.54 added package-aware defaults for common artifact and documentation steps; v0.55 adds the standard package workflow shortcut.

`package.ins` stays declarative package metadata, similar to `build.zig.zon`. `build.ins` is interpreted build logic, similar to a deliberately narrow first version of `build.zig`.

Most packages can start with the standard workflow:

```inscription
Import Build.

To build package package: Build.Package.
Build.standard package workflow.
```

The build driver expands that sentence into conventional validation, tests, release artifacts, groups, and a default CI step. If `book/book.toml` exists, the standard workflow also includes checked mdBook documentation.

The required build phrase is a does phrase:

```inscription
To build package package: Build.Package.
```

The `Build.Package` value is opaque in v0.55. It is passed by the build driver, but scripts cannot inspect package fields. Package-aware and standard workflow steps use only package metadata already known to the driver.

## Standard workflow

`Build.standard package workflow.` records these steps for every package:

```inscription,no-check
Build.check package named "check".
Build.tests named "tests".
Build.static library for package.
Build.c header for package.
Build.interface json for package.
```

If the package has `book/book.toml`, it also records:

```inscription,no-check
Build.book checked for package.
```

Then it records groups and the default step. With a book:

```inscription,no-check
Build.group named "ci" with steps "check" and "tests" and "book-check".
Build.group named "release" with steps "ci" and "library" and "header" and "interface".
Build.default step is "ci".
```

Without a book, `ci` contains only `check` and `tests`:

```inscription,no-check
Build.group named "ci" with steps "check" and "tests".
Build.group named "release" with steps "ci" and "library" and "header" and "interface".
Build.default step is "ci".
```

The standard workflow intentionally does not include an executable step in v0.55. Add `Build.executable for package.` explicitly when a package needs one.

Duplicate rules are unchanged. Because the standard workflow expands to ordinary steps, adding `Build.tests named "tests".` or another `ci` group after it is rejected as a duplicate.

## Build API

The v0.55 Build API records standard workflows, named validation/test steps, package-aware artifact/documentation steps, aggregate groups, a default step, and older named artifact/documentation forms:

```inscription,no-check
Build.standard package workflow.
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

List expanded steps:

```sh
PYTHONPATH=src python -m inscription build path/to/package --list
```

Run one step or group:

```sh
PYTHONPATH=src python -m inscription build path/to/package release
```

Run the default step, or all ordinary steps when no default exists:

```sh
PYTHONPATH=src python -m inscription build path/to/package
```

Artifact and documentation outputs go under `build/`; groups produce no artifact.

Book steps require `mdbook`; checked book steps also require `book/tools/check_book_examples.py`. They do not deploy documentation and do not use arbitrary commands. `--runtime-checks`, `--opt-level`, `-O0`, `-O1`, `-O2`, `--verify`, and `--save-temps DIR` are forwarded where applicable. Test and artifact save temps are grouped by dependency step name, for example `temps/tests/...` or `temps/library/Package.mlir`; group steps do not create their own temp directory. Check steps run package validation and only require MLIR tools when `--verify` is supplied.

## Boundaries

v0.55 build scripts are intentionally narrow. They cannot import package source modules, inspect arbitrary package metadata, call externs, spawn processes, read arbitrary files, use the network, generate source, choose custom output paths, deploy docs, choose alternate documentation generators, or define general build graphs. `package.ins` remains parse-only, and dependency resolution is unchanged.
