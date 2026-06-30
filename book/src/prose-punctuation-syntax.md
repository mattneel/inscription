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

Nested controllers are greedy: a nested `For`, `While`, or `Match` owns following semicolon clauses until the sentence ends. Use `then` to resume the parent clause list after one nested controller:

```inscription,check
To nested for then, giving i32.
Let total be 0.
Let rows be 0.
For i from 0 up to 3: For j from 0 up to 3: total becomes total plus 1; then rows becomes rows plus 1.
Give total plus rows.

To main, giving i32.
Give nested for then.
```

The canonical formatter stabilizes this layout. Prefer `inscription format` over hand-aligning source.
