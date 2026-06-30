# CLI

Common commands:

```sh
PYTHONPATH=src python -m inscription compile SOURCE --verify
PYTHONPATH=src python -m inscription run SOURCE
PYTHONPATH=src python -m inscription format SOURCE --check
PYTHONPATH=src python -m inscription highlight SOURCE
PYTHONPATH=src python -m inscription check-tools --show-pipeline
```

`compile` emits artifacts without executing the program. `run` lowers through LLVM 22 and executes with `lli`. `format` is parse-only and does not need LLVM tools. `highlight` uses the same Inscription lexer used by this book.
