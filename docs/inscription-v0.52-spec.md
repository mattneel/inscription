# Inscription v0.52 build step groups and default step

Inscription v0.52 extends the executable package build script with aggregate group steps and an optional default step:

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

`build.ins` is not a package source module, is not included in source compilation, may import only the built-in `Build` module, and may not contain source-level `Test` declarations, externs, exports, or package source imports in v0.52.

## Minimal script

```inscription
Import Build.

To build package package: Build.Package.
Build.check package named "check".
Build.tests named "tests".
Build.static library named "library".
Build.c header named "header".
Build.interface json named "interface".
Build.group named "ci" with steps "check" and "tests".
Build.default step is "ci".
```

The required phrase is exactly:

```inscription
To build package package: Build.Package.
```

It is a does phrase, takes one opaque `Build.Package` parameter, and returns no value.

## Built-in Build API

The built-in `Build` module exists only while interpreting `build.ins`.

Supported v0.52 Build API requests are:

```inscription
Build.check package named "name".
Build.tests named "name".
Build.tests including dependencies named "name".
Build.group named "name" with steps "step_a" and "step_b".
Build.default step is "name".
Build.static library named "name".
Build.executable named "name".
Build.c header named "name".
Build.interface json named "name".
Build.llvm ir named "name".
Build.object named "name".
Build.mlir named "name".
Build.lowered mlir named "name".
```

Step names and group dependency names must be string literals in v0.52. They must be non-empty, use ASCII letters, digits, `_`, or `-`, start with a letter or `_`, and contain no path separators. Duplicate names are rejected.

The Build API records requested steps during interpretation. It does not run package commands immediately. Group steps depend on named steps in declaration order and may depend on other groups. Unknown dependencies, duplicate group dependencies, and cycles are rejected before execution. After interpretation, the build driver dispatches ordinary steps through existing package check, package test, or package artifact pipelines. Test failures stop later steps and make `inscription build` exit 1; package/compiler/tool diagnostics exit 2.

## Output paths and validation steps

Artifact steps write outputs under the package `build/` directory:

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

Outputs are overwritten. Group steps produce no artifact and only run their dependencies. `Build.check package` runs package validation without producing an artifact. `Build.tests` runs root package tests, and `Build.tests including dependencies` also runs dependency package tests. A package with no tests is still a successful test step and prints `no tests found`. Custom output paths in `build.ins` are not supported in v0.52. If a default step is declared, `inscription build PACKAGE_ROOT` runs that step. Without a default, a bare build runs all ordinary non-group steps in source order and skips groups unless they are requested explicitly.

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

When `--save-temps DIR` is used, artifact and test dependency steps write intermediates under `DIR/<step-name>/`. Group steps do not create their own temp directories. Check steps do not write temps unless future verification paths need them.

## Restrictions

v0.52 does not add arbitrary filesystem access, process spawning, networking, shell commands, source generation, target triples, cross compilation, custom toolchains, generic build graphs, custom output paths, package metadata field access, remote dependencies, registries, lockfiles, or dependency resolution changes.

`build.ins` and `comptime` share interpreter groundwork but are separate language/tooling surfaces. `package.ins` remains parse-only.
