# Inscription v0.34 explicit `then` continuation clauses

Inscription v0.34 keeps the v0.33 language semantics, AST model, MLIR lowering, ownership rules, formatter, artifacts, interface JSON, and C headers. It adds one punctuation-syntax marker, `then`, for parent-continuation inside nested control-flow clause lists.

No braces, indentation semantics, `end`, `do`, `begin`, new ownership behavior, or new lowering behavior are added.

## Problem

In punctuation clause lists, nested controllers are greedy by default. A nested `While`, `For`, `For each`, or `Match` clause owns following semicolon clauses until the enclosing sentence ends.

```inscription
For i from 0 up to 3: For j from 0 up to 3: total becomes total plus 1; counter becomes counter plus 1.
```

Both body clauses belong to the inner `For j` loop. This behavior remains valid and deterministic.

## `then` parent continuation

Use `; then` to close one nested controller and resume the parent clause list.

```inscription
For i from 0 up to 3: For j from 0 up to 3: total becomes total plus 1; then counter becomes counter plus 1.
```

This is equivalent to:

```text
for i:
  for j:
    total += 1
  counter += 1
```

Rules:

- `then` appears after a semicolon in a colon-introduced clause list.
- `then` is a structural marker, not a statement keyword and not an expression.
- `then` pops exactly one nested `While`, `For`, or `Match` controller level.
- `then` is valid only after a nested controller inside a clause list.
- `then` cannot begin a top-level sentence.
- `then` cannot appear after a simple non-control clause.

Invalid uses produce a deterministic diagnostic:

```inscription
To main, giving i32.
then Give 0.
```

```text
then may only resume a parent clause after nested control
```

```inscription
To main, giving i32.
Let x be 1; then x becomes 2.
Give x.
```

```text
then may only resume a parent clause after nested control
```

## Branch example

```inscription
To branch fill then flag: i1, giving i32.
Let result be 0.
Let cells be buffer of 4 i32 filled with 0.
When flag: For each index i of cells: cells at i becomes i plus 1; then result becomes cells at 0 plus cells at 1 plus cells at 2 plus cells at 3.
Otherwise: result becomes 1.
Give result.
```

The fill loop runs inside the `When` branch. The `result becomes ...` clause resumes the `When` branch after the loop, rather than becoming part of the loop body.

## Match example

```inscription
Enum Mode backed by u8 has idle be 0; active be 1.

To match then mode: Mode, giving i32.
Let result be 0.
Let seen be 0.
When true: Match mode: Mode.active: result becomes 7; otherwise: result becomes 3; then seen becomes seen plus 1.
Otherwise: result becomes 0.
Give result plus seen.
```

The `seen` update executes after the selected `Match` arm but still inside the `When` branch.

## Formatter and highlighting

`inscription format` preserves `then` and emits it where required to express a parent continuation. The canonical style remains punctuation-only: no indentation semantics, braces, or closing keywords. The highlighter recognizes lowercase `then` as a syntax keyword.

## Non-goals

v0.34 does not add braces, indentation semantics, end markers, new control-flow semantics, ownership features, MLIR lowering changes, artifact changes, or legacy syntax compatibility.
