# Inscription v0.61 stabilization, version reporting, and doctor

Inscription v0.61 makes the toolchain self-describing and easier to diagnose. It adds centralized version metadata, `inscription --version`, `inscription version`, `inscription doctor`, package health checks, and compiler/language metadata in release bundles. It does not add source language syntax, package manifest syntax, registries, publishing, telemetry, network checks, or automatic repair.

## Version metadata

The implementation keeps version constants in `src/inscription/version.py`:

- Inscription tool version
- language version
- required LLVM/MLIR major version
- interface JSON format
- release format
- package manifest format
- build script format

The v0.61 tool version is `0.61.0.dev0`, the language version is `v0.61`, and the required LLVM/MLIR major version remains `22`.

## Version commands

Print the short version:

```sh
inscription --version
```

Output:

```text
inscription 0.61.0.dev0
```

Print deterministic metadata:

```sh
inscription version
```

JSON output is available for tools:

```sh
inscription version --json
```

The JSON contains stable keys and no timestamps, hostnames, git hashes, dirty-state checks, or user-specific data.

## Doctor command

Run environment and package health checks:

```sh
inscription doctor [PACKAGE_ROOT]
inscription doctor [PACKAGE_ROOT] --json
```

`PACKAGE_ROOT` defaults to the current directory. Doctor is read-only: it does not build artifacts, run tests, mutate files, contact the network, install tools, or repair the environment.

Default checks include:

- Inscription version metadata
- Python version
- core package import
- required LLVM/MLIR tools: `mlir-opt`, `mlir-translate`, and `lli`
- optional tools: `llc`, `clang`, `llvm-ar`, and `mdbook`
- package manifest/layout/dependency validation when `package.ins` exists
- `build.ins` validation when present

Optional tool requirements can be promoted with:

```sh
inscription doctor --require-object
inscription doctor --require-executable
inscription doctor --require-static-library
inscription doctor --require-book
```

`--no-package` skips package checks. If no package manifest exists, doctor reports `package: not found` without failing. Missing required tools or invalid package health checks make doctor exit 2.

## Package health

When `PACKAGE_ROOT/package.ins` exists, doctor validates the package graph and reports deterministic package status lines such as:

```text
package: ok (ProtocolTools)
package sources: ok (src)
package tests: ok (tests)
package dependencies: ok (1)
build script: ok (8 steps)
```

Doctor does not run `package format`, `package check --verify`, `package test`, `package build`, or `package release`; it performs lightweight package layout and build-script validation only.

## Pages workflow check

`inscription doctor --check-pages-workflow` checks the repository mdBook Pages workflow without contacting GitHub. It verifies that `.github/workflows/book.yml` exists, contains Pages upload/configure/deploy actions, and that `book/book.toml` exists.

## JSON doctor output

`inscription doctor --json` emits deterministic JSON:

```json
{
  "ok": true,
  "checks": [
    {
      "name": "version",
      "status": "ok",
      "detail": "0.61.0.dev0"
    }
  ],
  "package": {
    "status": "ok",
    "name": "ProtocolTools",
    "root": "."
  }
}
```

Optional missing tools do not make `ok` false. Required failures do.

## Release metadata

Release bundle `release.json` now includes compiler/language metadata:

```json
{
  "format": "inscription-release-v1",
  "package": {
    "name": "ProtocolTools",
    "version": "0.1.0"
  },
  "inscription": {
    "version": "0.61.0.dev0",
    "language_version": "v0.61"
  },
  "artifacts": []
}
```

The release format remains `inscription-release-v1`; the new metadata remains deterministic and excludes timestamps, git hashes, hostnames, usernames, and dirty-state checks.

## check-tools relationship

`inscription check-tools` remains the focused LLVM/MLIR pipeline discovery command. `inscription doctor` is broader: it reports version metadata, Python health, required and optional tools, package health, build-script health, and optional Pages workflow health.

## Non-goals

v0.61 does not add auto-fix, tool installation, network checks, GitHub API checks, git hash embedding, dirty-state detection, telemetry, publishing, registry validation, dependency update checks, lockfile validation, workspaces, build profiles, target triples, or new source language semantics.
