# Inscription v0.32 prose-punctuation syntax specification

Inscription v0.32 keeps the v0.31 language semantics, AST model, MLIR lowering, ownership rules, artifacts, interface JSON, and C headers, but replaces the old indentation-delimited source syntax with sentence-oriented punctuation syntax. Legacy forms such as `main gives i32:` and `record Point:` are no longer accepted.

## Sentence structure

- A period (`.`) terminates top-level declarations, phrase-body sentences, and colon-introduced clause lists.
- A colon (`:`) introduces a governed clause list.
- A semicolon (`;`) separates sibling clauses inside a colon-introduced list.
- A comma (`,`) separates phrase-header clauses such as `, giving i32`, `, exported as ins_name`, and external `, as symbol`.
- Newlines and indentation are formatting only. Braces and `End ...` markers are not part of v0.32.

## Top-level declarations

```inscription
Module Protocol.
Import Math.Bits as Bits.
Type Byte be u8.
Constant header_size: i32 be size of Header.
Check header_size is greater than 0.
Record Point has x: i32; y: i32.
Layout record Header has tag: u8; length: u16.
Packed layout record Word has value: u16.
Enum Mode backed by Byte has idle be 0; active be 1.
Union ParseResult has value value: Header; error code: Byte and offset: i32.
External population count of x: i32, giving i32, as llvm.ctpop.i32.
```

Module declarations, imports, type aliases, constants, checks, records, layout records, enums, unions, externs, and exports retain their v0.31 semantics after parsing.

## Phrase declarations and bodies

Returning phrases use `To ..., giving TYPE.` and must end with `Give expression.`. Does phrases use `To ... .` and do not produce a value. Exported phrases add `, exported as SYMBOL`. External phrases use `External ..., giving TYPE, as SYMBOL.` or `External ..., as SYMBOL.` and have no bodies.

```inscription
To add left: i32 and right: i32, giving i32, exported as ins_add.
Give left plus right.

To notify code: i32, exported as ins_notify.
Require code is greater than or equal to 0.
```

Phrase bodies are sentence sequences until the next top-level declaration or EOF. Body sentences include `Let`, `Require`, `Check`, `Write`, assignments, stores, phrase-call steps, `When`/`Otherwise`, `While`, `For`, `For each`, and `Match`.

## Control flow

```inscription
When flag: x becomes 1; y becomes 2.
Otherwise: x becomes 3; y becomes 4.

While current is greater than 1: acc becomes acc times current; current becomes current minus 1.

For i from 0 up to n: total becomes total plus i.
For each index i of cells: total becomes total plus cells at i.
```

`Otherwise` is required immediately after `When`. Existing branch, loop-carried SSA, scoping, owned-buffer cleanup, and runtime-check semantics are unchanged.

## Match syntax

Match expressions are lowercase expression forms and use `Pattern gives expression` arms:

```inscription
Give match mode:
Mode.idle gives 0;
Mode.active gives 7;
otherwise gives 1.
```

Match step blocks are body sentences and use capitalized `Match` plus `Pattern: steps` arms:

```inscription
Match token:
Token.integer with value: total becomes total plus (value as i32);
Token.operator with symbol as op and precedence as prec: total becomes total plus (op as i32) plus (prec as i32);
otherwise: total becomes total.
```

All v0.31 match typing, payload binding, ownership restrictions, and lowering rules remain unchanged.

## Compatibility and non-goals

v0.32 does not add new type features, ownership features, MLIR dialects, formatter behavior, braces, optional periods, semicolon-free clause lists, early return, generics, macros, strings beyond existing byte literals, or legacy syntax compatibility.
