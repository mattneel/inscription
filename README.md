# Inscription

Inscription is a deterministic, phrase-shaped compiler that lowers a small prose-like language to MLIR and executes through LLVM 22.

The language is readable, but it is **not** natural-language interpretation: every accepted line matches the grammar exactly. The core idea is that a phrase definition introduces a callable phrase, and each block evaluates to a value.

## Status

This repository currently implements **Inscription v0.7**:

- source-visible scalar types: `i1`, signed integers `i8`/`i16`/`i32`/`i64`, and unsigned integers `u8`/`u16`/`u32`/`u64`
- phrase-shaped function definitions and phrase-shaped calls
- value blocks with `expression when condition` and `otherwise expression`
- implicit returns: the block value is the phrase result
- local scalar bindings with `let name be expression` and `let name: type be expression`
- scalar rebinding with `name becomes expression`
- source-level value records declared with `record TypeName:` and scalar fields
- local fixed-size stack buffers with `let name be buffer of LENGTH TYPE filled with expression`
- buffer parameter holes with `name: buffer of LENGTH TYPE`
- buffer loads with `name at index` and buffer stores with `name at index becomes expression`
- static buffer length expressions with `length of name`
- local record values with constructors such as `Point with x be 1 and y be 2`
- record field reads and rebindings with `p.x` and `p.x becomes expression`
- record parameters passed by value and flattened into scalar MLIR operands
- side-effect-only `does` phrases used as standalone steps
- counted `for name from start up to end:` loops, with optional positive literal `by step`
- buffer index loops with `for each index name of buffer:`
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
- MLIR emission using `func`, `arith`, `scf.if`, `scf.for`, `scf.while`, flattened scalar SSA for records, and local `memref.alloca`/`memref.load`/`memref.store` for buffers
- LLVM 22 lowering and execution through `mlir-opt`, `mlir-translate`, and `lli`
- no source-level I/O, heap allocation, pointers, dynamic-size buffers, buffer return values, buffer aliasing, slices, ABI/layout structs, floats, strings, statement-level `return`, `break`, `continue`, overloading, type coercions, or natural-language inference

See [`docs/inscription-v0.7-spec.md`](docs/inscription-v0.7-spec.md) and [`grammar/inscription-v0.7.ebnf`](grammar/inscription-v0.7.ebnf) for the exact current language contract. The immutable previous contracts remain in [`docs/inscription-v0-spec.md`](docs/inscription-v0-spec.md), [`docs/inscription-v0.1-spec.md`](docs/inscription-v0.1-spec.md), [`docs/inscription-v0.2-spec.md`](docs/inscription-v0.2-spec.md), [`docs/inscription-v0.3-spec.md`](docs/inscription-v0.3-spec.md), [`docs/inscription-v0.4-spec.md`](docs/inscription-v0.4-spec.md), [`docs/inscription-v0.5-spec.md`](docs/inscription-v0.5-spec.md), [`docs/inscription-v0.6-spec.md`](docs/inscription-v0.6-spec.md), [`grammar/inscription-v0.ebnf`](grammar/inscription-v0.ebnf), [`grammar/inscription-v0.1.ebnf`](grammar/inscription-v0.1.ebnf), [`grammar/inscription-v0.2.ebnf`](grammar/inscription-v0.2.ebnf), [`grammar/inscription-v0.3.ebnf`](grammar/inscription-v0.3.ebnf), [`grammar/inscription-v0.4.ebnf`](grammar/inscription-v0.4.ebnf), [`grammar/inscription-v0.5.ebnf`](grammar/inscription-v0.5.ebnf), and [`grammar/inscription-v0.6.ebnf`](grammar/inscription-v0.6.ebnf).

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
  --expand-strided-metadata \
  --finalize-memref-to-llvm \
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
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/for_each_fill.ins --verify
PYTHONPATH=src python -m inscription run tests/fixtures/positive/for_each_fill.ins
```

Or install an editable copy:

```sh
python -m pip install -e .
inscription check-tools --show-pipeline
inscription compile tests/fixtures/positive/for_each_fill.ins --verify
inscription highlight tests/fixtures/positive/for_each_fill.ins
inscription run tests/fixtures/positive/for_each_fill.ins
```

`compile` accepts library-style source files without `main`. `run` executes the lowered module through `lli`; executable fixtures define a no-hole `main` and return an exit status in `0..255`.

## Example program

```text
fill buffer cells: buffer of 4 i32 with value: i32 does:
  for each index i of cells:
    cells at i becomes value

sum buffer cells: buffer of 4 i32 gives i32:
  let total be 0
  for each index i of cells:
    total becomes total plus cells at i
  total

main gives i32:
  let cells be buffer of 4 i32 filled with 0
  fill buffer cells with 7
  sum buffer cells
```

Compile it to MLIR:

```sh
PYTHONPATH=src python -m inscription compile tests/fixtures/positive/for_each_fill.ins --verify
```

Run it:

```sh
PYTHONPATH=src python -m inscription run tests/fixtures/positive/for_each_fill.ins
echo $?
# 24
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

A program is a list of top-level record declarations and phrase definitions:

```text
record TypeName:
  field: type

<phrase with typed holes> gives <type>:
  <body item>*
  <value block>

<phrase with typed holes> does:
  <body item>+
```

A scalar type is one of `i1`, `i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, or `u64`. A record type is a nominal top-level name declared with scalar fields. A buffer parameter type is written `buffer of LENGTH TYPE`, where `TYPE` is an integer numeric scalar type, not `i1`. `i1` is boolean only; all other scalar types are integer numeric types. Signedness is source-semantic: MLIR integers are signless, but Inscription signedness selects division, remainder, ordered comparison, right-shift, widening cast, and dynamic buffer-index conversion operations. A scalar typed hole is written `name: type`; a buffer typed hole is written `name: buffer of LENGTH type`. The call site mirrors the definition by filling the holes:

```text
square of n: i32 gives i32:
  n times n

main gives i32:
  square of 12
```

Records are source-level value aggregates with scalar fields. They do not have ABI layout in v0.7; the compiler flattens record fields into scalar SSA values and function operands:

```text
record Point:
  x: i32
  y: i32

sum point p: Point gives i32:
  p.x plus p.y

main gives i32:
  let p be Point with x be 10 and y be 20
  sum point p
```

Body items may introduce scalar or record `let` bindings, local buffers, scalar/record/field rebindings, buffer stores, `does` phrase calls, counted for loops, buffer index loops, while loops, or step-level if/otherwise blocks:

```text
let total be 0
total becomes total plus 1
let point be Point with x be 1 and y be 2
point.x becomes point.x plus 1
let bytes be buffer of 4 u8 filled with 0
bytes at 0 becomes 255
fill buffer bytes with 9
for i from 0 up to 4:
  total becomes total plus i
for each index i of bytes:
  bytes at i becomes 9
while total is less than 10:
  total becomes total plus 1
if total is greater than 10:
  total becomes 10
otherwise:
  total becomes total
```

A local scalar or record binding is introduced with `let`. A scalar binding, a whole record, or an individual record field is rebound with `becomes`. Rebinding lowers to SSA values, `scf.while` loop-carried results, and `scf.if` results, not memory storage.

A local buffer binding uses fixed-size stack storage:

```text
let bytes be buffer of 4 u8 filled with 0
let cells be buffer of 8 i32 filled with zero
```

Buffers are initialized with `filled with`, read with `name at index`, and written with `name at index becomes value`. `length of name` returns the static buffer length as `i32`. Buffer storage lowers to `memref.alloca`, `memref.load`, and `memref.store`. Literal indices are checked at compile time. Dynamic indices are not runtime-checked in v0.7; dynamic out-of-bounds access is undefined behavior. Buffers can be borrowed by phrase calls through buffer parameters, but cannot be returned, stored in scalar bindings, dynamically sized, heap allocated, rebound, cast, compared, or used as scalar values.


`gives` phrases return scalar values and can accept read-only buffer parameters:

```text
sum buffer cells: buffer of 4 i32 gives i32:
  let total be 0
  let i be 0
  while i is less than 4:
    total becomes total plus cells at i
    i becomes i plus 1
  total
```

`does` phrases return no value and are used as standalone steps for side effects. Buffer parameters in `does` phrases are writable:

```text
fill buffer cells: buffer of 4 i32 with value: i32 does:
  for each index i of cells:
    cells at i becomes value
```

Buffer arguments are borrowed; ownership stays with the caller. A read-only buffer parameter from a `gives` phrase cannot be passed to an effectful `does` phrase. Passing the same buffer to multiple buffer holes in one call is rejected.

Counted loops iterate from an inclusive start to an exclusive end. The start and end expressions must have the same integer numeric type, and the optional `by` step must be a positive decimal integer literal. The loop index is scoped to the loop body and is read-only:

```text
sum evens gives i32:
  let total be 0
  for i from 0 up to 10 by 2:
    total becomes total plus i
  total
```

`for each index i of buffer:` iterates over valid indices of a fixed-size buffer using an `i32` index. Scalar rebindings inside `for` loops lower through `scf.for` loop-carried SSA values; buffer writes mutate memref-backed storage.

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
bytes at i
length of bytes
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

Important v0.7 rules:

- function names are generated from the leading literal words in a phrase definition
- phrase names are unique; there is no overloading
- library compilation does not require `main`; if `main` exists, it must take no holes
- phrase holes plus scalar and record `let` bindings can be rebound locally with `becomes`
- record declarations are nominal; field names are unique and scalar-only in v0.7
- record constructors initialize fields in declaration order
- record fields are read with `p.x` and rebound with `p.x becomes expression`
- record parameters are passed by value, flattened to scalar function arguments, and callee field rebinding does not mutate the caller
- records cannot be returned, stored in buffers, nested, addressed, referenced, or used as ABI/layout structs
- rebinding a phrase hole does not mutate the caller
- each scalar binding type is fixed after initialization or annotation
- typed `let` initializers and rebinding right-hand sides must match the binding type
- buffer lengths must be positive decimal integer literals
- buffer element types must be integer numeric types, not `i1`
- buffer fill and store expressions must match the element type
- buffer parameter actuals must exactly match length and element type
- buffer parameters in `gives` phrases are read-only; buffer parameters in `does` phrases are writable
- duplicate buffer actuals in one phrase call are rejected
- `length of buffer` returns the static buffer length as `i32`
- buffer index expressions must be integer numeric types, not `i1`
- literal buffer indices must be in range; dynamic indices are not runtime-checked
- buffers are lexical storage objects and cannot be used as scalar values
- for-loop bounds must be matching integer numeric types; `up to` is exclusive
- for-loop `by` steps must be positive decimal integer literals
- for-loop index bindings are scoped to the loop body, cannot shadow visible bindings, and cannot be rebound
- scalar bindings and assigned record fields inside `for` loops lower through `scf.for` iter_args in deterministic binding/field order
- buffer writes inside `for` loops mutate memref-backed storage
- while conditions must be `i1`
- while-body lets and buffers are scoped to that loop iteration and do not escape
- nested while loops are supported
- if/otherwise conditions must be `i1`, and both branches must contain at least one step
- branch-local lets and buffers do not escape
- scalar bindings and assigned record fields in if branches lower to `scf.if` results in deterministic binding/field order
- arithmetic, bitwise, and shift operands must be matching integer numeric types, never `i1`
- source signedness controls `divided by`, `remainder`, ordered comparisons, `shifted right by`, widening casts, and dynamic index conversion
- comparisons require matching integer numeric operands and return `i1`
- there are no implicit casts between signed and unsigned types or between widths
- boolean `and`, `or`, and `not` require `i1` operands and return `i1`
- variables must be initialized by a phrase hole or prior visible `let`
- phrase calls must match a declared phrase template exactly
- conditional value blocks require `otherwise`
- removed ceremony words such as `Function`, `End function`, `Set`, `Return`, and `call ... with` are not valid Inscription syntax
- unsupported `track`, I/O, dynamic arrays, floats, pointers, heap allocation, source-level memrefs, record returns, record buffers, nested records, and free prose are rejected

## Tests

Run the full test suite:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v
```

The suite includes exact MLIR golden conformance files under [`tests/goldens`](tests/goldens). Each `*.ins` source must compile byte-for-byte to its sibling `*.mlir`.

With LLVM/MLIR 22 available, verify the toolchain and fixture exit codes:

```sh
PYTHONPATH=src python -m inscription check-tools --show-pipeline
PYTHONPATH=src python -m inscription run tests/fixtures/positive/adjust.ins                # exits 3
PYTHONPATH=src python -m inscription run tests/fixtures/positive/loop_sum.ins              # exits 55
PYTHONPATH=src python -m inscription run tests/fixtures/positive/iterative_factorial.ins   # exits 120
PYTHONPATH=src python -m inscription run tests/fixtures/positive/gcd.ins                   # exits 6
PYTHONPATH=src python -m inscription run tests/fixtures/positive/collatz_steps.ins         # exits 16
PYTHONPATH=src python -m inscription run tests/fixtures/positive/nested_while_multiply.ins # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/u8_cast.ins               # exits 255
PYTHONPATH=src python -m inscription run tests/fixtures/positive/bitwise_flags.ins         # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/shifts.ins                # exits 8
PYTHONPATH=src python -m inscription run tests/fixtures/positive/unsigned_remainder.ins    # exits 5
PYTHONPATH=src python -m inscription run tests/fixtures/positive/unsigned_comparison.ins   # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/buffer_sum.ins            # exits 100
PYTHONPATH=src python -m inscription run tests/fixtures/positive/filled_buffer.ins         # exits 15
PYTHONPATH=src python -m inscription run tests/fixtures/positive/swap_endpoints.ins        # exits 16
PYTHONPATH=src python -m inscription run tests/fixtures/positive/branch_store.ins          # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/loop_writes.ins           # exits 10
PYTHONPATH=src python -m inscription run tests/fixtures/positive/sum_buffer_parameter.ins  # exits 10
PYTHONPATH=src python -m inscription run tests/fixtures/positive/fill_buffer_procedure.ins # exits 28
PYTHONPATH=src python -m inscription run tests/fixtures/positive/copy_buffer_procedure.ins # exits 12
PYTHONPATH=src python -m inscription run tests/fixtures/positive/nested_procedure_calls.ins # exits 24
PYTHONPATH=src python -m inscription run tests/fixtures/positive/u8_buffer_parameter.ins   # exits 36
PYTHONPATH=src python -m inscription run tests/fixtures/positive/counted_loop_sum.ins      # exits 45
PYTHONPATH=src python -m inscription run tests/fixtures/positive/counted_loop_step.ins     # exits 20
PYTHONPATH=src python -m inscription run tests/fixtures/positive/buffer_length.ins         # exits 4
PYTHONPATH=src python -m inscription run tests/fixtures/positive/for_each_buffer_sum.ins   # exits 10
PYTHONPATH=src python -m inscription run tests/fixtures/positive/for_each_fill.ins         # exits 24
PYTHONPATH=src python -m inscription run tests/fixtures/positive/nested_for_multiply.ins   # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/for_with_branch.ins       # exits 5
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_field_access.ins    # exits 30
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_field_rebinding.ins # exits 10
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_loop_carry.ins      # exits 15
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_branch_carry.ins    # exits 7
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_copy_rebind.ins     # exits 53
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_unsigned_fields.ins # exits 42
PYTHONPATH=src python -m inscription run tests/fixtures/positive/record_buffer_interop.ins  # exits 9
```

## Repository layout

```text
src/inscription/              compiler implementation
docs/inscription-v0-spec.md   original v0 language and toolchain specification
docs/inscription-v0.1-spec.md v0.1 language and toolchain specification
docs/inscription-v0.2-spec.md v0.2 language and toolchain specification
docs/inscription-v0.3-spec.md v0.3 language and toolchain specification
docs/inscription-v0.4-spec.md v0.4 language and toolchain specification
docs/inscription-v0.5-spec.md v0.5 language and toolchain specification
docs/inscription-v0.6-spec.md v0.6 language and toolchain specification
docs/inscription-v0.7-spec.md current v0.7 language and toolchain specification
grammar/inscription-v0.ebnf   original v0 grammar
grammar/inscription-v0.1.ebnf v0.1 grammar
grammar/inscription-v0.2.ebnf v0.2 grammar
grammar/inscription-v0.3.ebnf v0.3 grammar
grammar/inscription-v0.4.ebnf v0.4 grammar
grammar/inscription-v0.5.ebnf v0.5 grammar
grammar/inscription-v0.6.ebnf v0.6 grammar
grammar/inscription-v0.7.ebnf current v0.7 grammar
tests/goldens/                exact MLIR conformance goldens
tests/                        unit tests and executable fixtures
```
