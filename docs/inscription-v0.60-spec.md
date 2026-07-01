# Inscription v0.60 deterministic release archives and checksums

Inscription v0.60 extends release bundles with deterministic tar.gz archives and SHA-256 checksum manifests. It does not add publishing, registries, signing, upload, or new source language semantics.

## Package release command

```sh
inscription package release [PACKAGE_ROOT]
inscription package release [PACKAGE_ROOT] --include-executable
inscription package release [PACKAGE_ROOT] --include-book
inscription package release [PACKAGE_ROOT] --dry-run
inscription package release [PACKAGE_ROOT] --archive
inscription package release [PACKAGE_ROOT] --checksum
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

`package.ins` is copied exactly from the package root. v0.60 does not include source files, tests, `build.ins`, dependency package artifacts, signatures, signing metadata, or publishing metadata.

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

Build-script release steps include the static library, C header, interface JSON, copied manifest, and release metadata. Executable and book inclusion remain CLI-only in v0.60. Release steps pass through runtime-check, optimization, verify, and save-temp options where applicable.


## Deterministic archives

`inscription package release ROOT --archive` first creates the normal release directory, then writes a deterministic gzip-compressed tar archive next to it:

```text
build/release/PackageName-0.1.0/
build/release/PackageName-0.1.0.tar.gz
```

Archive entries are sorted lexicographically and contain a single top-level directory named after the release directory. File metadata is normalized: mtimes are zero, uid/gid are zero, uname/gname are empty, directories use mode `755`, files under `bin/` use mode `755`, and ordinary files use mode `644`. Gzip metadata is normalized with `mtime = 0`, so repeated archive builds from the same inputs are byte-for-byte reproducible.

## Checksums

`inscription package release ROOT --checksum` writes `checksums.sha256` inside the release directory. The manifest uses lowercase SHA-256 hex, two spaces, a package-relative path, and a trailing newline:

```text
<sha256>  interface.json
<sha256>  include/PackageName.h
<sha256>  lib/libPackageName.a
```

The checksum manifest excludes itself and includes `release.json`. When `--archive --checksum` are combined, the command also writes a sibling archive checksum file:

```text
build/release/PackageName-0.1.0.tar.gz.sha256
```

`release.json` records `"checksums": "checksums.sha256"` when checksums are requested and records the archive path when an archive is requested. The archive checksum is kept in the sibling `.sha256` file to avoid recursive metadata.

`--dry-run --archive --checksum` reports the planned release directory, archive path, release checksum manifest, and archive checksum file without writing or requiring archive tooling.

## Build script archive steps

Build scripts may request release archives:

```inscription
Import Build.

To build package package: Build.Package.
Build.release archive package.
Build.release archive package named "dist".
```

`Build.release archive package.` records a step named `archive`. The named form records the supplied step name. Both run package release with archive and checksum output enabled. The step does not include executable or book artifacts by default.

## Non-goals

v0.60 does not add zip output, signatures, publishing, installation, registry upload, dependency vendoring, source distributions, docs deployment, custom release layouts, build-script include-book/include-executable flags, package manifest release settings, release profiles, target triples, or new source language semantics.
