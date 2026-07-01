# Inscription v0.50 `build.ins` MVP

Inscription v0.50 adds the first executable package build script:

```text
build.ins
```

`package.ins` remains declarative package metadata, like `build.zig.zon`. `build.ins` is interpreted build logic, like a deliberately tiny first step toward `build.zig`-style scripts.

## File role

A package may contain:

```text
package.ins
build.ins
src/
tests/
```

`build.ins` is optional. `inscription package build` continues to work without it. The top-level `inscription build` command requires it and reports:

```text
build script not found at build.ins
```

`build.ins` is not a package source module, is not included in source compilation, may import only the built-in `Build` module, and may not contain tests, externs, exports, or package source imports in v0.50.

## Minimal script

```inscription
Import Build.

To build package package: Build.Package.
Build.static library named "library".
Build.c header named "header".
Build.interface json named "interface".
```

The required phrase is exactly:

```inscription
To build package package: Build.Package.
```

It is a does phrase, takes one opaque `Build.Package` parameter, and returns no value.

## Built-in Build API

The built-in `Build` module exists only while interpreting `build.ins`.

Supported v0.50 artifact requests are:

```inscription
Build.static library named "name".
Build.executable named "name".
Build.c header named "name".
Build.interface json named "name".
Build.llvm ir named "name".
Build.object named "name".
Build.mlir named "name".
Build.lowered mlir named "name".
```

Artifact names must be string literals in v0.50. They must be non-empty, use ASCII letters, digits, `_`, or `-`, start with a letter or `_`, and contain no path separators. Duplicate names are rejected.

The Build API records requested artifacts during interpretation. It does not compile immediately. After interpretation, the build driver dispatches each recorded step through the existing package build artifact pipeline.

## Output paths

`inscription build` writes outputs under the package `build/` directory:

| Request | Output |
| --- | --- |
| `Build.static library named "library".` | `build/liblibrary.a` |
| `Build.executable named "app".` | `build/app` |
| `Build.c header named "header".` | `build/header.h` |
| `Build.interface json named "interface".` | `build/interface.json` |
| `Build.llvm ir named "ir".` | `build/ir.ll` |
| `Build.object named "object".` | `build/object.o` |
| `Build.mlir named "source".` | `build/source.mlir` |
| `Build.lowered mlir named "lowered".` | `build/lowered.lowered.mlir` |

Outputs are overwritten. Custom output paths in `build.ins` are not supported in v0.50.

## CLI

```sh
inscription build [PACKAGE_ROOT]
inscription build [PACKAGE_ROOT] STEP
inscription build [PACKAGE_ROOT] --list
```

Options mirror package build where applicable:

- `--runtime-checks`
- `--opt-level none|basic|aggressive`
- `-O0`, `-O1`, `-O2`
- `--verify`
- `--save-temps DIR`

When `--save-temps DIR` is used, each step writes intermediates under `DIR/<step-name>/`.

## Restrictions

v0.50 does not add arbitrary filesystem access, process spawning, networking, shell commands, source generation, target triples, cross compilation, custom toolchains, generic build graphs, custom output paths, package metadata field access, remote dependencies, registries, lockfiles, or dependency resolution changes.

`build.ins` and `comptime` share interpreter groundwork but are separate language/tooling surfaces. `package.ins` remains parse-only.
