# CLI

Common commands:

```sh
PYTHONPATH=src python -m inscription compile SOURCE --verify
PYTHONPATH=src python -m inscription run SOURCE
PYTHONPATH=src python -m inscription test SOURCE
PYTHONPATH=src python -m inscription format SOURCE --check
PYTHONPATH=src python -m inscription highlight SOURCE
PYTHONPATH=src python -m inscription check-tools --show-pipeline
```

`compile` emits artifacts without executing the program. `run` lowers through LLVM 22 and executes `main` with `lli`. `test` discovers top-level `Test ... .` declarations, compiles each selected test through the MLIR/LLVM pipeline, and reports a deterministic summary. `format` is parse-only and does not need LLVM tools. `highlight` uses the same Inscription lexer used by this book.

Useful test options:

```sh
PYTHONPATH=src python -m inscription test SOURCE --list
PYTHONPATH=src python -m inscription test SOURCE --filter addition
PYTHONPATH=src python -m inscription test SOURCE --runtime-checks
PYTHONPATH=src python -m inscription test SOURCE --save-temps /tmp/inscription-test-temps
```

`test` exits 0 when all selected tests pass, exits 1 when any selected test fails at runtime, and exits 2 for compiler/tooling diagnostics.
