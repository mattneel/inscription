# Inscription v0.3 specification

Inscription v0.3 is a deterministic, phrase-shaped compiler. It keeps the v0.2 surface for phrase calls, value blocks, `let`/`becomes`, `while`, and step-level `if`/`otherwise`, and adds scalar systems operations: explicit integer widths, unsigned integer types, bitwise operators, shifts, and integer casts.

## Execution model

- A program is a list of phrase definitions.
- A phrase definition introduces a callable phrase template with zero or more typed holes.
- Source-visible scalar types are `i1`, `i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, and `u64`.
- `i1` is boolean only.
- Signed integer types are `i8`, `i16`, `i32`, and `i64`.
- Unsigned integer types are `u8`, `u16`, `u32`, and `u64`.
- All source integer types lower to MLIR signless integer types of the same width; source signedness is semantic and selects division, remainder, ordered comparison, cast extension, and right-shift operations.
- Each phrase body evaluates to a value; the final value block is the phrase result.
- Library compilation does not require `main`; if `main` exists, it must take no holes.
- v0.3 has no source I/O and no source-level storage.

## Lexical and layout rules

- Blank lines are ignored.
- Phrase, `while`, `if`, and `otherwise` block headers end with `:`.
- Body lines are bare lines without statement terminators.
- Indented lines after a control-flow header form that block's step block.
- Identifiers match `[a-z][a-z0-9_]*` and cannot be reserved words.
- Integer literals are base-10 decimal literals. There is no hex, binary, or octal syntax.
- Integer literals are typed by context when an expected integer type is known; otherwise untyped integer expressions default to `i32` as in earlier versions.
- `zero` is sugar for integer literal `0` and is valid in all integer contexts.
- Boolean literals are `true` and `false` and have type `i1`.
- `track` is not valid current syntax and is reserved so the compiler can reject old syntax clearly.

## Phrase definitions, body items, and value blocks

A phrase definition has a template and a body ending in a value block:

```text
max of a: i32 and b: i32 gives i32:
  a when a is greater than b
  otherwise b
```

A phrase body is:

```text
body_item*
value_block
```

Body items are evaluated sequentially and must appear before the value block:

```text
let name be expression
let name: type be expression
name becomes expression
while condition:
  step
if condition:
  step
otherwise:
  step
```

A value block supports:

```text
expression
expression when condition
otherwise expression
```

There is no statement-level `return`.

## Local bindings and rebinding

A local binding is introduced with `let`:

```text
let total be 0
let acc: i64 be 1
let byte: u8 be 255
let done be false
```

If the optional type annotation is present, the initializer must type-check exactly as that type. If no annotation is present, the initializer is typed by normal expression typing rules. The binding's type is fixed after initialization.

`becomes` rebinds any visible phrase hole or `let` binding:

```text
total becomes total plus i
n becomes n minus 1
done becomes n is equal to zero
```

Rebinding lowers to SSA values only. It emits the right-hand expression and updates the compiler's binding map; it emits no memory storage, load, or store.

## While loops and step-level if blocks

A while loop has an `i1` condition and an indented step block:

```text
while i is less than or equal to n:
  total becomes total plus i
  i becomes i plus 1
```

Nested `while` loops are supported. Let bindings declared inside a loop body are scoped to that iteration and do not escape. Bindings declared before a while and assigned anywhere inside it are carried by the lowered `scf.while`, ordered by source binding order.

A step-level if block requires `otherwise`:

```text
if condition:
  step
otherwise:
  step
```

The condition must be `i1`, and both branches must contain at least one step. Branch-local lets do not escape. Visible bindings assigned in either branch are yielded by the lowered `scf.if`; branches that do not assign a yielded binding yield the pre-if value.

## Integer literals and ranges

When an expected integer type is known, integer literals are checked against that type's range:

```text
let x: u8 be 255
let y: i16 be 32767
low byte of 511
```

Ranges:

- `i8`: -128 through 127
- `i16`: -32768 through 32767
- `i32`: -2147483648 through 2147483647
- `i64`: -9223372036854775808 through 9223372036854775807
- `u8`: 0 through 255
- `u16`: 0 through 65535
- `u32`: 0 through 4294967295
- `u64`: 0 through 18446744073709551615

No implicit casts are inserted for literals or other expressions.

## Expressions and precedence

Expressions are deterministic and statically typed:

- integer literal: `120`
- zero literal: `zero`
- boolean literal: `true`, `false`
- variable reference: `result`
- phrase call: `max of 7 and 3`
- postfix integer cast: `value as u32`
- unary boolean: `not value`
- unary bitwise: `bitwise not value`
- binary arithmetic: `plus`, `minus`, `times`, `divided by`, `remainder`
- shifts: `shifted left by`, `shifted right by`
- bitwise binary: `bitwise and`, `bitwise xor`, `bitwise or`
- binary boolean: `and`, `or`
- parenthesized expression: `(a plus b) times 2`
- comparison expression: `x is equal to 0`

Precedence, strongest to weakest:

1. parenthesized expressions
2. literals, names, and phrase calls
3. postfix `as type`
4. unary `not` and `bitwise not`
5. `times`, `divided by`, `remainder`
6. `plus`, `minus`
7. `shifted left by`, `shifted right by`
8. `bitwise and`
9. `bitwise xor`
10. `bitwise or`
11. comparisons
12. boolean `and`
13. boolean `or`

Binary operators are left-associative except that the shift amount is parsed as an additive expression, so `x shifted left by n plus 1` means `x shifted left by (n plus 1)`.

Boolean `and` and `or` are strict expression operators; v0.3 has no short-circuit semantics.

## Typing and lowering rules

### Arithmetic

`plus`, `minus`, `times`, `divided by`, and `remainder` require matching integer numeric types, never `i1`. Results have the same source type.

Lowering:

- `plus` -> `arith.addi`
- `minus` -> `arith.subi`
- `times` -> `arith.muli`
- signed `divided by` -> `arith.divsi`
- unsigned `divided by` -> `arith.divui`
- signed `remainder` -> `arith.remsi`
- unsigned `remainder` -> `arith.remui`

No runtime division-by-zero or remainder-by-zero checks are added.

### Comparisons

Comparisons require matching integer numeric operand types and return `i1`:

- equality lowers to `arith.cmpi eq` / `ne`
- signed ordering lowers to `slt`, `sle`, `sgt`, `sge`
- unsigned ordering lowers to `ult`, `ule`, `ugt`, `uge`

### Bitwise operators

`bitwise and`, `bitwise or`, `bitwise xor`, and `bitwise not` require integer numeric operands, never `i1`. Binary operands must have matching source types.

Lowering:

- `bitwise and` -> `arith.andi`
- `bitwise or` -> `arith.ori`
- `bitwise xor` -> `arith.xori`
- `bitwise not x` -> `arith.xori` with an all-ones constant of the same width

### Shifts

`value shifted left by amount` and `value shifted right by amount` require matching integer numeric source types for value and amount. Results have the value/source type.

Lowering:

- `shifted left by` -> `arith.shli`
- signed `shifted right by` -> `arith.shrsi`
- unsigned `shifted right by` -> `arith.shrui`

Oversize shift amounts are not masked or checked at runtime.

### Casts

Postfix casts are explicit:

```text
x as u8
x as i32
(pack high and low) as i32
```

The source and target must both be integer numeric types, not `i1`.

- Same-width casts emit no MLIR op and only change source semantic signedness.
- Narrowing casts lower to `arith.trunci`.
- Widening signed casts lower to `arith.extsi`.
- Widening unsigned casts lower to `arith.extui`.

There are no implicit casts between widths or signedness anywhere else.

## MLIR subset

The v0.3 emitter uses only:

```text
builtin.module
func.func
func.call
return
arith.constant
arith.addi
arith.subi
arith.muli
arith.divsi
arith.divui
arith.remsi
arith.remui
arith.andi
arith.ori
arith.xori
arith.shli
arith.shrsi
arith.shrui
arith.trunci
arith.extsi
arith.extui
arith.cmpi
scf.if
scf.while
scf.condition
scf.yield
```

No memory or storage lowering is permitted: no `memref`, `alloca`, globals, heap objects, stack slots, mutable storage dialects, or source-level state outside SSA values.

## Golden conformance suite

The minimum v0.3 quality bar is the exact-output golden suite in `tests/goldens`. Each `*.ins` source file must compile byte-for-byte to its sibling `*.mlir`; the unit test suite enforces this with unified diffs on mismatch.
