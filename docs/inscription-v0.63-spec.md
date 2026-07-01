# Inscription v0.63 diagnostic codes and `inscription explain`

Inscription v0.63 makes diagnostics stable and referenceable. It adds diagnostic codes to common compiler, ownership, interpreter/comptime, package, build-script, formatter, test, release, and toolchain failures, and adds the local `inscription explain` command for code lookup.

No source-language syntax changes are introduced in v0.63.

## Diagnostic codes

Coded diagnostics render as:

```text
error[INS-SEM-0001]: unknown binding missing
 --> src/App.ins:2:6
   |
 2 | Give missing.
   |      ^^^^^^^
```

Uncoded diagnostics still render as:

```text
error: message
```

Codes use the form `INS-CATEGORY-NNNN`. Current categories include `PARSE`, `SEM`, `OWN`, `PKG`, `BUILD`, `COMP`, `TOOL`, `FMT`, `TEST`, `REL`, and `INT`. Codes are stable identifiers and are not reused or casually renumbered.

## `inscription explain`

`inscription explain CODE` prints the local explanation for a diagnostic code:

```sh
PYTHONPATH=src python -m inscription explain INS-SEM-0001
```

`inscription explain --list` lists the local catalog in deterministic code order. `inscription explain --list --json` emits the same catalog as deterministic JSON for tools.

Unknown codes fail with a coded compiler-driver diagnostic:

```text
error[INS-COMP-0001]: unknown diagnostic code INS-NOPE-9999
```

## Coverage

v0.63 assigns codes to representative common diagnostics, including missing periods, unexpected tokens, unknown bindings/phrases, type mismatches, match exhaustiveness/pattern errors, ownership move errors, unsupported interpreter/comptime features, duplicate package declarations, dependency cycles, duplicate build steps, unknown Build API phrases, formatter check failures, test expectation failures, release output collisions, and required tool discovery/version errors.

Some older or filesystem-only diagnostics may remain uncoded in v0.63. Human-readable messages, source spans, source excerpts, and exit-code conventions remain deterministic.

## Non-goals

v0.63 does not add warnings, lints, fix-its, automatic fixes, LSP/editor integration, multi-error recovery, localization, telemetry, network lookups, online docs URLs, or colored output by default.
