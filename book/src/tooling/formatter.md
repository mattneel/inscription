# Formatter

The formatter canonicalizes punctuation syntax.

```sh
PYTHONPATH=src python -m inscription format source.ins
PYTHONPATH=src python -m inscription format source.ins -o formatted.ins
PYTHONPATH=src python -m inscription format source.ins --in-place
PYTHONPATH=src python -m inscription format source.ins --check
```

`--check` exits 0 when the file is already formatted and exits 2 with a deterministic diagnostic when it would change. The formatter does not sort imports or declarations, simplify expressions, infer missing punctuation, or run semantic lowering.

The formatter preserves `then` parent-continuation clauses in nested punctuation control flow:

```inscription,format
To nested for then, giving i32.
Let total be 0.
Let rows be 0.
For i from 0 up to 3: For j from 0 up to 3: total becomes total plus 1; then rows becomes rows plus 1.
Give total plus rows.
```


Package manifests are formatted in manifest mode when the file is named `package.ins` or the first non-comment declaration is `Package`:

```inscription,manifest
Package ProtocolTools.

Version "0.1.0".

Sources are in "src".
Tests are in "tests".

Root module is ProtocolTools.

Expose module ProtocolTools.
```

## Package formatting

Packages can run the formatter over package-owned Inscription files discovered from `package.ins`:

```sh
PYTHONPATH=src python -m inscription package format path/to/package --check
PYTHONPATH=src python -m inscription package format path/to/package --in-place
PYTHONPATH=src python -m inscription package format path/to/package --check --include-dependencies
PYTHONPATH=src python -m inscription package format path/to/package --check --include-book
```

The package formatter checks or rewrites `package.ins`, `build.ins` when present, all `.ins` files under the sources directory, and all `.ins` files under the tests directory. It is parse/format-only and does not require LLVM tools. Book inclusion is check-only in v0.58; fenced snippets are checked by the package's `book/tools/check_book_examples.py` when present.
