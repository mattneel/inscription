# Inscription v0.54 package-aware build defaults

Inscription v0.54 extends the restricted `build.ins` Build API with convenience forms that derive step names and artifact output names from the current package metadata:

```inscription
Build.static library for package.
Build.c header for package.
Build.interface json for package.
Build.executable for package.
Build.book checked for package.
```

The feature keeps `package.ins` declarative and keeps `build.ins` sandboxed. Scripts still cannot inspect arbitrary package metadata fields, build dynamic strings, choose custom output paths, run shell commands, access arbitrary files, or generate source.

## Package-aware Build API additions

The v0.54 Build API includes all v0.53 named steps plus these package-aware forms:

```inscription
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
```

Each form is valid only in `build.ins` and records one build step. The `for package` word refers to the canonical build phrase parameter:

```inscription
To build package package: Build.Package.
```

In v0.54 the canonical parameter name is required for package-aware forms. A renamed parameter is rejected with a deterministic diagnostic.

## Derived step names and outputs

Package-aware forms share the same build-step namespace as named forms. Duplicate names are rejected before execution.

| Build API form | Derived step name | Output |
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

`<PackageFinalName>` is the final segment of the manifest package name with casing preserved. For example:

```inscription
Package Acme.ProtocolTools.
```

uses `ProtocolTools`, so `Build.static library for package.` writes `build/libProtocolTools.a`.

## Named steps still work

The existing named APIs remain valid and continue to name outputs directly:

```inscription
Build.static library named "library".
Build.c header named "header".
Build.book checked named "docs".
```

For example, `Build.static library named "library".` writes `build/liblibrary.a`, while `Build.static library for package.` creates a step named `library` that writes `build/lib<PackageFinalName>.a`.

## Groups and defaults

Package-aware steps participate in groups and defaults like any other step:

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

`inscription build --list` lists the derived step names normally. `--save-temps` uses those step names for compiler/test temp subdirectories, such as `temps/library/`.

## Diagnostics

Duplicate derived and named step names are rejected:

```inscription
Build.static library for package.
Build.static library named "library".
```

emits:

```text
build step library is already defined
```

A non-canonical package-aware form such as `Build.static library for other.` is rejected:

```text
package-aware build steps must use `for package`
```

## Non-goals

v0.54 does not add package metadata field access, build-time string variables, dynamic artifact names, custom output paths in `build.ins`, shell commands, arbitrary file/process APIs, source generation, install/clean/deploy steps, build profiles, target triples, or manifest syntax changes.
