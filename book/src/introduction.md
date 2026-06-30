# Introduction

Inscription is a small compiler and language for deterministic, phrase-shaped programs. A program reads like constrained prose, but it is not natural-language interpretation. Every accepted sentence matches the grammar exactly, and the compiler produces deterministic MLIR.

Inscription phrases are callable units. A returning phrase names typed holes, declares a return type with `giving`, and ends with `Give`:

```inscription,check
To square of x: i32, giving i32.
Give x times x.

To main, giving i32.
Give square of 8.
```

Since v0.32, Inscription uses prose-punctuation syntax. Periods close declarations and body sentences. Colons introduce clause lists. Semicolons separate sibling clauses. Indentation is only formatting and has no semantic meaning.

The compiler pipeline is deliberately conventional:

1. Parse punctuation syntax into the existing Inscription AST.
2. Type-check and lower source constructs to frontend MLIR using standard dialects such as `func`, `arith`, `scf`, `memref`, and `cf`.
3. Optionally optimize source MLIR with deterministic presets.
4. Lower through LLVM 22 tools to LLVM IR, objects, executables, or static archives.

Inscription is not prompt-to-code. It is not a natural-language runtime. It is not indentation-based after v0.32. It has no hidden inference layer: source text either matches the grammar and type rules or receives a deterministic diagnostic.
