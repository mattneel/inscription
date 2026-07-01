# Inscription

Inscription is a deterministic, phrase-shaped systems language that lowers to MLIR and LLVM 22. It uses prose-punctuation syntax: declarations and steps are sentences, phrases are introduced with `To ... .`, and returning phrases end with explicit `Give ... .` sentences.

```inscription
To main, giving i32.
Give 7.
```

The full language guide now lives in **[The Inscription Book](book/src/title-page.md)**. Once GitHub Pages is enabled for this repository, the hosted book is expected at <https://mattneel.github.io/inscription/>. Historical sprint specifications remain in [`docs/`](docs), and grammar mirrors remain in [`grammar/`](grammar).

## Status

This repository currently implements **Inscription v0.53: documentation build steps**. v0.53 extends the narrow interpreted `build.ins` package build script with sandboxed mdBook documentation steps on top of named groups, defaults, package check/test steps, and artifact requests. The existing v0.49 `comptime` scalar evaluation, v0.48 interpreter groundwork, v0.47 package path dependencies, package-aware static libraries, executables, LLVM IR, interface JSON, and C headers, first-class source tests, comments, documentation comments, owned buffer literal/copy initialization, pattern alternatives, integer ranges, match guards, exhaustive matches, and move-aware owned-buffer control flow remain available. The mdBook documentation site remains the primary language guide.

The current language includes:

- scalar integer, float, and boolean types
- deterministic prose-punctuation syntax, `then` parent continuations, canonical formatter, ordinary comments, documentation comments, first-class tests, test-time `Expect` assertions, declarative package manifests, narrow interpreted build scripts, and pure-subset interpreter groundwork
- modules, imports, package-aware module roots, local path dependencies, package build artifact routing, and `build.ins` named artifact/check/test/group/book steps
- constants, checks, `comptime` scalar/enum phrase-call evaluation, runtime `Require`, and optional `--runtime-checks`
- phrases, extern declarations, and scalar exported phrases
- records, layout records, nominal enums, tagged unions, exhaustive matches, wildcard `anything` patterns, match guards, pattern alternatives, integer ranges, and ignored union payload fields
- buffers, arrays, borrowed views, byte literals, and byte-string storage initialization
- owned dynamic buffers with lexical cleanup, owned-buffer returns, explicit consuming `move` calls, owned temporary moves, move-aware branch/match control flow, owned literal initialization, and explicit owned-buffer copies from storage
- MLIR, LLVM IR, object, executable, static-library, interface JSON with documentation metadata, and C header emission with exported phrase docs

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

Run source-level tests:

```sh
PYTHONPATH=src python -m inscription test tests/fixtures/positive/test_basic.ins
PYTHONPATH=src python -m inscription test tests/fixtures/positive/test_basic.ins --list
PYTHONPATH=src python -m inscription test tests/fixtures/positive/test_basic.ins --filter addition
```

Validate, test, and build a package:

```sh
PYTHONPATH=src python -m inscription package check tests/fixtures/packages/basic_package
PYTHONPATH=src python -m inscription package test tests/fixtures/packages/basic_package
PYTHONPATH=src python -m inscription package test tests/fixtures/packages/basic_package --list
PYTHONPATH=src python -m inscription package test tests/fixtures/packages/app_with_dependency --include-dependencies
PYTHONPATH=src python -m inscription package build tests/fixtures/packages/library_package --emit c-header -o ProtocolTools.h
PYTHONPATH=src python -m inscription package build tests/fixtures/packages/library_package --emit static-library -o libProtocolTools.a
PYTHONPATH=src python -m inscription build tests/fixtures/packages/build_script_package --list
PYTHONPATH=src python -m inscription build tests/fixtures/packages/build_script_package library
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

Source comments are line-oriented. `//` comments are ignored by semantics, `///` documents the next top-level declaration, and `//!` documents the module or root unit. Documentation comments appear in interface JSON, and exported phrase docs are emitted as C comments in generated headers.

```inscription
//! Protocol helpers.

/// Exported answer.
To answer, giving i32, exported as ins_answer.
// Ordinary body comment.
Give 42.
```

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

Source-level tests are top-level declarations. They use normal Inscription steps plus test-only `Expect` sentences, do not require `main`, and are ignored by ordinary `run`, C headers, and interface JSON.

```inscription
To add left: i32 and right: i32, giving i32.
Give left plus right.

Test addition works.
Expect add 20 and 22 is equal to 42.
```

Run them with `inscription test SOURCE`; use `--list` to list discovered tests and `--filter TEXT` to run matching test display names.

Package manifests live in `package.ins`. They are declarative metadata, not executable build scripts: package metadata, source/test directory layout, a root module, exposed module validation, local path dependencies, and package-aware artifact builds stay parse-only. v0.53 extends optional `build.ins` interpreted build scripts with mdBook documentation steps on top of named groups, defaults, package check/test workflow steps, and standard artifacts, while remote dependencies, registries, lockfiles, version solvers, arbitrary filesystem/process APIs, and custom build graph scripting remain out of scope.

```inscription
//! Package manifest for ProtocolTools.

Package ProtocolTools.

Version "0.1.0".

Sources are in "src".
Tests are in "tests".

Root module is ProtocolTools.

Expose module ProtocolTools.
Expose module ProtocolTools.Protocol.

Depend on Checksums from path "../checksums".
```

Run `inscription package check` to validate the manifest, source layout, and dependency graph. Run `inscription package test` to discover `.ins` test files under the manifest's test directory using the package source directory and direct dependency exposed modules for imports; add `--include-dependencies` to run dependency package tests. Run `inscription package build` to emit package artifacts; the default artifact is `build/lib<Package>.a`, and root package headers intentionally omit dependency exports.

Optional build scripts live in `build.ins`. They are interpreted build logic, not declarative package metadata. v0.53 requires `Import Build.` and a does phrase named `build package` that takes an opaque `Build.Package` parameter. Build API calls record named package validation, test, artifact, documentation, and group steps; the driver then dispatches them through existing package check/test/build machinery with deterministic group dependencies.

```inscription
Import Build.

To build package package: Build.Package.
Build.check package named "check".
Build.tests named "tests".
Build.static library named "library".
Build.c header named "header".
Build.interface json named "interface".
Build.executable named "app".
Build.book checked named "book".
Build.group named "ci" with steps "check" and "tests" and "book".
Build.default step is "ci".
```

Run `inscription build path/to/package --list` to list steps and the default, `inscription build path/to/package ci` to run a group, `inscription build path/to/package library` to build one artifact step, or `inscription build path/to/package` to run the declared default step. If no default is declared, a bare build preserves source-order ordinary step execution and skips groups unless requested. Step names are simple names, not paths; outputs go under `build/`. Build scripts cannot import package modules, call externs, spawn arbitrary processes, read arbitrary files, perform arbitrary I/O, deploy docs, or define custom output paths in v0.53.


## Compile-time evaluation and interpreter groundwork

v0.49 adds `comptime phrase call` expressions for pure scalar/enum compile-time execution:

```inscription
To square x: i32, giving i32.
Give x times x.

Constant sixteen: i32 be comptime square 4.
```

`comptime` calls are evaluated by the internal deterministic interpreter and emit ordinary constants; no runtime call is lowered. v0.49 supports scalar and enum arguments/results, pure phrase calls, control flow, matches, guards, alternatives, ranges, casts, and arithmetic. It intentionally rejects storage, owned buffers, views, extern calls, unsupported result types, and step-limit exhaustion. `package.ins` remains declarative. `build.ins` uses the same interpreter groundwork for a restricted build-script surface with check/test/build/group/book steps, and `comptime` remains separate from macros or reflection.

v0.48 introduced `src/inscription/interpreter.py`, an internal deterministic interpreter for checked pure phrases over scalar, enum, record, layout-record-as-value, and union values. It supports selected expression and control-flow evaluation for compiler tests and static tooling, with deterministic diagnostics for unsupported features. It is not a stable user-facing runtime interpretation mode.

## Documentation map

- [`book/src/SUMMARY.md`](book/src/SUMMARY.md): table of contents for The Inscription Book
- [`book/src/tooling/packages.md`](book/src/tooling/packages.md): package manifest and package command guide
- [`book/tools/check_book_examples.py`](book/tools/check_book_examples.py): deterministic book example checker
- [`book/tools/inscription_mdbook_preprocessor.py`](book/tools/inscription_mdbook_preprocessor.py): mdBook preprocessor that reuses Inscription's own highlighter
- [`docs/github-pages.md`](docs/github-pages.md): GitHub Pages setup notes
- [`docs/inscription-v0.53-spec.md`](docs/inscription-v0.53-spec.md): current language sprint spec
- [`grammar/inscription-v0.53.ebnf`](grammar/inscription-v0.53.ebnf): current grammar mirror

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
