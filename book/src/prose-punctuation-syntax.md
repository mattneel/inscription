# Prose-Punctuation Syntax

Inscription source is sentence-oriented.

- A period `.` terminates a top-level declaration or phrase-body sentence.
- A colon `:` introduces a governed clause list.
- A semicolon `;` separates sibling clauses inside a clause list.
- A comma `,` separates header modifiers such as `giving` and `exported as`.
- Phrase bodies start after a `To ... .` declaration and continue until the next top-level declaration or EOF.
- Returning phrases use an explicit final `Give ... .` sentence.
- Indentation has no semantic meaning.
- Braces and `End` markers are not part of the language.

```inscription,check
To choose flag flag: i1, giving i32.
Let value be 0.
When flag, value becomes 7.
Otherwise, value becomes 3.
Give value.

To main, giving i32.
Give choose flag true.
```

Clause lists can hold loops and matches:

```inscription,check
Enum Mode backed by u8 has idle be 0; active be 1.

To count active modes: view of Mode, giving i32.
Let active be 0.
For each index i of modes:
Match modes at i:
Mode.active: active becomes active plus 1;
otherwise: active becomes active.
Give active.

To main, giving i32.
Let modes be array of 3 Mode containing Mode.idle, Mode.active, Mode.active.
Give count active modes.
```

The canonical formatter stabilizes this layout. Prefer `inscription format` over hand-aligning source.
