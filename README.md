# Inscription

Inscription is a deterministic, phrase-shaped compiler that lowers a small prose-like language to MLIR and executes through LLVM 22.

The language is readable, but it is **not** natural-language interpretation: every accepted line matches the grammar exactly. The core idea is that a phrase definition introduces a callable phrase, and each block evaluates to a value.

## Status

This repository currently implements **Inscription v0.3**:

- source-visible scalar types: `i1`, signed integers `i8`/`i16`/`i32`/`i64`, and unsigned integers `u8`/`u16`/`u32`/`u64`
- phrase-shaped function definitions and phrase-shaped calls
- value blocks with `expression when condition` and `otherwise expression`
- implicit returns: the block value is the phrase result
- local bindings with `let name be expression` and `let name: type be expression`
- rebinding visible local bindings with `name becomes expression`
- `while condition:` step blocks lowered as loop-carried SSA values through `scf.while`
- nested `while` loops
- step-level `if condition:` / `otherwise:` blocks lowered through `scf.if` SSA results
- integer arithmetic: `plus`, `minus`, `times`, `divided by`, and `remainder`
- bitwise integer operators: `bitwise and`, `bitwise or`, `bitwise xor`, and `bitwise not`
- integer shifts: `shifted left by` and `shifted right by`
- explicit integer casts with postfix `as type`
- boolean literals: `true` and `false`
- boolean operators: `and`, `or`, and `not`
- comparison expressions that evaluate to `i1`
- parenthesized expressions
- deterministic parsing and semantic checks
- exact MLIR golden conformance tests in [`tests/goldens`](tests/goldens)
- MLIR emission using `func`, `arith`, `scf.if`, and `scf.while`
- LLVM 22 lowering and execution through `mlir-opt`, `mlir-translate`, and `lli`
- no source-level I/O, arrays, floats, pointers, memrefs, storage allocation, statement-level `return`, `break`, `continue`, or natural-language inference

See [`docs/inscription-v0.3-spec.md`](docs/inscription-v0.3-spec.md) and [`grammar/inscription-v0.3.ebnf`](grammar/inscription-v0.3.ebnf) for the exact current language contract. The immutable previous contracts remain in [`docs/inscription-v0-spec.md`](docs/inscription-v0-spec.md), [`docs/inscription-v0.1-spec.md`](docs/inscription-v0.1-spec.md), [`docs/inscription-v0.2-spec.md`](docs/inscription-v0.2-spec.md), [`grammar/inscription-v0.ebnf`](grammar/inscription-v0.ebnf), [`grammar/inscription-v0.1.ebnf`](grammar/inscription-v0.1.ebnf), and [`grammar/inscription-v0.2.ebnf`](grammar/inscription-v0.2.ebnf).

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
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/loop_sum.ins --verify
PYTHONPATH=src python -m inscription run tests/fixtures/positive/loop_sum.ins
```

Or install an editable copy:

```sh
python -m pip install -e .
inscription check-tools --show-pipeline
inscription compile tests/fixtures/positive/loop_sum.ins --verify
inscription highlight tests/fixtures/positive/loop_sum.ins
inscription run tests/fixtures/positive/loop_sum.ins
```

`compile` accepts library-style source files without `main`. `run` executes the lowered module through `lli`; executable fixtures define a no-hole `main` and return an exit status in `0..255`.

## Example program

```text
sum through n: i32 gives i32:
  let total be 0
  let i be 1
  while i is less than or equal to n:
    total becomes total plus i
    i becomes i plus 1
  total

main gives i32:
  sum through 10
```

Compile it to MLIR:

```sh
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/loop_sum.ins --verify
```

Run it:

```sh
PYTHONPATH=src python -m inscription run tests/fixtures/positive/loop_sum.ins
echo $?
# 55
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
  <body item>*
  <value block>
```

A type is one of `i1`, `i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, or `u64`. `i1` is boolean only; all other types are integer numeric types. Signedness is source-semantic: MLIR integers are signless, but Inscription signedness selects division, remainder, ordered comparison, and right-shift operations. A typed hole is written `name: type`. The call site mirrors the definition by filling the holes:

```text
square of n: i32 gives i32:
  n times n

main gives i32:
  square of 12
```

Body items may introduce local `let` bindings, rebindings, while loops, or step-level if/otherwise blocks:

```text
let total be 0
total becomes total plus 1
while total is less than 10:
  total becomes total plus 1
if total is greater than 10:
  total becomes 10
otherwise:
  total becomes total
```

A local binding is introduced with `let`. A binding is rebound with `becomes`. Rebinding lowers to SSA values, `scf.while` loop-carried results, and `scf.if` results, not memory storage.

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

Narrow, wide, signed, and unsigned integer definitions are supported:

```text
low byte of x: u32 gives u8:
  x as u8

pack high: u8 and low: u8 gives u16:
  ((high as u16) shifted left by 8) bitwise or (low as u16)
```

Comparison expressions return `i1`; boolean literals are `true` and `false`; boolean operators are strict `i1` expressions:

```text
is zero x: i32 gives i1:
  x is equal to 0

between one and ten x: i32 gives i1:
  x is greater than or equal to 1 and x is less than or equal to 10
```

There are no implicit casts between widths or signedness. Use postfix `as type` for explicit integer casts. Same-width casts change source signedness without emitting an MLIR op; narrowing emits `arith.trunci`; widening emits `arith.extsi` or `arith.extui`.

Expressions:

```text
120
zero
true
false
name
square of 12
max of 7 and 3
left plus right
left minus right
left times right
left divided by right
left remainder right
left bitwise and right
left bitwise or right
left bitwise xor right
bitwise not mask
x shifted left by amount
x shifted right by amount
x as u32
not done
left and right
left or right
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

Important v0.3 rules:

- function names are generated from the leading literal words in a phrase definition
- phrase names are unique; there is no overloading
- library compilation does not require `main`; if `main` exists, it must take no holes
- phrase holes and `let` bindings can be rebound locally with `becomes`
- rebinding a phrase hole does not mutate the caller
- each binding type is fixed after initialization or annotation
- typed `let` initializers and rebinding right-hand sides must match the binding type
- while conditions must be `i1`
- while-body lets are scoped to that loop iteration and do not escape
- nested while loops are supported
- if/otherwise conditions must be `i1`, and both branches must contain at least one step
- branch-local lets do not escape
- bindings assigned in if branches lower to `scf.if` results in source binding order
- arithmetic, bitwise, and shift operands must be matching integer numeric types, never `i1`
- source signedness controls `divided by`, `remainder`, ordered comparisons, and `shifted right by`
- comparisons require matching integer numeric operands and return `i1`
- there are no implicit casts between signed and unsigned types or between widths
- boolean `and`, `or`, and `not` require `i1` operands and return `i1`
- variables must be initialized by a phrase hole or prior visible `let`
- phrase calls must match a declared phrase template exactly
- conditional value blocks require `otherwise`
- removed ceremony words such as `Function`, `End function`, `Set`, `Return`, and `call ... with` are not valid Inscription syntax
- unsupported `track`, I/O, arrays, floats, pointers, memrefs, mutable storage lowering, and free prose are rejected

## Tests

Run the full test suite:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
```

The suite includes exact MLIR golden conformance files under [`tests/goldens`](tests/goldens). Each `*.ins` source must compile byte-for-byte to its sibling `*.mlir`.

With LLVM/MLIR 22 available, verify the toolchain and fixture exit codes:

```sh
PYTHONPATH=src python -m inscription check-tools --show-pipeline
PYTHONPATH=src python -m inscription run tests/fixtures/positive/adjust.ins              # exits 3
PYTHONPATH=src python -m inscription run tests/fixtures/positive/loop_sum.ins            # exits 55
PYTHONPATH=src python -m inscription run tests/fixtures/positive/iterative_factorial.ins # exits 120
PYTHONPATH=src python -m inscription run tests/fixtures/positive/gcd.ins                 # exits 6
PYTHONPATH=src python -m inscription run tests/fixtures/positive/collatz_steps.ins       # exits 16
PYTHONPATH=src python -m inscription run tests/fixtures/positive/nested_while_multiply.ins # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/u8_cast.ins             # exits 255
PYTHONPATH=src python -m inscription run tests/fixtures/positive/bitwise_flags.ins       # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/shifts.ins              # exits 8
PYTHONPATH=src python -m inscription run tests/fixtures/positive/unsigned_remainder.ins  # exits 5
PYTHONPATH=src python -m inscription run tests/fixtures/positive/unsigned_comparison.ins # exits 7
```

## Repository layout

```text
src/inscription/              compiler implementation
docs/inscription-v0-spec.md   original v0 language and toolchain specification
docs/inscription-v0.1-spec.md v0.1 language and toolchain specification
docs/inscription-v0.2-spec.md v0.2 language and toolchain specification
docs/inscription-v0.3-spec.md current v0.3 language and toolchain specification
grammar/inscription-v0.ebnf   original v0 grammar
grammar/inscription-v0.1.ebnf v0.1 grammar
grammar/inscription-v0.2.ebnf v0.2 grammar
grammar/inscription-v0.3.ebnf current v0.3 grammar
tests/goldens/                exact MLIR conformance goldens
tests/                        unit tests and executable fixtures
```
