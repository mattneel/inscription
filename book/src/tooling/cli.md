# CLI

Common commands:

```sh
PYTHONPATH=src python -m inscription compile SOURCE --verify
PYTHONPATH=src python -m inscription run SOURCE
PYTHONPATH=src python -m inscription test SOURCE
PYTHONPATH=src python -m inscription package check PACKAGE_ROOT
PYTHONPATH=src python -m inscription package test PACKAGE_ROOT
PYTHONPATH=src python -m inscription package build PACKAGE_ROOT
PYTHONPATH=src python -m inscription format SOURCE --check
PYTHONPATH=src python -m inscription highlight SOURCE
PYTHONPATH=src python -m inscription check-tools --show-pipeline
```

`compile` emits artifacts without executing the program. `run` lowers through LLVM 22 and executes `main` with `lli`. `test` discovers top-level `Test ... .` declarations, compiles each selected test through the MLIR/LLVM pipeline, and reports a deterministic summary. `package check` validates `package.ins` manifests, dependency graphs, and package source layout. `package test` discovers test files from the manifest test directory and runs them with the package source directory plus direct dependency exposed modules as import roots. `package build` emits package-aware artifacts through the existing compile pipeline. `format` is parse-only and does not need LLVM tools. `highlight` uses the same Inscription lexer used by this book.

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

`package check` exits 0 on a valid manifest/layout/dependency graph and exits 2 for manifest, package, compiler, or tool diagnostics. `package test` exits 0 when all selected tests pass, exits 1 for runtime test failures, and exits 2 for package/compiler/tool diagnostics. `package build` exits 0 on success and exits 2 for package/compiler/tool diagnostics; its default output is `build/lib<Package>.a`.
