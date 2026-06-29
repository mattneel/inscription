# Inscription

Inscription is a deterministic, phrase-shaped compiler that lowers a small prose-like v0 language to MLIR and executes through LLVM 22.

The language is readable, but it is **not** natural-language interpretation: every accepted line matches the grammar exactly. The core idea is that a phrase definition introduces a callable phrase, and each block evaluates to a value.

## Status

This repository currently implements **Inscription v0**:

- source-visible scalar types: `i1`, `i32`, and `i64`
- phrase-shaped function definitions and phrase-shaped calls
- value blocks with `expression when condition` and `otherwise expression`
- implicit returns: the block value is the phrase result
- `let name be expression` bindings before a value block
- integer arithmetic: `plus`, `minus`, `times`, and `divided by`
- comparison expressions that evaluate to `i1`
- parenthesized expressions
- deterministic parsing and semantic checks
- exact MLIR golden conformance tests in [`tests/goldens`](tests/goldens)
- MLIR emission using `func`, `arith`, and `scf.if`
- LLVM 22 lowering and execution through `mlir-opt`, `mlir-translate`, and `lli`
- no source-level I/O, arrays, floats, pointers, memrefs, mutable storage, statement-level `return`, or natural-language inference

See [`docs/inscription-v0-spec.md`](docs/inscription-v0-spec.md) and [`grammar/inscription-v0.ebnf`](grammar/inscription-v0.ebnf) for the exact language contract.

## Requirements

- Python 3.11+
- Pygments for the `highlight` command; installed automatically from `pyproject.toml`
- LLVM/MLIR 22 tools:
  - `mlir-opt`
  - `mlir-translate`
  - `lli`

Tool discovery is intentionally strict. The CLI uses `MLIR_TOOLCHAIN` when set; otherwise it checks `/usr/lib/llvm-22/bin`. All required tools must report LLVM/MLIR `22.x`.

```sh
export MLIR_TOOLCHAIN=/usr/lib/llvm-22/bin
PYTHONPATH=src python -m inscription check-tools --show-pipeline
```

The lowering pipeline is:

```sh
mlir-opt input.mlir \
  --convert-scf-to-cf \
  --convert-cf-to-llvm \
  --convert-arith-to-llvm \
  --convert-func-to-llvm \
  --reconcile-unrealized-casts \
  -o lowered.mlir
mlir-translate --mlir-to-llvmir lowered.mlir -o output.ll
lli output.ll
```

## Quick start

Run directly from a checkout:

```sh
PYTHONPATH=src python -m inscription check-tools --show-pipeline
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/phrase_max.ins --verify
PYTHONPATH=src python -m inscription run tests/fixtures/positive/phrase_max.ins
```

Or install an editable copy:

```sh
python -m pip install -e .
inscription check-tools --show-pipeline
inscription compile tests/fixtures/positive/phrase_max.ins --verify
inscription highlight tests/fixtures/positive/phrase_max.ins
inscription run tests/fixtures/positive/phrase_max.ins
```

`compile` accepts library-style source files without `main`. `run` executes the lowered module through `lli`; executable fixtures define a no-hole `main` and return an exit status in `0..255`.

## Example program

```text
max of a: i32 and b: i32 gives i32:
  a when a is greater than b
  otherwise b

main gives i32:
  max of 7 and 3
```

Compile it to MLIR:

```sh
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/phrase_max.ins --verify
```

Run it:

```sh
PYTHONPATH=src python -m inscription run tests/fixtures/positive/phrase_max.ins
echo $?
# 7
```

## CLI

```sh
python -m inscription compile SOURCE [-o OUTPUT] [--verify]
python -m inscription highlight SOURCE [-o OUTPUT] [--format terminal|html] [--style STYLE] [--full]
python -m inscription run SOURCE
python -m inscription check-tools [--show-pipeline]
```

Commands return `2` for compiler, diagnostic, toolchain, or filesystem errors.

`highlight` uses Pygments with a built-in Inscription lexer. The default output is ANSI-colored terminal text. Use `--format html --full -o file.html` to emit a complete HTML document.

## Language summary

A program is a list of phrase definitions:

```text
<phrase with typed holes> gives <type>:
  <value block>
```

A type is one of `i1`, `i32`, or `i64`. A typed hole is written `name: type`. The call site mirrors the definition by filling the holes:

```text
square of n: i32 gives i32:
  n times n

main gives i32:
  square of 12
```

Conditional value blocks return the first matching line, with a required fallback:

```text
absolute value of n: i32 gives i32:
  zero minus n when n is less than zero
  otherwise n
```

Multiple conditional lines lower to nested `scf.if` result expressions:

```text
clamp x: i32 between low: i32 and high: i32 gives i32:
  low when x is less than low
  high when x is greater than high
  otherwise x
```

Bindings are expression helpers and must appear before the value block:

```text
average of left: i32 and right: i32 gives i32:
  let total be left plus right
  total divided by 2
```

`i64` definitions are supported:

```text
factorial of n: i64 gives i64:
  1 when n is less than or equal to 1
  otherwise n times factorial of (n minus 1)
```

Comparison expressions return `i1`:

```text
is zero x: i32 gives i1:
  x is equal to 0
```

Expressions:

```text
120
zero
name
square of 12
max of 7 and 3
left plus right
left minus right
left times right
left divided by right
(a plus b) times 2
x is equal to 0
```

Comparisons:

```text
left is equal to right
left is not equal to right
left is less than right
left is less than or equal to right
left is greater than right
left is greater than or equal to right
```

Important v0 rules:

- function names are generated from the leading literal words in a phrase definition
- phrase names are unique; there is no overloading in v0
- library compilation does not require `main`; if `main` exists, it must take no holes
- arithmetic operands must be numeric (`i32` or `i64`)
- comparisons require numeric operands and return `i1`
- variables must be initialized by a phrase hole or prior `let`
- phrase calls must match a declared phrase template exactly
- conditional value blocks require `otherwise`
- removed ceremony words such as `Function`, `End function`, `Set`, `Return`, and `call ... with` are not valid Inscription syntax
- unsupported I/O, arrays, floats, pointers, memrefs, mutable storage, and free prose are rejected

## Tests

Run the full test suite:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
```

The suite includes exact MLIR golden conformance files under [`tests/goldens`](tests/goldens). Each `*.ins` source must compile byte-for-byte to its sibling `*.mlir`.

With LLVM/MLIR 22 available, verify the toolchain and fixture exit codes:

```sh
PYTHONPATH=src python -m inscription check-tools --show-pipeline
PYTHONPATH=src python -m inscription run tests/fixtures/positive/add.ins                 # exits 5
PYTHONPATH=src python -m inscription run tests/fixtures/positive/phrase_max.ins          # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/recursive_factorial.ins # exits 120
PYTHONPATH=src python -m inscription run tests/fixtures/positive/clamp.ins               # exits 255
```

## Repository layout

```text
src/inscription/            compiler implementation
docs/inscription-v0-spec.md language and toolchain specification
grammar/inscription-v0.ebnf formal v0 grammar
tests/goldens/              exact MLIR v0 conformance goldens
tests/                      unit tests and executable fixtures
```
