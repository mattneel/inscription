# Inscription v0.45 package manifests

Inscription v0.45 adds a declarative package manifest named `package.ins` plus package-aware validation and test commands. A manifest is Inscription-native prose-punctuation metadata, comparable to `build.zig.zon`: it describes package layout and modules but does not execute code.

No dependencies, package registry, lockfile, `build.ins`, interpreter, comptime, variables, conditionals, workspace support, build graph scripting, package publishing, or remote fetching are added.

## Manifest file

`package.ins` lives at the package root. It is not a normal source module. It uses a restricted grammar and supports only:

- `//!` module/file documentation comments
- ordinary `//` comments
- `Package NAME.`
- `Version "MAJOR.MINOR.PATCH".`
- `Sources are in "PATH".`
- `Tests are in "PATH".`
- `Root module is MODULE_PATH.`
- `Expose module MODULE_PATH.`

Normal source declarations such as `To`, `Import`, `Let`, `Record`, `Enum`, `Union`, and `Test` are rejected inside manifests.

## Manifest syntax

Canonical form:

```inscription
//! Package manifest for ProtocolTools.

Package ProtocolTools.

Version "0.1.0".

Sources are in "src".
Tests are in "tests".

Root module is ProtocolTools.

Expose module ProtocolTools.
Expose module ProtocolTools.Protocol.
Expose module ProtocolTools.Checksum.
```

Rules:

- `Package NAME.` is required and must be the first non-comment declaration.
- Package names use module-path syntax: `Identifier ("." Identifier)*`.
- `Version "...".` is optional and must use `MAJOR.MINOR.PATCH` in v0.45.
- `Sources are in "PATH".` is required.
- `Tests are in "PATH".` is optional.
- `Root module is MODULE_PATH.` is required.
- `Expose module MODULE_PATH.` is optional and repeatable.
- Duplicate singleton declarations are rejected.
- Duplicate exposed modules are rejected.
- The formatter emits declarations in canonical order: Package, Version, Sources, Tests, Root module, Expose module declarations.

Manifest strings are metadata strings, not source-level string values. Paths are relative to the package root. Empty paths, absolute paths, NUL bytes, and `..` path components are rejected.

## Package check

```sh
inscription package check [PACKAGE_ROOT]
inscription package check [PACKAGE_ROOT] --verify
```

`PACKAGE_ROOT` defaults to the current directory and must contain `package.ins`.

`package check`:

- parses and validates the manifest
- checks that the sources directory exists
- checks that the tests directory exists when declared
- resolves the root module under the sources directory
- verifies the root module file declares the expected module
- resolves and validates every exposed module
- type-checks validated modules using the sources directory as the module root

`--verify` additionally runs source-MLIR verification for the checked modules using the configured LLVM/MLIR toolchain.

A successful check prints:

```text
package ProtocolTools: ok
```

Compiler or package diagnostics exit with status 2.

## Package test

```sh
inscription package test [PACKAGE_ROOT]
```

Supported options:

```text
--filter TEXT
--list
--runtime-checks
--opt-level none|basic|aggressive
-O0 / -O1 / -O2
--save-temps DIR
```

`package test` validates the package, uses the manifest's sources directory as the module root, discovers `.ins` files recursively under the tests directory when one is declared, and runs the same `inscription test` pipeline for each test file.

If no tests directory is declared, or the tests directory contains no `.ins` files, the command prints `no tests found` and exits 0. If a filter matches no discovered tests, it prints `no tests matched filter <TEXT>` and exits 0. Runtime test failures exit 1; compiler/package diagnostics exit 2.

Package test display names are prefixed by the test file path relative to the package root, for example:

```text
test tests/checksum.ins::root::checksum works ... ok
```

## Module root behavior

Package commands set the module root to:

```text
package_root / sources_directory
```

Module paths resolve as usual under that source root:

```text
ProtocolTools -> src/ProtocolTools.ins
ProtocolTools.Protocol -> src/ProtocolTools/Protocol.ins
```

Test files outside the source root can import package modules because `package test` supplies the package source directory as the module root.

## Formatter and highlighter

`inscription format package.ins`, `--check`, and `--in-place` work on package manifests. The formatter auto-detects manifest mode when the file basename is `package.ins` or the first non-comment declaration is `Package`.

The highlighter recognizes the manifest declaration keywords `Package`, `Version`, `Sources`, `Tests`, `Root`, and `Expose`.

## Diagnostics

Representative diagnostics include:

```text
package manifest not found at package.ins
package manifest must start with Package declaration
package declaration requires a package name
package manifest declares sources more than once
package manifest must declare a sources directory
package manifest must declare a root module
package sources directory `src` does not exist
root module P not found at src/P.ins
root module P resolved to module Other; expected P
exposed module P.Missing not found at src/P/Missing.ins
package manifest exposes module P more than once
package version must use MAJOR.MINOR.PATCH format
package paths must be relative
package paths may not contain `..`
package manifests do not support phrase declarations
package manifests do not support imports
```
