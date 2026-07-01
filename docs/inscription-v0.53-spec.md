# Inscription v0.53 documentation build steps

Inscription v0.53 extends the restricted `build.ins` Build API with sandboxed mdBook documentation steps:

```inscription
Build.book named "book".
Build.book checked named "book-check".
```

`package.ins` remains declarative metadata. `build.ins` still cannot run arbitrary shell commands, access arbitrary files, deploy documentation, or choose custom output paths.

## Build API additions

The v0.53 Build API includes all v0.52 step kinds plus:

```inscription
Build.book named "name".
Build.book checked named "name".
```

Both forms are valid only in `build.ins`. Step names use the same simple-name rules as artifact, check, test, and group steps: non-empty ASCII letters, digits, `_`, or `-`, starting with a letter or `_`, with no path separators. Duplicate step names are rejected.

## Book step

`Build.book named "book".` builds the mdBook located at:

```text
PACKAGE_ROOT/book
```

The package must contain:

```text
book/book.toml
```

The output directory is:

```text
PACKAGE_ROOT/build/<step-name>/
```

For example, `Build.book named "docs".` writes to `build/docs/`. Existing output at exactly that directory is removed before building. Step names cannot contain path separators, so the step cannot delete arbitrary paths.

The step requires `mdbook`. If `mdbook` is not available, the diagnostic is deterministic:

```text
book step requires mdbook, but mdbook was not found
```

If `book/book.toml` is missing, the diagnostic is:

```text
book step docs requires book/book.toml
```

## Checked book step

`Build.book checked named "book-check".` first runs:

```text
python book/tools/check_book_examples.py
```

from the package root, then builds the book if the checker succeeds. The checker is package-local and must exist at:

```text
book/tools/check_book_examples.py
```

If the checker is missing, the diagnostic is:

```text
book check step book-check requires book/tools/check_book_examples.py
```

If the checker or mdBook build fails, the build command exits with a package/build diagnostic status.

## Groups, defaults, and flags

Book and checked-book steps participate in v0.52 groups and defaults like any other step:

```inscription
Import Build.

To build package package: Build.Package.
Build.check package named "check".
Build.tests named "tests".
Build.book checked named "book".
Build.group named "ci" with steps "check" and "tests" and "book".
Build.default step is "ci".
```

Group de-duplication applies. If a book step fails, the group fails and later dependencies are not run. `inscription build --list` does not require mdBook and lists book steps normally.

`--runtime-checks`, `--opt-level`, and `--verify` do not affect documentation steps. `--save-temps` is ignored for documentation steps; docs output always goes to `build/<step-name>/`. Compiler and test dependencies in the same group still use their step-specific save-temp directories.

## Non-goals

v0.53 does not add arbitrary process execution, shell commands, custom documentation generators, deployment steps, GitHub Pages deployment from `build.ins`, custom docs output paths, source generation, file APIs, networking, package publishing, build profiles, package metadata string access, string variables, or host-state conditionals.
