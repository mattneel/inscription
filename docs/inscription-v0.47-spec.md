# Inscription v0.47 package path dependencies

Inscription v0.47 extends declarative `package.ins` manifests with local path dependencies. This remains package metadata, not executable build logic: v0.47 does not add `build.ins`, remote dependencies, git dependencies, registries, lockfiles, version solving, workspaces, package install/publish commands, feature flags, or arbitrary manifest expressions.

## Manifest syntax

A package may depend on another local package with:

```inscription
Depend on Checksums from path "../checksums".
Depend on Wire from path "vendor/wire".
```

The dependency name uses module-path syntax (`Name` or `Name.SubName`). The path is a manifest string relative to the package root. Dependency paths may contain `..` components, unlike `Sources are in ...` and `Tests are in ...`, but they must not be absolute or empty. The target directory must contain `package.ins`.

The dependency package's `Package ... .` declaration must exactly match the dependency name:

```inscription
Depend on Checksums from path "../checksums".
```

requires `../checksums/package.ins` to contain:

```inscription
Package Checksums.
```

Duplicate dependency names are rejected. If two dependency declarations in one manifest resolve to the same directory with different names, the manifest is rejected for determinism.

The manifest formatter emits declarations in this canonical order:

```text
Package
Version
Sources
Tests
Root module
Expose module*
Depend on*
```

Dependency declarations retain source order within the dependency group.

## Dependency graph loading

Package commands load direct dependencies recursively. Each package root is canonicalized internally so the graph is deterministic. The loader rejects:

- missing dependency manifests
- dependency package-name mismatches
- duplicate dependency names
- the same dependency root declared under different names
- the same package name resolving to multiple roots
- dependency cycles

Cycle diagnostics name the package chain, for example:

```text
package dependency cycle detected: App -> Checksums -> App
```

## Module resolution

Package commands continue to use the manifest `Sources are in ... .` directory as the package's local module root.

A source file resolves imports in this order:

1. The importing package's own source directory.
2. The importing package's direct dependencies, but only dependency modules that are externally visible.

A dependency exposes its root module and every `Expose module ... .` entry. Other dependency modules are internal to that package and may be imported by that dependency's own source files, but not by dependents. Importing an unexposed dependency module fails deterministically:

```text
module Checksums.Internal is not exposed by package Checksums
```

Transitive dependencies are not implicitly visible to a dependent package. If `App` depends on `A` and `A` depends on `B`, `App` must declare its own `Depend on B ... .` before importing `B` directly.

## Package check

`inscription package check [ROOT]` now loads and validates the dependency graph before validating source layout and modules. It validates every dependency manifest, root module, exposed module, source directory, and declared test directory. Root and exposed modules are type-checked with dependency-aware module resolution. `--verify` also verifies generated source MLIR for the checked modules.

Successful output remains concise:

```text
package App: ok
```

## Package test

`inscription package test [ROOT]` lets root package tests import root modules and direct dependency root/exposed modules. Dependency package tests are not run by default.

Use `--include-dependencies` to run dependency package tests too:

```sh
inscription package test . --include-dependencies
```

Display names include the package name and test file path so root and dependency tests remain distinct:

```text
test App::tests/app.ins::root::app checksum works ... ok
test Checksums::tests/checksum.ins::root::checksum works ... ok
```

`--list`, `--filter`, `--runtime-checks`, optimization options, and `--save-temps` work with dependency-aware package tests. Filtering applies to package-qualified display names.

## Package build

`inscription package build [ROOT]` compiles package modules that import dependency root/exposed modules.

- `--emit executable` builds the root module and imported dependency modules as needed.
- Library-like emits include the root package root/exposed modules plus dependency modules reached through imports.
- Root package C headers include only root package exported phrases by default. Dependency exported phrases are intentionally omitted; build the dependency package separately to generate its header.
- Static libraries and executable builds may contain dependency code when dependency modules are imported and lowered as part of the compilation graph.

## Interface JSON

Package interface JSON includes dependency metadata under the existing top-level `package` object:

```json
{
  "package": {
    "name": "App",
    "version": "0.1.0",
    "sources": "src",
    "tests": "tests",
    "root_module": "App",
    "exposed_modules": ["App"],
    "dependencies": [
      {
        "name": "Checksums",
        "path": "../checksums",
        "version": "0.1.0"
      }
    ]
  }
}
```

Dependency paths use the spelling from the root manifest, not absolute paths. Dependency version is included when the dependency manifest declares one. Single-file `compile --emit interface-json` output remains unchanged.

## Diagnostics

Representative deterministic diagnostics:

```text
dependency Missing not found at ../missing/package.ins
dependency Checksums resolved to package Other; expected Checksums
package manifest declares dependency Checksums more than once
dependency path ../shared is declared for both A and B
package dependency cycle detected: A -> B -> A
module Checksums.Internal is not exposed by package Checksums
dependency paths must be relative
dependency path must not be empty
Depend declarations are only valid in package manifests
```

## Non-goals

v0.47 does not add git or registry dependencies, semantic version constraints, version solving, lockfiles, vendoring, install/publish commands, workspaces, dependency features, optional dependencies, `build.ins`, arbitrary manifest evaluation, source generation, package scripts, re-exports, or visibility modifiers.
