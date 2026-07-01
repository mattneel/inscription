# Inscription v0.43 comments and documentation comments

Inscription v0.43 adds source comments and documentation comments without changing language semantics, MLIR lowering, or artifact kinds.

New behavior:

- `//` starts an ordinary line comment outside byte and string literals.
- `///` starts a documentation comment block attached to the next top-level declaration.
- `//!` starts a module/file documentation block before the first declaration.
- Documentation comments are emitted in interface JSON.
- Documentation comments on exported phrases are emitted as C comments before generated C prototypes.
- The canonical formatter preserves ordinary comments, documentation comments, and module docs deterministically.

No block comments, markdown parsing, comment directives, attributes, pragmas, conditional compilation, local-statement doc comments, or field/case/variant doc comments are added.

## Ordinary comments

`//` starts a comment outside literals and continues to the end of the line:

```inscription
// This program exits 42.
To main, giving i32.
// Return the answer.
Give 42.
```

Ordinary comments may appear between top-level declarations and between phrase body sentences. The formatter preserves standalone comments at column 0 and preserves trailing comments after complete sentences when possible. Ordinary comments are ignored by parsing semantics, type checking, MLIR lowering, interface JSON, and C header generation.

Comment delimiters inside literals are not comments:

```inscription
To main, giving i32.
Let bytes be array of bytes "http://example".
Give length of bytes.
```

Block comments are not supported:

```text
block comments are not supported; use //
```

## Declaration documentation comments

`///` starts a declaration documentation comment. Consecutive `///` lines form one documentation block. The block attaches to the next top-level declaration, and no blank line may appear between the block and its declaration.

```inscription
/// Adds two counts.
/// Returns the sum as i32.
To add counts left: i32 and right: i32, giving i32, exported as ins_add_counts.
Give left plus right.
```

Documentation text is normalized by stripping the leading `///`, stripping at most one following space, and joining consecutive lines with `\n`. Documentation comments are allowed before documentable top-level declarations such as modules, type aliases, constants, records, layout records, enums, unions, external phrases, and `To` phrases. They cannot attach to imports or phrase-body sentences.

Diagnostics include:

```text
documentation comment must be followed by a declaration
documentation comments cannot attach to imports
documentation comments are only supported before top-level declarations
```

## Module documentation comments

`//!` starts a module/file documentation comment. Consecutive `//!` lines form one module documentation block. Module docs must appear before the first top-level declaration:

```inscription
//! Protocol parsing helpers.

Module Protocol.
```

If a `Module` declaration exists, the docs attach to that module. Otherwise they attach to the root/unmoduled compilation unit. Module docs are emitted in interface JSON. They are not required to appear in C headers.

A `//!` comment after code is rejected:

```text
module documentation comments must appear before the first declaration
```

## Interface JSON

Interface JSON includes deterministic `documentation` fields for modules and emitted declaration metadata. Missing docs are represented as `null`; present docs are strings.

Example excerpt:

```json
{
  "name": "Mode",
  "kind": "enum",
  "documentation": "Packet mode."
}
```

Ordinary comments are not included. Documentation comments on imports are rejected, and declarations that are not emitted by the current interface JSON format are not added solely for documentation.

## C headers

Documentation comments on exported phrases are emitted before the generated prototype:

```c
/*
 * Adds two counts.
 * Returns the sum.
 */
int32_t ins_add_counts(int32_t arg0, int32_t arg1);
```

Only exported phrase docs are emitted in C headers. Ordinary comments and extern docs are not emitted. If documentation text contains `*/`, the header generator escapes it deterministically as `* /`.

## Formatter and highlighter

The formatter preserves comments and keeps documentation blocks attached to their declarations:

```inscription
//! Protocol helpers.

Module Protocol.

/// Packet mode.
Enum Mode backed by u8 has idle be 0; active be 1.
```

The highlighter recognizes `//`, `///`, and `//!` comments and does not treat `//` inside string literals as a comment.
