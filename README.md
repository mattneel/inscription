# Inscription

Inscription is a deterministic, phrase-shaped compiler that lowers a small prose-like v0 language to MLIR and executes through LLVM 22.

The language is readable, but it is **not** natural-language interpretation: every accepted line matches the grammar exactly. The core idea is that a phrase definition introduces a callable phrase, and each block evaluates to a value.

## Status

This repository currently implements **Inscription v0**:

- signed `i32` values only
- phrase-shaped function definitions and phrase-shaped calls
- value blocks with `expression when condition` and `otherwise expression`
- `let name be expression` bindings before a value block
- deterministic parsing and semantic checks
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

`run` returns the compiled program's `main` result as the `lli` process exit status, so fixture results are expected to be in `0..255`.

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
<phrase with typed holes> gives i32:
  <value block>
```

A typed hole is written `name: i32`. The call site mirrors the definition by filling the holes:

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
align address: i32 to boundary: i32 gives i32:
  let mask be boundary minus 1
  address plus mask
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
- `main gives i32:` must exist and take no holes
- all holes, bindings, and return values are `i32`
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
tests/                      unit tests and executable fixtures
```
