# Inscription

Inscription is a deterministic, prose-shaped compiler that lowers a small v0 language to MLIR and executes through LLVM 22.

The language looks like restricted English, but it is **not** a natural-language interface: every accepted line must match the fixed grammar exactly. Unsupported prose is rejected with a diagnostic instead of being guessed or interpreted.

## Status

This repository currently implements **Inscription v0**:

- signed `i32` values only
- functions, calls, variables, `if`/`otherwise`, `while`, and `return`
- deterministic parsing and semantic checks
- MLIR emission using `func`, `arith`, and `scf`
- LLVM 22 lowering and execution through `mlir-opt`, `mlir-translate`, and `lli`
- no source-level I/O, arrays, floats, pointers, memrefs, storage dialects, or natural-language inference

See [`docs/inscription-v0-spec.md`](docs/inscription-v0-spec.md) and [`grammar/inscription-v0.ebnf`](grammar/inscription-v0.ebnf) for the exact language contract.

## Requirements

- Python 3.11+
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
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/add.ins --verify
PYTHONPATH=src python -m inscription run tests/fixtures/positive/add.ins
```

Or install an editable copy:

```sh
python -m pip install -e .
inscription check-tools --show-pipeline
inscription compile tests/fixtures/positive/add.ins --verify
inscription run tests/fixtures/positive/add.ins
```

`run` returns the compiled program's `main` result as the `lli` process exit status, so fixture results are expected to be in `0..255`.

## Example program

```text
Function add takes a and b.
Return a plus b.
End function.

Function main takes no parameters.
Set result to call add with 2 and 3.
Return result.
End function.
```

Compile it to MLIR:

```sh
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/add.ins --verify
```

Run it:

```sh
PYTHONPATH=src python -m inscription run tests/fixtures/positive/add.ins
echo $?
# 5
```

## CLI

```sh
python -m inscription compile SOURCE [-o OUTPUT] [--verify]
python -m inscription run SOURCE
python -m inscription check-tools [--show-pipeline]
```

Commands return `2` for compiler, diagnostic, toolchain, or filesystem errors.

## Language summary

A program is a list of function definitions:

```text
Function name takes no parameters.
Function name takes a and b.
Function name takes a, b, and c.
End function.
```

Statements:

```text
Set name to expression.
If comparison then.
  ...
Otherwise.
  ...
End if.
While comparison do.
  ...
End while.
Return expression.
```

Expressions:

```text
120
name
call add with 2 and 3
call zero with no arguments
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

- every nonblank source line ends with `.`
- identifiers match `[a-z][a-z0-9_]*` and cannot be reserved words
- function names are unique
- calls must target known functions with the exact arity
- variables must be initialized before use
- `main` must exist, take no parameters, and return `i32`
- `if` always requires `Otherwise`
- variables assigned in `while` must already exist before the loop
- early `Return` inside `if`, `otherwise`, or `while` blocks is not part of v0

## Tests

Run the full test suite:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
```

With LLVM/MLIR 22 available, verify the toolchain and fixture exit codes:

```sh
PYTHONPATH=src python -m inscription check-tools --show-pipeline
PYTHONPATH=src python -m inscription run tests/fixtures/positive/add.ins              # exits 5
PYTHONPATH=src python -m inscription run tests/fixtures/positive/max_call.ins         # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/while_factorial.ins  # exits 120
PYTHONPATH=src python -m inscription run tests/fixtures/positive/recursive_factorial.ins # exits 120
```

## Repository layout

```text
src/inscription/            compiler implementation
docs/inscription-v0-spec.md language and toolchain specification
grammar/inscription-v0.ebnf formal v0 grammar
tests/                      unit tests and executable fixtures
```
