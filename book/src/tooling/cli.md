# CLI

Common commands:

```sh
PYTHONPATH=src python -m inscription compile SOURCE --verify
PYTHONPATH=src python -m inscription run SOURCE
PYTHONPATH=src python -m inscription test SOURCE
PYTHONPATH=src python -m inscription package new PATH --name PackageName
PYTHONPATH=src python -m inscription package init PACKAGE_ROOT --name PackageName
PYTHONPATH=src python -m inscription package check PACKAGE_ROOT
PYTHONPATH=src python -m inscription package test PACKAGE_ROOT
PYTHONPATH=src python -m inscription package build PACKAGE_ROOT
PYTHONPATH=src python -m inscription build PACKAGE_ROOT
PYTHONPATH=src python -m inscription format SOURCE --check
PYTHONPATH=src python -m inscription highlight SOURCE
PYTHONPATH=src python -m inscription check-tools --show-pipeline
```

`compile` emits artifacts without executing the program. `run` lowers through LLVM 22 and executes `main` with `lli`. `test` discovers top-level `Test ... .` declarations, compiles each selected test through the MLIR/LLVM pipeline, and reports a deterministic summary. `package new` and `package init` generate formatter-clean package skeletons. `package format` checks or rewrites package-owned `.ins` files. `package clean` removes generated package `build/` artifacts. `package check` validates `package.ins` manifests, dependency graphs, and package source layout. `package test` discovers test files from the manifest test directory and runs them with the package source directory plus direct dependency exposed modules as import roots. `package build` emits package-aware artifacts through the existing compile pipeline. `build` interprets `build.ins` and dispatches named clean, format, check, test, artifact, documentation, and group steps through the package machinery. `format` is parse-only and does not need LLVM tools. `highlight` uses the same Inscription lexer used by this book.

Useful test options:

```sh
PYTHONPATH=src python -m inscription test SOURCE --list
PYTHONPATH=src python -m inscription test SOURCE --filter addition
PYTHONPATH=src python -m inscription test SOURCE --runtime-checks
PYTHONPATH=src python -m inscription test SOURCE --save-temps /tmp/inscription-test-temps
```

`test` exits 0 when all selected tests pass, exits 1 when any selected test fails at runtime, and exits 2 for compiler/tooling diagnostics.


Useful package commands:

```sh
PYTHONPATH=src python -m inscription package new hello --name Hello
PYTHONPATH=src python -m inscription package new docs-pkg --name DocsPkg --with-book
PYTHONPATH=src python -m inscription package init . --name ExistingPkg
PYTHONPATH=src python -m inscription package new app --name App --executable
PYTHONPATH=src python -m inscription package format hello --check
PYTHONPATH=src python -m inscription package format hello --in-place
PYTHONPATH=src python -m inscription package clean hello --dry-run
PYTHONPATH=src python -m inscription package clean hello
PYTHONPATH=src python -m inscription package check .
PYTHONPATH=src python -m inscription package check . --verify
PYTHONPATH=src python -m inscription package test .
PYTHONPATH=src python -m inscription package test . --list
PYTHONPATH=src python -m inscription package test . --filter addition
PYTHONPATH=src python -m inscription package test . --include-dependencies
PYTHONPATH=src python -m inscription package build .
PYTHONPATH=src python -m inscription package build . --emit c-header -o build/package.h
PYTHONPATH=src python -m inscription package build . --emit interface-json -o build/package.json
PYTHONPATH=src python -m inscription package build . --emit executable -o build/app
```

`package init` initializes an existing directory, creating it if needed. `package new` creates and initializes a package directory. Both commands default to a library template, accept `--executable`, can add a minimal mdBook with `--with-book`, and protect existing generated files unless `--force` is supplied. `package format` requires `--check` or `--in-place`; `--include-dependencies` includes local path dependencies and `--include-book` runs package book example checks when present. `package clean` removes only `build/`, supports `--dry-run`, and cleans local path dependencies only with `--include-dependencies`.

`package check` exits 0 on a valid manifest/layout/dependency graph and exits 2 for manifest, package, compiler, or tool diagnostics. `package test` exits 0 when all selected tests pass, exits 1 for runtime test failures, and exits 2 for package/compiler/tool diagnostics. `package build` exits 0 on success and exits 2 for package/compiler/tool diagnostics; its default output is `build/lib<Package>.a`.


Useful build script commands:

```sh
PYTHONPATH=src python -m inscription build . --list
PYTHONPATH=src python -m inscription build . ci
PYTHONPATH=src python -m inscription build . library
PYTHONPATH=src python -m inscription build . book
PYTHONPATH=src python -m inscription build .
PYTHONPATH=src python -m inscription build . ci --save-temps build/temps
```

`build` exits 0 on success, exits 1 when a test step fails, and exits 2 for package, build-script, compiler, or tool diagnostics. With a step name, it runs that step; group steps run dependencies once in declaration order. Without a step name, it runs the declared default step when present, otherwise it runs all ordinary non-group steps in source order. Documentation steps write to `build/<step-name>/` and require mdBook only when executed.
