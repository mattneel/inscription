# Language Overview

Inscription is intentionally narrow. Programs contain top-level declarations, phrase definitions, and phrase-body sentences. Values are scalars, nominal records, enums, unions, and owned-buffer returns. Storage objects such as fixed buffers, arrays, views, and owned buffers have dedicated syntax and cannot be used as ordinary scalar values.

The language lowers to standard MLIR dialects and keeps source semantics deterministic. There are no macros, generics, implicit casts, exceptions, heap strings, pointers, or natural-language inference.
