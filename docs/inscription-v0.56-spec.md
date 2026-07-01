# Inscription v0.56 package initialization and example package polish

Inscription v0.56 adds package ergonomics around the existing package/build stack. It introduces fixed, deterministic package skeleton generation through:

```sh
inscription package init [ROOT]
inscription package new PATH
```

This sprint does not add source language semantics. The generated packages use existing `package.ins`, `build.ins`, source modules, tests, and optional mdBook documentation.

## Commands

`package init` initializes an existing directory, creating it when needed:

```sh
inscription package init . --name HelloPkg
```

`package new` creates a new package directory and initializes it:

```sh
inscription package new hello --name Hello
inscription package new protocol-tools --name ProtocolTools --with-book
```

Options shared by both commands:

- `--name NAME`: explicit package/module path.
- `--library`: generate the default library template.
- `--executable`: generate an executable-oriented source/test template.
- `--with-book`: also generate a minimal mdBook skeleton.
- `--force`: overwrite only files owned by the package initializer.

`--library` and `--executable` are mutually exclusive. Library is the default template.

## Generated layout

For `HelloPkg`, the library template creates:

```text
package.ins
build.ins
src/HelloPkg.ins
tests/basic.ins
```

`package.ins`:

```inscription
//! Package manifest for HelloPkg.

Package HelloPkg.

Version "0.1.0".

Sources are in "src".
Tests are in "tests".

Root module is HelloPkg.

Expose module HelloPkg.
```

`build.ins`:

```inscription
Import Build.

To build package package: Build.Package.
Build.standard package workflow.
```

The library source exports a simple scalar function for static-library/header smoke tests:

```inscription
Module HelloPkg.

/// Adds two numbers.
To add left: i32 and right: i32, giving i32, exported as ins_add.
Give left plus right.
```

The generated test imports the package root module and checks the sample function.

## Executable template

`--executable` generates:

```inscription
Module HelloPkg.

To main, giving i32.
Give 42.
```

and a test that expects `HelloPkg.main` to equal `42`. The generated `build.ins` still uses the standard workflow, which intentionally does not include an executable artifact. It includes a commented reminder showing `Build.executable for package.` for users who want to add that step.

## Book template

`--with-book` adds:

```text
book/book.toml
book/src/SUMMARY.md
book/src/introduction.md
book/tools/check_book_examples.py
```

The book skeleton is intentionally small and valid for mdBook. The generated checker is a tiny deterministic script in v0.56. Because `book/book.toml` exists, the standard build workflow automatically includes `book-check`.

## Name inference and validation

When `--name` is omitted, the package name is inferred from the target directory basename:

```text
protocol-tools -> ProtocolTools
hello_world    -> HelloWorld
hello          -> Hello
```

If no valid name can be inferred, the command fails with:

```text
package name could not be inferred; pass --name NAME
```

Explicit names use the existing module-path form `Identifier(.Identifier)*`. Invalid explicit names fail deterministically, for example:

```text
invalid package name 123Bad
```

## Overwrite rules

Without `--force`, initialization fails before writing anything if a generated target file already exists:

```text
package init would overwrite package.ins; use --force to overwrite
```

`package new` also rejects existing nonempty directories unless `--force` is supplied:

```text
package new target already exists and is not empty; use --force to overwrite
```

With `--force`, only files owned by the fixed skeleton generator are overwritten. Unrelated files are not deleted.

## Non-goals

v0.56 does not add a package registry, publishing, installation, lockfiles, dependency solving, remote fetching, workspaces, arbitrary templates, build profiles, target triples, interactive prompts, network access, custom template directories, git initialization, license/CI generation, or source generation beyond fixed package skeleton files.
