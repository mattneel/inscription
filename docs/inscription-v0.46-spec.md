# Inscription v0.46 package build artifacts

Inscription v0.46 adds package-aware artifact builds on top of v0.45 `package.ins` manifests. `package.ins` remains declarative metadata, comparable to `build.zig.zon`; v0.46 routes the existing single-source compiler artifact pipeline through package metadata without adding `build.ins`, dependencies, package scripts, registries, lockfiles, workspaces, target triples, or new language semantics.

## Command

```sh
inscription package build [PACKAGE_ROOT]
```

`PACKAGE_ROOT` defaults to the current directory. The command reads `PACKAGE_ROOT/package.ins`, validates it with the same manifest/source checks as `package check`, and compiles the manifest root module using `Sources are in ...` as the module root.

Supported options mirror `compile` where applicable:

```text
--emit mlir|lowered-mlir|llvm-ir|object|executable|static-library|interface-json|c-header
-o OUTPUT
--runtime-checks
--opt-level none|basic|aggressive
-O0 / -O1 / -O2
--save-temps DIR
--link-object PATH
--archive-object PATH
--verify
```

Compiler/package/tool diagnostics exit 2. Successful builds exit 0. `package build` does not run tests and does not require a declared tests directory.

## Defaults

The default emit mode is `static-library`.

```sh
inscription package build
```

For `Package ProtocolTools.`, the default output path is:

```text
build/libProtocolTools.a
```

For a dotted package name, the final package segment is used and casing is preserved:

```text
Package Acme.ProtocolTools. -> build/libProtocolTools.a
```

`build/` is created when the default static-library output path is used.

## Emit modes

Package emit modes map to existing compiler artifact modes:

- `mlir`, `lowered-mlir`, and `llvm-ir` emit text artifacts.
- `object` emits one native object and requires `-o`.
- `executable` builds the root module as an executable and requires `-o` plus a runnable no-hole integer-scalar `main`.
- `static-library` builds a deterministic archive; if `-o` is omitted, the package default path is used.
- `interface-json` emits interface metadata and may write to stdout when `-o` is omitted.
- `c-header` emits exported scalar phrase prototypes and may write to stdout when `-o` is omitted.

`--link-object` is valid only with `--emit executable`. `--archive-object` is valid only with `--emit static-library`.

## Module root and exposed modules

Package build uses:

```text
PACKAGE_ROOT / Sources
```

as the module root. The manifest root module resolves normally:

```text
Root module is ProtocolTools. -> src/ProtocolTools.ins
Root module is ProtocolTools.App. -> src/ProtocolTools/App.ins
```

For library-like package emits (`mlir`, `lowered-mlir`, `llvm-ir`, `object`, `static-library`, `interface-json`, and `c-header`), the package build includes the root module and every `Expose module ... .` entry, even when an exposed module is not imported by the root module. This makes package headers, interface JSON, and static libraries represent package exports rather than only root-module imports.

For executable emits, the root module is compiled normally. Exposed modules are included only when they are imported by the executable root.

## Interface JSON

Package interface JSON adds a top-level `package` field while preserving the normal interface format:

```json
{
  "format": "inscription-interface-v1",
  "package": {
    "name": "ProtocolTools",
    "version": "0.1.0",
    "sources": "src",
    "tests": "tests",
    "root_module": "ProtocolTools",
    "exposed_modules": ["ProtocolTools", "ProtocolTools.Checksum"]
  },
  "source": "package.ins",
  "module_root": ".",
  "root_module": "ProtocolTools",
  "modules": []
}
```

Single-file `compile --emit interface-json` output remains unchanged.

## C headers

Package C headers include exported scalar phrases from the root module and exposed modules in deterministic package order. Exported phrase documentation comments are preserved as C comments before prototypes. Extern declarations and tests are not emitted.

## Save temps

`--save-temps DIR` writes deterministic package intermediates using the final package name segment as the stem, for example:

```text
DIR/ProtocolTools.mlir
DIR/ProtocolTools.optimized.mlir   # when optimization is enabled
DIR/ProtocolTools.lowered.mlir
DIR/ProtocolTools.ll
DIR/ProtocolTools.o
```

## Examples

```sh
inscription package build . --emit static-library -o build/libProtocolTools.a
inscription package build . --emit c-header -o build/ProtocolTools.h
inscription package build . --emit interface-json -o build/ProtocolTools.json
inscription package build . --emit llvm-ir --verify -o build/ProtocolTools.ll
inscription package build . --emit executable -o build/app
```

## Non-goals

v0.46 does not add executable build scripts, dependencies, lockfiles, registries, installation, publishing, workspaces, build profiles, source generation, target triples, package artifact declarations in the manifest, or arbitrary manifest evaluation.
