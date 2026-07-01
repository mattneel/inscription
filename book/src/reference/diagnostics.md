# Diagnostics

Inscription diagnostics are deterministic and intentionally direct. They report parser errors, type errors, unsupported ABI usage, storage misuse, ownership misuse, test failures, package/build-script issues, release packaging failures, and toolchain failures.

## Diagnostic codes

v0.63 adds stable diagnostic codes. Coded diagnostics render the code in the header:

```text
error[INS-SEM-0001]: unknown binding missing
 --> src/App.ins:2:6
   |
 2 | Give missing.
   |      ^^^^^^^
```

Use `inscription explain CODE` to read the local explanation for a code, and `inscription explain --list` to list the local catalog:

```sh
PYTHONPATH=src python -m inscription explain INS-SEM-0001
PYTHONPATH=src python -m inscription explain --list
PYTHONPATH=src python -m inscription explain --list --json
```

Codes are stable identifiers. New diagnostics may gain codes over time, but existing codes are not reused or casually renumbered. Some older or filesystem-only diagnostics may still be uncoded.

Code categories:

- `PARSE`: syntax/parser errors
- `SEM`: semantic and type-checking errors
- `OWN`: ownership and move-checking errors
- `PKG`: package manifest and package graph errors
- `BUILD`: `build.ins` and build-command errors
- `COMP`: compiler driver diagnostics
- `TOOL`: external toolchain discovery/version errors
- `FMT`: formatter diagnostics
- `TEST`: source-level test runner diagnostics
- `REL`: release bundle/archive/checksum diagnostics
- `INT`: interpreter and `comptime` diagnostics

## Source excerpts

v0.62 introduced file/line/column spans and caret excerpts when source text is available. Parser, semantic, package manifest, `build.ins`, formatter, and common test diagnostics use the shared renderer.

```text
error[INS-PARSE-0001]: missing period at end of sentence
 --> src/App.ins:2:8
   |
 2 | Give 42
   |        ^
```

Diagnostics remain deterministic and color-free by default. Filesystem and external toolchain failures may stay locationless when they are not tied to an Inscription source span.

## Current diagnostic code catalog

| Code | Title | Category | Summary |
| ---- | ----- | -------- | ------- |
| `INS-BUILD-0001` | Duplicate build step | BUILD | A build.ins script declares the same build step name more than once. |
| `INS-BUILD-0002` | Unknown Build API phrase | BUILD | A build.ins script calls a Build phrase that v0.63 does not define. |
| `INS-BUILD-0003` | Build step dependency cycle | BUILD | Build step groups form a dependency cycle. |
| `INS-BUILD-0004` | Invalid build script | BUILD | A build.ins script violates the restricted v0.63 build-script shape. |
| `INS-BUILD-0005` | Build tool missing | BUILD | A build step requires an external documentation or artifact tool that was not found. |
| `INS-COMP-0001` | Unknown diagnostic code | COMP | The requested diagnostic code is not in the local Inscription catalog. |
| `INS-FMT-0001` | Formatting check failed | FMT | A source, package manifest, or build script is not in canonical formatter output. |
| `INS-INT-0001` | Comptime evaluation failed | INT | A comptime expression could not be evaluated by the pure interpreter. |
| `INS-INT-0002` | Interpreter step limit exceeded | INT | Pure interpretation exceeded the deterministic step limit. |
| `INS-INT-0003` | Unsupported interpreter feature | INT | The v0.63 pure interpreter encountered a feature it intentionally does not execute. |
| `INS-OWN-0001` | Owned buffer was moved | OWN | An owned buffer is used after its ownership has been moved. |
| `INS-OWN-0002` | Partial move across control flow | OWN | Control-flow paths leave ownership in incompatible states. |
| `INS-OWN-0003` | Invalid move target | OWN | A move expression targets something that cannot transfer ownership. |
| `INS-OWN-0004` | Cannot copy or rebind owned buffer | OWN | An owned buffer operation would duplicate or overwrite ownership unsafely. |
| `INS-PARSE-0001` | Expected period | PARSE | A punctuation sentence is missing its terminating period. |
| `INS-PARSE-0002` | Unexpected token | PARSE | The parser found syntax that does not match the expected grammar form. |
| `INS-PARSE-0003` | Unterminated string literal | PARSE | A string or byte string literal ends before its closing quote. |
| `INS-PARSE-0004` | Invalid escape sequence | PARSE | A string or byte literal contains an unsupported escape sequence. |
| `INS-PARSE-0005` | Legacy syntax not supported | PARSE | The parser found old pre-punctuation syntax. |
| `INS-PKG-0001` | Invalid package manifest | PKG | package.ins is missing required declarations or contains an unsupported manifest sentence. |
| `INS-PKG-0002` | Duplicate package declaration | PKG | package.ins declares a singleton field more than once. |
| `INS-PKG-0003` | Package path invalid | PKG | A package source/test/dependency path violates manifest path rules. |
| `INS-PKG-0004` | Package dependency cycle | PKG | Local path package dependencies form a cycle. |
| `INS-PKG-0005` | Package module not exposed | PKG | A package imports a dependency module that the dependency does not expose. |
| `INS-REL-0001` | Release output exists | REL | A release output directory already exists and is nonempty. |
| `INS-REL-0002` | Release archive failed | REL | A deterministic release archive could not be created. |
| `INS-REL-0003` | Checksum failed | REL | A release checksum manifest or archive checksum could not be written. |
| `INS-SEM-0001` | Unknown binding | SEM | The compiler could not find a binding with the requested name in the current scope. |
| `INS-SEM-0002` | Unknown phrase | SEM | A phrase call does not match any phrase visible in the current compilation. |
| `INS-SEM-0003` | Type mismatch | SEM | An expression has a different type than the surrounding context requires. |
| `INS-SEM-0004` | Invalid return value | SEM | A phrase returns no value or a value incompatible with its declared return type. |
| `INS-SEM-0005` | Match is not exhaustive | SEM | A match expression or step does not cover every possible input value. |
| `INS-SEM-0006` | Duplicate or unreachable match pattern | SEM | A match arm can never be selected because an earlier arm already covers it. |
| `INS-SEM-0007` | Unsupported type in this context | SEM | A type appears in a language position that v0.63 does not support. |
| `INS-TEST-0001` | Expect failed | TEST | A source-level test expectation evaluated to false at runtime. |
| `INS-TOOL-0001` | Required tool not found | TOOL | A required external LLVM/MLIR or documentation tool was not found. |
| `INS-TOOL-0002` | Tool version mismatch | TOOL | An external tool exists but does not report the required version. |

Negative tests in `tests/test_inscription.py` remain the executable catalog of exact diagnostic wording.
