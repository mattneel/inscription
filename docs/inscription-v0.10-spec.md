# Inscription v0.10 specification

Inscription v0.10 keeps the v0.9 scalar, control-flow, buffer, record, layout-record, serialization, constant, and compile-time-check surface and adds modules plus imports.

## Execution model

A source file may optionally declare a module:

```text
module math
module geometry.points
```

A source file may import modules:

```text
import math
import geometry.points
```

A program is otherwise still a list of top-level constants, checks, record declarations, layout record declarations, packed layout record declarations, and phrase definitions. Existing single-file programs do not need a `module` declaration and emit the same MLIR as v0.9.

v0.10 does not add exports, wildcard imports, unqualified imported names, import aliasing, packages, macros, generics, dynamic linking, global storage, heap allocation, pointers, strings, floats, source-level `return`, `break`, `continue`, overloading, inference, implicit casts, or a custom dialect.

## Module declarations

A module declaration is written at top level:

```text
module module.name
```

Rules:

- Module names are lowercase identifier segments separated by dots.
- A file may declare at most one module.
- A file that is imported must declare exactly the module name used by the import.
- The root file being compiled may be unmoduled.
- A module declaration does not change single-file phrase syntax inside that file.

## Imports

Imports are top-level declarations:

```text
import module.name
```

Rules:

- Imports resolve relative to the root source directory.
- By default the root source directory is the directory containing the root source file.
- The CLI accepts `--module-root PATH` on `compile` and `run` to override the root source directory.
- Module `a.b` resolves to `ROOT/a/b.ins`.
- Import cycles are rejected deterministically.
- Importing the same module twice in one file is rejected.
- Imported declarations are qualified only. A phrase from `math` must be called as `math.phrase ...`, not `phrase ...`.
- Imports are not transitive. A file sees only modules it imports directly.

## Qualified phrase calls

Imported phrase calls prefix the phrase with the module name and a dot:

```text
import math

main gives i32:
  math.add 2 and 3
```

For an imported module:

```text
module math

add a: i32 and b: i32 gives i32:
  a plus b
```

The imported call is lowered to a stable module-qualified MLIR symbol:

```mlir
func.call @math__add(...)
```

Nested module names use the same rule:

```text
import geometry.points

main gives i32:
  geometry.points.sum point p
```

The corresponding MLIR symbol starts with `@geometry__points__`.

Inside a module, phrases declared in the same file may still call each other by their ordinary unqualified phrase spelling. Imported phrases used inside that module must be module-qualified.

## Imported constants

Imported constants may be used with a module-qualified name:

```text
import limits

main gives i32:
  limits.answer
```

Imported constants remain compile-time scalar values and lower as inline `arith.constant` operations at use sites. Unqualified uses of imported constants are rejected.

## Imported records and local module implementation details

Record and layout-record declarations inside imported modules are available to phrases in that module and are internally namespaced so they do not leak unqualified into the root file. v0.10 does not add source syntax for constructing imported record types directly from another module. Use imported phrases as the boundary.

## MLIR lowering

The emitter uses the same standard dialects as v0.9:

```text
builtin.module
func
arith
scf
memref
```

Imported module phrases are emitted before the root file's phrases in deterministic dependency order. Imported phrase symbols are prefixed by the module path with `.` replaced by `__`:

```text
math.add        -> @math__add
geometry.points.sum -> @geometry__points__sum
```

Root unmoduled programs emit byte-for-byte identical MLIR to v0.9.

## Golden conformance suite

The minimum v0.10 quality bar is the exact-output golden suite in `tests/goldens`. Each top-level `*.ins` source file compiles byte-for-byte to its sibling `*.mlir`; module dependencies used by goldens live below subdirectories and are resolved through the module loader.
