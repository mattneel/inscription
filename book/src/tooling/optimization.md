# Optimization

Optimization presets run on source MLIR before lowering:

- `--opt-level none` or `-O0`: no optimization.
- `--opt-level basic` or `-O1`: canonicalize and CSE.
- `--opt-level aggressive` or `-O2`: deterministic scalar and control-flow cleanup passes.

Optimization affects lowered MLIR, LLVM IR, object files, executables, static libraries, and `run`. It does not change raw `--emit mlir`, interface JSON, or C headers.
