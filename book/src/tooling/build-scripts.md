# Build Scripts

Inscription v0.50 added an optional package build script named `build.ins`; v0.51 adds package check and test steps to that script surface.

`package.ins` stays declarative package metadata, similar to `build.zig.zon`. `build.ins` is interpreted build logic, similar to a deliberately narrow first version of `build.zig`.

A minimal script imports the built-in `Build` module and defines the required build phrase:

```inscription
Import Build.

To build package package: Build.Package.
Build.check package named "check".
Build.tests named "tests".
Build.static library named "library".
Build.c header named "header".
Build.interface json named "interface".
```

Packages with a runnable `main` can request an executable too:

```inscription
Import Build.

To build package package: Build.Package.
Build.executable named "app".
Build.check package named "check".
Build.tests named "tests".
Build.static library named "library".
Build.c header named "header".
```

The required build phrase is a does phrase:

```inscription
To build package package: Build.Package.
```

The `Build.Package` value is opaque in v0.51. It is passed by the build driver, but scripts cannot inspect package fields yet.

## Build API

The v0.51 Build API records named validation/test steps and standard artifacts:

```inscription,no-check
Build.check package named "check".
Build.tests named "tests".
Build.tests including dependencies named "all-tests".
Build.static library named "library".
Build.executable named "app".
Build.c header named "header".
Build.interface json named "interface".
Build.llvm ir named "ir".
Build.object named "object".
Build.mlir named "source".
Build.lowered mlir named "lowered".
```

Step names are metadata string literals, not normal source strings. They must be simple names: ASCII letters, digits, `_`, and `-`, starting with a letter or `_`. They cannot contain path separators.

The script records steps during interpretation. The driver then calls the existing package check, package test, or package build pipeline for each step. `Build.tests` runs root package tests; `Build.tests including dependencies` also runs dependency package tests.

## Commands

List steps:

```sh
PYTHONPATH=src python -m inscription build path/to/package --list
```

Run one step:

```sh
PYTHONPATH=src python -m inscription build path/to/package library
```

Build every recorded step:

```sh
PYTHONPATH=src python -m inscription build path/to/package
```

Artifact outputs go under `build/`:

- static library: `build/lib<name>.a`
- executable: `build/<name>`
- C header: `build/<name>.h`
- interface JSON: `build/<name>.json`
- LLVM IR: `build/<name>.ll`
- object: `build/<name>.o`
- MLIR: `build/<name>.mlir`
- lowered MLIR: `build/<name>.lowered.mlir`

`--runtime-checks`, `--opt-level`, `-O0`, `-O1`, `-O2`, `--verify`, and `--save-temps DIR` are forwarded where applicable. Test save temps are grouped by step name, for example `temps/tests/...`; artifact save temps use the same step grouping, for example `temps/library/Package.mlir`. Check steps run package validation and only require MLIR tools when `--verify` is supplied.

## Boundaries

v0.51 build scripts are intentionally narrow. They cannot import package source modules, call externs, spawn processes, read arbitrary files, use the network, generate source, choose custom output paths, or define general build graphs. `package.ins` remains parse-only, and dependency resolution is unchanged.
