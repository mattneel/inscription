# Inscription v0.57 package-wide formatting and build format steps

Inscription v0.57 adds package-level formatter tooling and build-script format steps. It does not change source language semantics.

## Package format command

```sh
inscription package format [PACKAGE_ROOT] --check
inscription package format [PACKAGE_ROOT] --in-place
```

`PACKAGE_ROOT` defaults to the current directory. The command reads `package.ins` and discovers:

- `package.ins`
- `build.ins`, when present
- every `.ins` file under the manifest sources directory
- every `.ins` file under the manifest tests directory, when declared and present

`--check` exits 0 when every discovered file is already canonical and exits 2 with one deterministic diagnostic per changed file when formatting would change anything:

```text
formatting check failed: src/ProtocolTools.ins is not formatted
```

`--in-place` rewrites discovered files with canonical formatting. The two modes are mutually exclusive, and one mode is required:

```text
package format requires --check or --in-place
```

Package formatting is parse/format-only. It does not type-check, lower MLIR, run tests, or require LLVM tools.

## Dependencies and books

`--include-dependencies` recursively includes local path dependency packages in dependency graph order. Dependency files are formatted relative to each dependency package root.

`--include-book` checks package mdBook Inscription examples by running `book/tools/check_book_examples.py` when `book/book.toml` exists. In v0.57 this is check-only; rewriting fenced book snippets is intentionally unsupported:

```text
package format --include-book --in-place is not supported in v0.57
```

## Build API

`build.ins` gains two sandboxed Build API phrases:

```inscription
Build.format check named "format".
Build.format package named "format-in-place".
```

`Build.format check` records a non-mutating format-check step equivalent to `inscription package format --check`. `Build.format package` records an explicit in-place formatter step equivalent to `inscription package format --in-place`. Both are valid only in `build.ins`, share the normal build-step namespace, and follow existing step-name validation and duplicate rules.

`Build.format package` is intentionally explicit and is not included in the standard workflow.

## Standard workflow update

`Build.standard package workflow.` now records a format-check step before validation and tests:

```inscription
Build.format check named "format".
Build.check package named "check".
Build.tests named "tests".
Build.static library for package.
Build.c header for package.
Build.interface json for package.
```

When `book/book.toml` exists it still records `Build.book checked for package.`.

With a book, `ci` expands to:

```inscription
Build.group named "ci" with steps "format" and "check" and "tests" and "book-check".
```

Without a book, `ci` expands to:

```inscription
Build.group named "ci" with steps "format" and "check" and "tests".
```

`release` remains:

```inscription
Build.group named "release" with steps "ci" and "library" and "header" and "interface".
```

The default step remains `ci`.

## Non-goals

v0.57 does not add formatter configuration, line-width settings, import sorting, declaration sorting, semantic rewrites, custom package globs, arbitrary build commands, shell/process steps, build profiles, package registry features, or automatic formatting outside explicit `package format`/Build format steps.
