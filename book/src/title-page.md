# The Inscription Book

Inscription is a deterministic, phrase-shaped systems language that lowers to MLIR and LLVM. This book is the primary human-facing guide for learning and using the language.

The current language surface is prose-punctuation syntax: declarations and steps are sentences, phrase bodies end with explicit `Give` sentences, and punctuation rather than indentation defines structure. Nested control can resume parent clause lists with `then`.

```inscription,check
To main, giving i32.
Give 7.
```

Use this book when you want a narrative path. Use the historical version specs in `docs/` when you need the exact contract for a particular sprint version.
