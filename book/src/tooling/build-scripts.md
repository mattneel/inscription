# Build Scripts

Inscription v0.50 added an optional package build script named `build.ins`; v0.51 added package check and test steps; v0.52 added build step groups and a default step; v0.53 adds dedicated mdBook documentation steps.

`package.ins` stays declarative package metadata, similar to `build.zig.zon`. `build.ins` is interpreted build logic, similar to a deliberately narrow first version of `build.zig`.

A minimal workflow script imports the built-in `Build` module, records package validation/test steps, groups them, and selects that group as the default:

```inscription
Import Build.

To build package package: Build.Package.
Build.check package named "check".
Build.tests named "tests".
Build.book checked named "book".
Build.group named "ci" with steps "check" and "tests" and "book".
Build.default step is "ci".
```

Packages can request artifacts in the same script. A package with a runnable `main` can include an executable step:

```inscription
Import Build.

To build package package: Build.Package.
Build.check package named "check".
Build.tests named "tests".
Build.static library named "library".
Build.c header named "header".
Build.executable named "app".
Build.book named "book".
Build.group named "release" with steps "check" and "tests" and "library" and "header" and "book".
Build.default step is "release".
```

The required build phrase is a does phrase:

```inscription
To build package package: Build.Package.
```

The `Build.Package` value is opaque in v0.53. It is passed by the build driver, but scripts cannot inspect package fields yet.

## Build API

The v0.53 Build API records named validation/test steps, documentation steps, aggregate groups, a default step, and standard artifacts:

```inscription,no-check
Build.check package named "check".
Build.tests named "tests".
Build.tests including dependencies named "all-tests".
Build.book named "book".
Build.book checked named "book-check".
Build.group named "ci" with steps "check" and "tests" and "book".
Build.default step is "ci".
Build.static library named "library".
Build.executable named "app".
Build.c header named "header".
Build.interface json named "interface".
Build.llvm ir named "ir".
Build.object named "object".
Build.mlir named "source".
Build.lowered mlir named "lowered".
```

Step names and group dependency names are metadata string literals, not normal source strings. They must be simple names: ASCII letters, digits, `_`, and `-`, starting with a letter or `_`. They cannot contain path separators.

The script records steps during interpretation. The driver then calls the existing package check, package test, package build, or dedicated mdBook pipeline for each ordinary step. `Build.tests` runs root package tests; `Build.tests including dependencies` also runs dependency package tests. Group steps run their named dependencies in order, de-duplicate already successful dependencies during one invocation, and reject unknown dependencies or cycles before execution.

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

Artifact and documentation outputs go under `build/`; groups produce no artifact:

- static library: `build/lib<name>.a`
- executable: `build/<name>`
- C header: `build/<name>.h`
- interface JSON: `build/<name>.json`
- LLVM IR: `build/<name>.ll`
- object: `build/<name>.o`
- MLIR: `build/<name>.mlir`
- lowered MLIR: `build/<name>.lowered.mlir`
- mdBook documentation: `build/<name>/`

Book steps require `mdbook`; checked book steps also require `book/tools/check_book_examples.py`. They do not deploy documentation and do not use arbitrary commands. `--runtime-checks`, `--opt-level`, `-O0`, `-O1`, `-O2`, `--verify`, and `--save-temps DIR` are forwarded where applicable. Test and artifact save temps are grouped by dependency step name, for example `temps/tests/...` or `temps/library/Package.mlir`; group steps do not create their own temp directory. Check steps run package validation and only require MLIR tools when `--verify` is supplied.

## Boundaries

v0.53 build scripts are intentionally narrow. They cannot import package source modules, call externs, spawn processes, read arbitrary files, use the network, generate source, choose custom output paths, deploy docs, choose alternate documentation generators, or define general build graphs. `package.ins` remains parse-only, and dependency resolution is unchanged.
