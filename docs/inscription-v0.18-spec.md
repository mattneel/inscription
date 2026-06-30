# Inscription v0.18 tooling specification

Inscription v0.18 keeps the v0.17 source language unchanged and adds native executable emission to the CLI artifact pipeline. This is a tooling-only sprint: source parsing, typing, source MLIR generation, optimization presets, and the default `run` behavior through `lli` remain compatible with v0.17.

## Executable emission

The `compile` command accepts a new emit mode:

```text
inscription compile SOURCE --emit executable -o OUTPUT
```

`--emit executable` produces a native executable file and requires `-o OUTPUT`. It does not run the executable. The mode supports `--verify`, `--runtime-checks`, `--module-root DIR`, `--save-temps DIR`, `--opt-level none|basic|aggressive`, and `-O0`/`-O1`/`-O2`.

The executable pipeline reuses the existing stages:

```text
source MLIR -> optimized MLIR when requested -> lowered MLIR -> LLVM IR -> object -> executable
```

The object stage uses LLVM 22 `llc` and the link stage uses LLVM 22 `clang`:

```text
llc -relocation-model=pic -filetype=obj output.ll -o output.o
clang output.o -o executable
```

The compiler does not add target triples, clang optimization flags, linker flags, library paths, standard-library configuration, or direct `ld` invocation.

## Runnable main requirement

Executable emission requires the root program to define a no-hole `main` whose return type is an integer scalar. A missing no-hole `main` is a deterministic compile error. A `main` returning `i1` or a record is rejected with the same integer-scalar diagnostic used by executable eligibility checks.

Exported phrases do not replace `main`; `main` remains the process entry point when present.

## Toolchain discovery

Required tools for existing lowering and execution remain:

```text
mlir-opt
mlir-translate
lli
```

Object emission requires optional LLVM 22 `llc`. Executable emission requires both LLVM 22 `llc` and LLVM 22 `clang`.

`clang` discovery checks the configured LLVM toolchain root only. When `MLIR_TOOLCHAIN` is set, the compiler checks `$MLIR_TOOLCHAIN/clang` and `$MLIR_TOOLCHAIN/clang-22`. Otherwise it checks `/usr/lib/llvm-22/bin/clang` and `/usr/lib/llvm-22/bin/clang-22`.

`check-tools` reports optional `llc` and `clang` availability and supports:

```text
inscription check-tools --require-object
inscription check-tools --require-executable
```

`--require-executable` fails when either `llc` or `clang` is missing or not LLVM 22.x.

`check-tools --show-pipeline` reports optimization presets, the lowering pipeline, object emission, executable emission, and `lli` execution.

## Additional link objects

Executable emission supports repeated explicit object inputs:

```text
inscription compile main.ins --emit executable -o main --link-object host.o
```

Each `--link-object PATH` is passed to clang after the generated Inscription object. Inscription checks that each path exists, but does not inspect the object file. v0.18 deliberately does not add `--link-lib`, library search paths, arbitrary linker arguments, linker scripts, or target triples.

This small surface is intended for programs that call scalar-only extern phrases provided by separately built objects.

## Extern and exported phrase interaction

Programs with unresolved extern symbols may still compile to object files. Executable linking fails if clang cannot resolve those symbols, with the deterministic diagnostic prefix:

```text
executable link failed
```

Exported phrase symbols are emitted as normal global functions and can be present in the object/executable alongside `main`. Exported phrases do not change source call syntax and do not replace `main`.

## Saved intermediates

For `--emit executable --save-temps DIR`, the compiler saves:

```text
<stem>.mlir
<stem>.optimized.mlir   (only for --opt-level basic/aggressive)
<stem>.lowered.mlir
<stem>.ll
<stem>.o
```

The `-o OUTPUT` path remains the authoritative executable output. Saving a copy of the final executable under the temps directory is not required in v0.18.

## Run behavior

`inscription run SOURCE` continues to execute through LLVM 22 `lli` by default. v0.18 does not add a native run backend.

## Non-goals

Inscription v0.18 does not add source syntax changes, a standard library, package manifests, executable packaging beyond one output file, static libraries, shared libraries, C header generation, library search paths, linker flags, linker scripts, target triples, clang optimization flags, debug info, source maps, C ABI declarations, pointer types, references, strings, heap allocation, I/O syntax, macros, generics, custom MLIR dialects, a native runtime library, or cross-compilation.
