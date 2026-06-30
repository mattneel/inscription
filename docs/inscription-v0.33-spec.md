# Inscription v0.33 canonical formatter and syntax stabilization specification

Inscription v0.33 keeps the v0.32 prose-punctuation language semantics, AST model, MLIR lowering, ownership rules, artifacts, interface JSON, and C headers. It adds a deterministic source formatter and stabilizes the canonical style for punctuation syntax.

No legacy indentation/block syntax is reintroduced. Forms such as `main gives i32:` and `record Point:` remain invalid.

## Formatter CLI

```sh
inscription format SOURCE
inscription format SOURCE -o OUTPUT
inscription format SOURCE --check
inscription format SOURCE --in-place
```

Rules:

- `format SOURCE` writes formatted source to stdout.
- `format SOURCE -o OUTPUT` writes formatted source to `OUTPUT`.
- `format SOURCE --in-place` overwrites `SOURCE` with formatted source.
- `format SOURCE --check` exits 0 when `SOURCE` is already formatted.
- `format SOURCE --check` exits 2 and reports `formatting check failed: SOURCE is not formatted` when formatting would change the file.
- `--check` never modifies files.
- `--in-place` and `-o` are mutually exclusive.
- `--check` and `--in-place` are mutually exclusive.
- `--check` and `-o` are mutually exclusive.
- Formatting errors use the existing compiler diagnostic style and exit code 2.
- Formatting does not require LLVM/MLIR tools.
- Formatting is syntax-preserving. It does not reorder declarations, sort imports, simplify expressions, change semantics, run MLIR lowering, or consult LLVM tools.

## Canonical layout

Top-level declarations are emitted as paragraphs separated by one blank line. Consecutive imports stay in a compact import group, with one blank line after the group before the next non-import declaration.

```inscription
Module Protocol.

Import Math.
Import Math.Bits as Bits.

Type Byte be u8.

Enum Mode backed by Byte has idle be 0; active be 1; failed be 2.
```

There are no leading blank lines, no trailing whitespace, and exactly one trailing newline at EOF.

## Phrase layout

Phrase headers are emitted at column 0:

```inscription
To sum cells cells: view of i32, giving i32.
Let total be 0.
For each index i of cells: total becomes total plus cells at i.
Give total.

To notify code: i32, exported as ins_notify.
Require code is greater than or equal to 0.
```

There is no blank line between a phrase header and its body. Separate phrases are separated by one blank line. Returning phrases still end with an explicit `Give ... .` sentence; does phrases still have no `Give` value.

## Canonical sentences and clause lists

Simple sentences are emitted on one line:

```inscription
Let total be 0.
total becomes total plus 1.
Require total is greater than or equal to 0.
Write header into bytes at 0.
Give total.
```

Records, layout records, enums, and unions are emitted as single-line declarations in v0.33:

```inscription
Record Point has x: i32; y: i32.
Packed layout record Word has value: u16.
Enum Mode backed by u8 has idle be 0; active be 1.
Union Token has eof; integer value: i64; operator symbol: u8 and precedence: u8.
```

Line wrapping is not configurable in v0.33.

## Match formatting

Match expressions are emitted as multiline clause lists with lowercase `match`:

```inscription
Give match mode:
Mode.idle gives 0;
Mode.active gives 7;
otherwise gives 1.
```

Match step blocks are emitted as multiline clause lists with capitalized `Match`:

```inscription
Match token:
Token.integer with value: total becomes total plus (value as i32);
Token.operator with symbol as op and precedence as prec: total becomes total plus (op as i32) plus (prec as i32);
otherwise: total becomes total.
```

Nested match step blocks inside loop/control clause lists remain punctuation-delimited and are rendered deterministically.

## Syntax tolerance

The formatter accepts valid v0.32/v0.33 punctuation source with extra blank lines, extra spaces, and line breaks around semicolon-separated arms. It rejects missing periods, semicolons outside clause lists, `Otherwise` without a corresponding `When`, legacy indentation syntax, and other syntactically invalid source.

Comments are not part of the Inscription source language in v0.33, so the formatter does not define comment preservation behavior.

## Internal migration helper

`tests/v032_migrate.py` remains as an internal test helper for historical v0.31-and-earlier snippets embedded in the unit suite. It is not a user-facing formatter or compatibility layer. The `inscription format` command is the supported canonical source-formatting tool.

## Non-goals

v0.33 does not add formatter configuration, line width settings, import sorting, declaration sorting, semantic rewrites, legacy syntax migration, automatic punctuation insertion, optional periods, braces, indentation semantics, comments, new language features, MLIR changes, or custom dialects.
