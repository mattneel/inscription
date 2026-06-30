# Inscription v0.16 tooling specification

Inscription v0.16 keeps the v0.15 source language unchanged and adds deterministic CLI artifact emission plus saved compiler intermediates. This is a tooling-only sprint: source parsing, typing, source MLIR generation, and the LLVM/MLIR lowering pipeline remain compatible with v0.15.

## Compile artifact emission

The `compile` command accepts an optional `--emit` mode:

```text
inscription compile SOURCE --emit mlir
inscription compile SOURCE --emit lowered-mlir
inscription compile SOURCE --emit llvm-ir
inscription compile SOURCE --emit object -o OUTPUT
```

Supported modes are:

- `mlir`: emit the frontend source MLIR. This is the default and remains the exact-golden artifact.
- `lowered-mlir`: emit MLIR after the configured lowering pipeline.
- `llvm-ir`: emit LLVM IR produced by `mlir-translate --mlir-to-llvmir`.
- `object`: emit a native object file using LLVM 22 `llc`; this mode requires `-o OUTPUT`.

Textual artifacts (`mlir`, `lowered-mlir`, and `llvm-ir`) may be written to stdout when `-o` is omitted. Object emission is binary and never writes to stdout.

All emit modes support `--verify`, `--runtime-checks`, and `--module-root`.

## Saved intermediates

Both `compile` and `run` accept:

```text
--save-temps DIR
```

The directory is created if it does not exist. The compiler writes deterministic stage files using the root source basename:

```text
<stem>.mlir
<stem>.lowered.mlir
<stem>.ll
<stem>.o
```

Only stages that are produced by the command are saved. `run` saves source MLIR, lowered MLIR, and LLVM IR because it executes through `lli`. Object emission saves the `.o` file when `--save-temps` is used.

## Toolchain discovery

Required LLVM/MLIR 22 tools remain:

```text
mlir-opt
mlir-translate
lli
```

`llc` is optional and required only for `compile --emit object`. `check-tools` reports optional `llc` availability and supports:

```text
inscription check-tools --require-object
```

When `--require-object` is present, missing or non-LLVM-22 `llc` is a deterministic toolchain error.

## Verification semantics

`compile --verify` validates the relevant stages for the selected emit mode:

- `--emit mlir --verify`: verify source MLIR and that it lowers through the configured pipeline.
- `--emit lowered-mlir --verify`: verify source MLIR and lowered MLIR.
- `--emit llvm-ir --verify`: verify source/lowered MLIR before translation.
- `--emit object --verify`: verify source/lowered MLIR and LLVM IR generation before object emission.

The default `compile SOURCE` behavior is unchanged and emits source MLIR.

## Extern and exported phrases

Artifact emission supports extern and exported phrases from v0.14/v0.15. LLVM IR and object output may contain unresolved external symbols; resolving those symbols is a linker concern outside Inscription v0.16.

## Non-goals

Inscription v0.16 does not add new source syntax, linking, executable emission, static or shared libraries, header generation, package manifests, target triples, optimization levels, linker flags, C ABI metadata, object inspection, symbol export lists, debug info, source maps, custom MLIR dialects, a new runtime, standard library lookup, pointers, references, strings, heap allocation, I/O syntax, macros, or generics.
