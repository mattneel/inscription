# Inscription v0.20 tooling specification

Inscription v0.20 keeps the v0.19 source language unchanged and adds deterministic static-library emission plus C header/archive integration validation.

```text
inscription compile SOURCE --emit static-library -o OUTPUT
```

This is a tooling-only sprint. Source parsing, type checking, source MLIR generation, lowering, optimization presets, object emission, executable emission, interface JSON, C header generation, and `run` remain compatible with v0.19.

## Static-library emission

`compile --emit static-library -o OUTPUT` produces a native static archive, typically named with a `.a` suffix.

Rules:

- `-o OUTPUT` is required; archive bytes are never written to stdout.
- A root `main` phrase is not required.
- The mode supports `--verify`, `--runtime-checks`, `--module-root DIR`, `--save-temps DIR`, `--opt-level none|basic|aggressive`, and `-O0`/`-O1`/`-O2`.
- The mode reuses the existing artifact pipeline:
  - frontend source MLIR
  - optimized source MLIR when the selected optimization level is not `none`
  - lowered MLIR
  - LLVM IR
  - object file through LLVM 22 `llc`
  - static archive through LLVM 22 `llvm-ar`
- Static-library emission does not invoke `clang`.
- Static-library emission does not link and does not resolve extern symbols.
- Sources containing only exported phrases are valid library inputs.
- Sources containing a normal `main` are also accepted; the resulting archive is still just an archive artifact and is not executed.
- Exported symbols are emitted into the generated object/archive according to the existing v0.15 export rules.
- When the compilation contains exported phrases, the root executable `main` entry point is omitted from the archive object so generated C callers can provide their own `main`.
- Non-exported helper symbols may also be present. v0.20 does not add general symbol stripping, symbol DCE, or archive member partitioning.

The archive command is deterministic:

```sh
llvm-ar rcsD OUTPUT generated.o [archive-object ...]
```

Inscription does not use system `ar`, does not invoke `ranlib` separately, and does not add target triples, linker flags, library search paths, package manifests, or install steps.

## Archive object inputs

`--archive-object PATH` may be repeated with `--emit static-library`.

Rules:

- The option is valid only with `--emit static-library`.
- Each path must exist before archive construction.
- Paths are added to the archive after the generated Inscription object.
- Paths are not inspected beyond existence.
- No arbitrary `ar` flags are exposed.
- `--archive-object` is separate from executable-only `--link-object`.

Diagnostics:

```text
static library emission requires -o OUTPUT
--archive-object is only valid with --emit static-library
archive object host.o does not exist
```

## Tool discovery

LLVM/MLIR tool discovery remains strict. Required baseline tools are still `mlir-opt`, `mlir-translate`, and `lli` from LLVM/MLIR 22.

Static-library emission additionally requires:

- LLVM 22 `llc`
- LLVM 22 `llvm-ar`

`llvm-ar` is discovered from `MLIR_TOOLCHAIN` when set, otherwise `/usr/lib/llvm-22/bin`, matching the existing LLVM tool policy.

Plain `check-tools` reports optional static-library support but does not fail when `llvm-ar` is unavailable. `check-tools --require-static-library` requires both `llc` and `llvm-ar`.

Suggested deterministic diagnostics:

```text
static library emission requires llc from LLVM 22, but llc was not found
static library emission requires llvm-ar from LLVM 22, but llvm-ar was not found
static library emission requires llvm-ar from LLVM 22, got LLVM 21.x
```

`check-tools --show-pipeline` reports the archive stage:

```text
static library emission: llvm-ar rcsD output.a output.o
```

## Saved intermediates

With `--save-temps DIR`, static-library emission writes the same deterministic compiler intermediates as object/executable emission:

```text
<stem>.mlir
<stem>.optimized.mlir   # only when optimization level is not none
<stem>.lowered.mlir
<stem>.ll
<stem>.o
```

The `-o OUTPUT` archive remains the authoritative final archive path. v0.20 does not require copying the final archive into the temps directory.

## C header and archive smoke integration

v0.20 validates that v0.19 C headers can pair with v0.20 archives for exported scalar phrases.

A library-style source may be compiled twice:

```sh
inscription compile library.ins --emit c-header -o inscription_export.h
inscription compile library.ins --emit static-library -o libinscription.a
```

A C caller can then include the generated header and link against the archive with LLVM 22 `clang`:

```c
#include "inscription_export.h"

int main(void) {
  return ins_add(40, 2);
}
```

The integration test is intentionally narrow:

- It covers exported scalar phrases supported by v0.19 C headers.
- It may cover exports from imported modules.
- It may cover `--archive-object` by adding a host object that defines an extern symbol required by an exported Inscription phrase.
- It does not add source strings, C ABI structs, pointer parameters, callbacks, dynamic libraries, package manifests, or generated build-system files.

## Non-goals

v0.20 does not add:

- source syntax changes
- dynamic/shared library emission
- package manifests
- header installation
- standard library lookup
- C ABI structs or layout-record C structs
- buffer/view C ABI
- pointer parameters
- string literals
- callbacks or varargs
- arbitrary linker flags
- library search paths
- target triples
- debug info or optimization remarks
- cross compilation
- custom runtime support
- custom MLIR dialects
