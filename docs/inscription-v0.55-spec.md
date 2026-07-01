# Inscription v0.55 standard package build workflows

Inscription v0.55 adds a safe workflow shortcut to the restricted `build.ins` Build API:

```inscription
Build.standard package workflow.
```

The shortcut expands to conventional package validation, tests, library/header/interface artifacts, groups, and a default `ci` step. It is declarative shorthand only: it records the same internal step records as explicit Build API calls and does not run arbitrary commands or expose package metadata strings to the script.

## Standard workflow expansion

A minimal standard build script is:

```inscription
Import Build.

To build package package: Build.Package.
Build.standard package workflow.
```

The build driver expands it deterministically.

Always recorded:

```inscription
Build.check package named "check".
Build.tests named "tests".
Build.static library for package.
Build.c header for package.
Build.interface json for package.
```

If `book/book.toml` exists at the package root, also recorded:

```inscription
Build.book checked for package.
```

Then groups/default are recorded. With a book:

```inscription
Build.group named "ci" with steps "check" and "tests" and "book-check".
Build.group named "release" with steps "ci" and "library" and "header" and "interface".
Build.default step is "ci".
```

Without a book:

```inscription
Build.group named "ci" with steps "check" and "tests".
Build.group named "release" with steps "ci" and "library" and "header" and "interface".
Build.default step is "ci".
```

The book check is a package-driver rule, not arbitrary script filesystem access. If a package has no declared tests directory, the `tests` step is still recorded and uses existing package-test behavior: `no tests found`, exit 0.

## Outputs

The standard workflow uses v0.54 package-aware output defaults. For:

```inscription
Package StandardPkg.
```

release artifacts are:

```text
build/libStandardPkg.a
build/StandardPkg.h
build/StandardPkg.json
```

If a book exists, the checked book output is:

```text
build/book-check/
```

The standard workflow intentionally does not include an executable step in v0.55. Packages that want an executable can add an explicit step such as `Build.executable for package.` or use a custom group.

## Commands

A bare build runs the default `ci` step:

```sh
inscription build path/to/package
```

Run the release group explicitly:

```sh
inscription build path/to/package release
```

List the expanded steps:

```sh
inscription build path/to/package --list
```

With a book, list output includes `book-check` and `ci` depends on it. Without a book, `book-check` is absent and `ci` depends only on `check` and `tests`.

## Duplicate behavior

`Build.standard package workflow.` expands into ordinary step records, so normal duplicate rules apply. This is invalid:

```inscription
Build.standard package workflow.
Build.tests named "tests".
```

and emits:

```text
build step tests is already defined
```

Likewise, adding another `ci` group or another default step after the standard workflow is rejected deterministically.

## Build phrase parameter

The standard workflow uses package-aware defaults and therefore requires the canonical build phrase:

```inscription
To build package package: Build.Package.
```

A renamed parameter is rejected with:

```text
build phrase parameter must be named package in v0.55
```

## Non-goals

v0.55 does not add arbitrary shell commands, arbitrary process execution, filesystem APIs, source generation, custom output paths, build profiles, target triples, deploy/publish/install steps, package metadata string access, dynamic step names, conditionals over host state, remote dependencies, lockfiles, or workspaces.
