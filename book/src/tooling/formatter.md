# Formatter

The formatter canonicalizes punctuation syntax.

```sh
PYTHONPATH=src python -m inscription format source.ins
PYTHONPATH=src python -m inscription format source.ins -o formatted.ins
PYTHONPATH=src python -m inscription format source.ins --in-place
PYTHONPATH=src python -m inscription format source.ins --check
```

`--check` exits 0 when the file is already formatted and exits 2 with a deterministic diagnostic when it would change. The formatter does not sort imports or declarations, simplify expressions, infer missing punctuation, or run semantic lowering.
