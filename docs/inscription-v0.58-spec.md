# Inscription v0.58 package clean and build artifact hygiene

Inscription v0.58 adds deterministic cleanup for package-generated build artifacts. It does not change source language semantics.

## Package clean command

```sh
inscription package clean [PACKAGE_ROOT]
inscription package clean [PACKAGE_ROOT] --dry-run
inscription package clean [PACKAGE_ROOT] --include-dependencies
```

`PACKAGE_ROOT` defaults to the current directory. The command reads `package.ins`, loads the local path dependency graph, and removes only the generated package build directory:

```text
build/
```

When `build/` is absent, the command succeeds:

```text
package clean: nothing to clean
```

When `build/` exists, the command removes it recursively and reports:

```text
package clean: removed build
```

`--dry-run` reports the deletion without modifying the filesystem:

```text
package clean: would remove build
```

## Dependency cleaning

By default, `package clean` cleans only the root package. With `--include-dependencies`, it cleans the root package and every loaded local path dependency exactly once in deterministic package graph order. Output is package-qualified:

```text
package App: removed build
package Checksums: removed build
```

## Safety rules

`package clean` never removes package sources, tests, manifests, build scripts, book sources, documentation, grammar files, dependency package outputs by default, arbitrary globs, or custom paths. It only targets `PACKAGE_ROOT/build` for each package being cleaned.

If `build` is a symlink, the command refuses to remove it rather than following or unlinking it:

```text
package clean refuses to remove symlink build
```

If `build` exists but is not a directory, the command reports:

```text
package clean expected build to be a directory
```

## Build API

`build.ins` gains clean steps:

```inscription
Build.clean package.
Build.clean package named "clean".
```

`Build.clean package.` is package-aware shorthand for a step named `clean`. `Build.clean package named "name".` records the same clean operation under an explicit simple step name.

Clean steps:

- are valid only in `build.ins`
- remove only the root package `build/` directory
- do not clean dependency packages in v0.58
- do not require LLVM/MLIR tools
- do not require mdBook
- ignore runtime-check, optimization, and save-temp flags
- participate in groups and default steps like ordinary build steps

Duplicate step names use the existing deterministic diagnostic:

```text
build step clean is already defined
```

## Fresh workflow pattern

The standard workflow does not include clean. Packages that want an explicit fresh release can write:

```inscription
Build.clean package.
Build.standard package workflow.
Build.group named "fresh" with steps "clean" and "release".
```

Running `inscription build PACKAGE fresh` removes `build/` and then runs the release group, which recreates the configured artifacts.

## Non-goals

v0.58 does not add arbitrary file deletion, clean globs, custom clean paths, clean hooks, shell commands, process execution, dependency cleaning by default, workspace cleaning, remote cache cleaning, generated source cleanup outside known `build/` directories, package uninstall, build profiles, or new source language semantics.
