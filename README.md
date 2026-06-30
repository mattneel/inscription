# Inscription

Inscription is a deterministic, phrase-shaped systems language that lowers to MLIR and LLVM 22. It uses prose-punctuation syntax: declarations and steps are sentences, phrases are introduced with `To ... .`, and returning phrases end with explicit `Give ... .` sentences.

```inscription
To main, giving i32.
Give 7.
```

The full language guide now lives in **[The Inscription Book](book/src/title-page.md)**. Once GitHub Pages is enabled for this repository, the hosted book is expected at <https://mattneel.github.io/inscription/>. Historical sprint specifications remain in [`docs/`](docs), and grammar mirrors remain in [`grammar/`](grammar).

## Status

This repository currently implements **Inscription v0.34: explicit `then` parent-continuation clauses**. v0.34 keeps the v0.33 compiler semantics and lowering while adding `; then ...` as a punctuation marker that resumes a parent clause list after nested `For`, `While`, or `Match` control. The mdBook documentation site remains the primary language guide.

The current language includes:

- scalar integer, float, and boolean types
- deterministic prose-punctuation syntax, `then` parent continuations, and canonical formatter
- modules and imports
- constants, checks, runtime `Require`, and optional `--runtime-checks`
- phrases, extern declarations, and scalar exported phrases
- records, layout records, nominal enums, and tagged unions
- buffers, arrays, borrowed views, byte literals, and byte-string storage initialization
- owned dynamic buffers with lexical cleanup and owned-buffer returns
- MLIR, LLVM IR, object, executable, static-library, interface JSON, and C header emission

See the book for the tutorial, language guide, tooling guide, examples, and reference links.

## Quick setup

Requirements:

- Python 3.11+
- LLVM/MLIR 22 tools (`mlir-opt`, `mlir-translate`, `lli`; additional artifact modes use `llc`, `clang`, and `llvm-ar`)
- mdBook for the documentation site

Install from a checkout:

```sh
python -m pip install -e ".[docs]"
export MLIR_TOOLCHAIN=/usr/lib/llvm-22/bin
PYTHONPATH=src python -m inscription check-tools --show-pipeline
```

## Quick commands

Compile and verify source MLIR:

```sh
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/phrase_max.ins --verify
```

Run a program:

```sh
PYTHONPATH=src python -m inscription run tests/fixtures/positive/phrase_max.ins
```

Format source:

```sh
PYTHONPATH=src python -m inscription format tests/fixtures/positive/phrase_max.ins --check
PYTHONPATH=src python -m inscription format path/to/file.ins --in-place
```

Emit artifacts:

```sh
PYTHONPATH=src python -m inscription compile path/to/file.ins --emit llvm-ir --verify -o file.ll
PYTHONPATH=src python -m inscription compile path/to/file.ins --emit executable -o file
PYTHONPATH=src python -m inscription compile path/to/file.ins --emit interface-json -o interface.json
PYTHONPATH=src python -m inscription compile path/to/file.ins --emit c-header -o interface.h
```

Build the book locally:

```sh
python -m pip install -e ".[docs]"
python book/tools/check_book_examples.py
mdbook build book
```

Serve the book during editing:

```sh
mdbook serve book --open
```


Nested punctuation control is greedy by default. Use `then` to resume the parent clause list after a nested controller:

```inscription
To nested for then, giving i32.
Let total be 0.
Let rows be 0.
For i from 0 up to 3: For j from 0 up to 3: total becomes total plus 1; then rows becomes rows plus 1.
Give total plus rows.
```

## Documentation map

- [`book/src/SUMMARY.md`](book/src/SUMMARY.md): table of contents for The Inscription Book
- [`book/tools/check_book_examples.py`](book/tools/check_book_examples.py): deterministic book example checker
- [`book/tools/inscription_mdbook_preprocessor.py`](book/tools/inscription_mdbook_preprocessor.py): mdBook preprocessor that reuses Inscription's own highlighter
- [`docs/github-pages.md`](docs/github-pages.md): GitHub Pages setup notes
- [`docs/inscription-v0.34-spec.md`](docs/inscription-v0.34-spec.md): current language sprint spec
- [`grammar/inscription-v0.34.ebnf`](grammar/inscription-v0.34.ebnf): current grammar mirror

## Testing

Run the compiler and documentation tests:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python -m py_compile src/inscription/*.py tests/test_inscription.py book/tools/*.py
git diff --check
python book/tools/check_book_examples.py
mdbook build book
```

The unit suite includes exact source-MLIR golden tests, artifact smoke tests, formatter tests, and local book structure/preprocessor/checker tests. Some artifact or highlighter tests skip when optional LLVM/Pygments tools are unavailable.

## GitHub Pages

The `.github/workflows/book.yml` workflow builds the book on pull requests and deploys it on pushes to `master` or manual dispatches. In repository **Settings → Pages**, set the Pages source to **GitHub Actions**. See [`docs/github-pages.md`](docs/github-pages.md).
