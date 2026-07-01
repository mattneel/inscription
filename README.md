# Inscription

Inscription is a deterministic, phrase-shaped systems language that lowers to MLIR and LLVM 22. It uses prose-punctuation syntax: declarations and steps are sentences, phrases are introduced with `To ... .`, and returning phrases end with explicit `Give ... .` sentences.

```inscription
To main, giving i32.
Give 7.
```

The full language guide now lives in **[The Inscription Book](book/src/title-page.md)**. Once GitHub Pages is enabled for this repository, the hosted book is expected at <https://mattneel.github.io/inscription/>. Historical sprint specifications remain in [`docs/`](docs), and grammar mirrors remain in [`grammar/`](grammar).

## Status

This repository currently implements **Inscription v0.42: owned buffer literal and copy initialization**. v0.42 adds `owned buffer ... containing ...`, mutable owned byte-string buffers with `owned buffer of bytes "..."`, and explicit `owned buffer copied from source` initialization on top of pattern alternatives, integer ranges, match guards, exhaustive matches, and move-aware owned-buffer control flow. The mdBook documentation site remains the primary language guide.

The current language includes:

- scalar integer, float, and boolean types
- deterministic prose-punctuation syntax, `then` parent continuations, and canonical formatter
- modules and imports
- constants, checks, runtime `Require`, and optional `--runtime-checks`
- phrases, extern declarations, and scalar exported phrases
- records, layout records, nominal enums, tagged unions, exhaustive matches, wildcard `anything` patterns, match guards, pattern alternatives, integer ranges, and ignored union payload fields
- buffers, arrays, borrowed views, byte literals, and byte-string storage initialization
- owned dynamic buffers with lexical cleanup, owned-buffer returns, explicit consuming `move` calls, owned temporary moves, move-aware branch/match control flow, owned literal initialization, and explicit owned-buffer copies from storage
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

Owned buffers can be consumed by normal phrases only with an explicit `move` actual:

```inscription
To consume cells cells: owned buffer of i32, giving i32.
Give length of cells.

To main, giving i32.
Let cells be owned buffer of 7 i32 filled with 1.
Give consume cells move cells.
```

After `move cells`, the caller binding is consumed and the callee owns cleanup unless it returns or moves the buffer onward. Borrowing through `view of TYPE` remains non-consuming and does not use `move`.

Owned-buffer-returning phrase calls can also be moved directly into consuming parameters when parenthesized:

```inscription
To make cells count: i32, giving owned buffer of i32.
Let cells be owned buffer of count i32 filled with 1.
Give cells.

To main, giving i32.
Give consume cells move (make cells 7).
```

Bind the returned buffer first when you need to inspect, borrow, or reuse it; direct temporaries are consumed immediately and cannot be used as scalar values or view arguments.

All paths through non-loop control flow may move the same outer owned buffer. Mixed move/live branches are rejected, and loops still reject moving outer-scope owned buffers:

```inscription
To branch move all flag: i1, giving i32.
Let cells be owned buffer of 4 i32 filled with 1.
Let result be 0.
When flag, result becomes consume cells move cells.
Otherwise, result becomes consume cells move cells.
Give result.
```

Owned buffers can also be initialized with explicit data or copied into fresh owned storage:

```inscription
To owned data, giving i32.
Let cells be owned buffer of 4 i32 containing 1, 2, 3, 4.
Let bytes be owned buffer of bytes "hello".
Let copy be owned buffer copied from cells.
copy at 0 becomes 10.
Give copy at 0 plus cells at 0 plus length of bytes.
```

`owned buffer copied from source` is an explicit element-wise copy from a buffer, array, view, or owned buffer. It does not consume the source; `move` remains the only ownership-transfer syntax. Zero-length owned buffers are still unsupported, and byte strings are byte storage rather than heap strings.

Enum, union, and boolean matches can be written without `otherwise` when every case is covered. Use `anything` as an explicit wildcard catch-all. Match arms may also use lowercase `when` guards; guarded arms are tested in source order and do not count toward exhaustiveness. Direct enum cases, booleans, integer literals, byte literals, and payload-free union variants can be combined with `or`, and integer scalar matches can use inclusive `through` ranges:

```inscription
Enum Mode backed by u8 has idle be 0; active be 1; failed be 2.

To code for mode mode: Mode, giving i32.
Give match mode:
Mode.idle or Mode.failed gives 0;
Mode.active gives 7.

To classify byte b: u8 and enabled: i1, giving i32.
Give match b:
byte "0" through byte "9" or byte "A" through byte "F" when enabled gives 7;
anything gives 1.
```

Union payload fields can be ignored without binding a name:

```inscription
Union Token has eof; operator symbol: u8 and precedence: u8.

To precedence token token: Token, giving i32.
Give match token:
Token.operator with symbol ignored and precedence as prec gives prec as i32;
anything gives 0.
```

## Documentation map

- [`book/src/SUMMARY.md`](book/src/SUMMARY.md): table of contents for The Inscription Book
- [`book/tools/check_book_examples.py`](book/tools/check_book_examples.py): deterministic book example checker
- [`book/tools/inscription_mdbook_preprocessor.py`](book/tools/inscription_mdbook_preprocessor.py): mdBook preprocessor that reuses Inscription's own highlighter
- [`docs/github-pages.md`](docs/github-pages.md): GitHub Pages setup notes
- [`docs/inscription-v0.42-spec.md`](docs/inscription-v0.42-spec.md): current language sprint spec
- [`grammar/inscription-v0.42.ebnf`](grammar/inscription-v0.42.ebnf): current grammar mirror

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
