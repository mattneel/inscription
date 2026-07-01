# Punctuation

Punctuation is syntax, not style. Periods end declarations and sentences. Colons introduce clause lists. Semicolons separate clauses. Commas separate header modifiers.

```inscription,check
To main, giving i32.
Let x be 0.
When true: x becomes 1; x becomes x plus 6.
Otherwise: x becomes 3.
Give x.
```

The formatter chooses a canonical spelling. It does not infer missing punctuation.

## Comments

Inscription comments are line comments. They are recognized outside byte and string literals and do not affect semantics or MLIR lowering.

```inscription,check
// This program exits 42.
To main, giving i32.
// Return the answer.
Give 42.
```

Use `///` for documentation attached to the next top-level declaration. Use `//!` for module or file documentation before the first declaration.

```inscription,format
//! Protocol helpers.

/// A byte alias used by protocol records.
Type Byte be u8.

/// Compute an exported answer.
To answer, giving i32, exported as ins_answer.
Give 42.
```

Documentation comments are preserved by the formatter, emitted in interface JSON, and emitted before generated C prototypes for exported phrases. Ordinary `//` comments are preserved by the formatter but are otherwise ignored. Block comments are not supported.
