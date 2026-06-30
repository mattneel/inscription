# Inscription v0.17 tooling specification

Inscription v0.17 keeps the v0.16 source language unchanged and adds deterministic optimization presets to the CLI artifact pipeline. This is a tooling-only sprint: source parsing, typing, source MLIR generation, and the default lowering/execution behavior remain compatible with v0.16.

## Optimization levels

The `compile` and `run` commands accept:

```text
--opt-level none
--opt-level basic
--opt-level aggressive
-O0
-O1
-O2
```

Aliases map as follows:

- `-O0`: `--opt-level none`
- `-O1`: `--opt-level basic`
- `-O2`: `--opt-level aggressive`

The default is `none`. Existing commands without optimization flags behave as in v0.16. Supplying conflicting levels, such as `--opt-level basic -O2` or `-O1 -O2`, is a deterministic error.

## Preset definitions

Optimization presets run with LLVM/MLIR 22 `mlir-opt` on the frontend/source MLIR before the existing lowering pipeline.

```text
none:       <none>
basic:      canonicalize, cse
aggressive: canonicalize, cse, sccp, canonicalize, cse,
            control-flow-sink, loop-invariant-code-motion,
            canonicalize, cse
```

The presets are version-controlled and deterministic. v0.17 does not accept arbitrary user-supplied pass pipelines. The presets intentionally do not include `symbol-dce`, `inline`, LLVM `opt`, LTO, linker flags, target triples, or optimization remarks.

## Artifact behavior

`compile --emit mlir` always emits raw frontend/source MLIR, even when an optimization level is supplied. This preserves source MLIR exact-golden semantics.

Optimization affects downstream artifacts only:

- `--emit lowered-mlir`: lowers raw source MLIR for `none`; lowers optimized source MLIR for `basic` or `aggressive`.
- `--emit llvm-ir`: translates lowered MLIR from the selected pipeline.
- `--emit object`: emits object code from LLVM IR from the selected pipeline.
- `run`: executes LLVM IR from the selected pipeline through `lli`.

All optimization levels work with `--verify`, `--runtime-checks`, `--module-root`, and `--save-temps`.

## Saved intermediates

For `--opt-level none`, v0.16 saved temp filenames are unchanged:

```text
<stem>.mlir
<stem>.lowered.mlir
<stem>.ll
<stem>.o
```

For `--opt-level basic` or `--opt-level aggressive`, saved temps include the optimized source MLIR stage:

```text
<stem>.mlir
<stem>.optimized.mlir
<stem>.lowered.mlir
<stem>.ll
<stem>.o
```

`<stem>.mlir` is always raw frontend/source MLIR. `<stem>.optimized.mlir` is the source MLIR after the selected optimization preset and is not written for `none`.

## Verification and diagnostics

`--verify` verifies the raw source MLIR. When optimization is enabled, it also verifies the optimized source MLIR before lowering. Lowered MLIR verification, LLVM IR translation, and object emission retain the v0.16 semantics for the selected emit mode.

Tool failures report the failed stage deterministically, including:

- `source MLIR optimization failed during basic preset`
- `source MLIR optimization failed during aggressive preset`
- `MLIR lowering failed`
- `MLIR translation failed`
- `object emission failed`

`check-tools --show-pipeline` reports both the lowering pipeline and the optimization preset pass sequences.

## Non-goals

Inscription v0.17 does not add source syntax changes, arbitrary pass pipeline strings, user-defined optimization passes, LLVM `opt`, LTO, linker integration, executable emission, target triples, optimization remarks, debug info, profile-guided optimization, symbol stripping, inlining, symbol DCE by default, standard library lookup, macros, generics, custom MLIR dialects, pointers, references, strings, heap allocation, or I/O syntax.
