# Inscription v0.59 release bundles

Inscription v0.59 adds deterministic package release bundle creation. It does not add publishing, registries, signing, upload, or new source language semantics.

## Package release command

```sh
inscription package release [PACKAGE_ROOT]
inscription package release [PACKAGE_ROOT] --include-executable
inscription package release [PACKAGE_ROOT] --include-book
inscription package release [PACKAGE_ROOT] --dry-run
```

`PACKAGE_ROOT` defaults to the current directory. The command validates `package.ins` and creates a release directory. The default output is:

```text
build/release/<PackageFinalName>-<version>
```

When the manifest has no version, the default is:

```text
build/release/<PackageFinalName>
```

`-o OUTPUT_DIR` overrides the output directory. `--name NAME` overrides only the default directory basename when `-o` is not supplied. `--clean` replaces an existing target directory; without `--clean`, an existing nonempty output directory is rejected:

```text
release output directory already exists; use --clean to replace it
```

## Bundle layout

A release bundle always includes:

```text
package.ins
release.json
interface.json
include/<PackageFinalName>.h
lib/lib<PackageFinalName>.a
```

Optional flags add:

```text
bin/<PackageFinalName>      # --include-executable
docs/                       # --include-book
```

`package.ins` is copied exactly from the package root. v0.59 does not include source files, tests, `build.ins`, dependency package artifacts, compressed archives, signatures, checksums, or publishing metadata.

## release.json

`release.json` is deterministic and uses relative paths only:

```json
{
  "format": "inscription-release-v1",
  "package": {
    "name": "ProtocolTools",
    "version": "0.1.0"
  },
  "artifacts": [
    {
      "kind": "static-library",
      "path": "lib/libProtocolTools.a"
    },
    {
      "kind": "c-header",
      "path": "include/ProtocolTools.h"
    },
    {
      "kind": "interface-json",
      "path": "interface.json"
    }
  ]
}
```

The version is `null` when the package manifest omits `Version`. Metadata intentionally excludes timestamps, hostnames, usernames, git hashes, and nondeterministic data.

## Dry run

`--dry-run` validates enough package metadata to determine the release name and prints planned actions without requiring LLVM/MLIR or mdBook tools:

```text
release output: build/release/ProtocolTools-0.1.0
would build static library: lib/libProtocolTools.a
would build C header: include/ProtocolTools.h
would build interface JSON: interface.json
would copy package manifest: package.ins
would write release metadata: release.json
```

## Build API

`build.ins` gains release bundle steps:

```inscription
Build.release package.
Build.release package named "dist".
```

`Build.release package.` records a package-aware step named `bundle` to avoid colliding with the standard workflow's existing `release` group. `Build.release package named "name".` records the same release behavior under an explicit simple step name.

Build-script release steps include the static library, C header, interface JSON, copied manifest, and release metadata. Executable and book inclusion remain CLI-only in v0.59. Release steps pass through runtime-check, optimization, verify, and save-temp options where applicable.

## Non-goals

v0.59 does not add tar/zip archive output, signing, checksums, publishing, installation, registry upload, dependency vendoring, source distributions, docs deployment, custom release layouts, build-script include-book/include-executable flags, package manifest release settings, release profiles, target triples, or new source language semantics.
