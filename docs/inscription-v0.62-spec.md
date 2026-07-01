# Inscription v0.62 diagnostic spans and source excerpts

Inscription v0.62 centralizes diagnostic rendering and adds source spans with readable excerpts for parser, semantic, package, build-script, and formatter errors when source text is available. It does not add source language syntax, warnings, colors, LSP support, multi-error recovery, automatic fixes, or JSON diagnostics.

## Diagnostic shape

Diagnostics have a deterministic message, severity, optional code, optional notes, and an optional source span. Spans use 1-based line and column coordinates. Columns are deterministic source-text positions; no terminal-width wrapping or color output is applied.

Text diagnostics render as:

```text
error: unknown binding missing
 --> src/App.ins:2:6
   |
 2 | Give missing.
   |      ^^^^^^^
```

When a diagnostic has no source location or source text cannot be loaded, the renderer preserves the previous compact form:

```text
error: package manifest not found at package.ins
```

## Covered surfaces

The compiler now attaches source context for common parser and semantic failures during `compile`, `run`, `test`, interface/header emission, package module validation, and package artifact builds. Package manifest and `build.ins` parsing attach spans for malformed declarations, duplicates, unknown Build API phrases, and group/default errors. Formatting parse errors use the same renderer. Filesystem and external toolchain diagnostics remain spanless when no source location exists.

## Stability

Successful command output remains stable. Existing exit-code conventions remain unchanged: compiler, package, build-script, formatter, filesystem, and tool diagnostics exit 2, while source-level test failures continue to use the test runner exit conventions. Diagnostic text remains deterministic and color-free by default.

## Non-goals

The v0.62 diagnostic work does not add warnings, suggestions, fixes, localization, color themes, terminal-width-dependent wrapping, LSP/editor integration, automatic code actions, or multi-error recovery.
