# Inscription v0.48 interpreter groundwork

Inscription v0.48 adds an internal deterministic interpreter for a pure, side-effect-free subset of checked Inscription programs. This is groundwork for future `build.ins`, `comptime`, compile-time generated data, and stronger static evaluation. v0.48 does **not** expose build scripts, package-time evaluation, user-facing runtime interpretation, or new source syntax.

## Scope

The interpreter lives in `src/inscription/interpreter.py` and is intentionally internal. Tests may import it directly, but the public CLI remains the compiler, runner, formatter, test runner, and package commands added in earlier sprints.

The interpreter evaluates checked ASTs in memory and executes pure returning phrases whose parameters, return type, body statements, and called phrases are all supported by v0.48.

## Value model

Interpreter values carry their Inscription type:

- `i1`
- signed integers: `i8`, `i16`, `i32`, `i64`
- unsigned integers: `u8`, `u16`, `u32`, `u64`
- `f32` and `f64`
- nominal enum values
- record values, including layout records as value records
- tagged union values with variant payloads

Integer arithmetic uses the same fixed-width normalization helpers as the constant evaluator. `f32` values are rounded through the existing f32 normalization path; `f64` uses Python floats consistently with the existing constant evaluator.

## Supported expressions

v0.48 supports the pure expression subset needed for scalar, enum, record, and union computation:

- integer, float, boolean, `zero`, byte literals, and `length of bytes "..."`
- variable references and top-level scalar/enum constants
- enum cases, record constructors, union constructors, and record field access
- arithmetic, integer remainder, bitwise operations, shifts, boolean `and`/`or`/`not`
- integer, float, and enum comparisons where the semantic checker permits them
- scalar and enum casts permitted by normal Inscription typing rules
- match expressions over integer, `i1`, enum, and union scrutinees, including guards, alternatives, ranges, `anything`, and ignored payload fields
- pure phrase calls returning supported values

Unsupported expressions fail with deterministic interpreter diagnostics such as:

```text
interpreter does not support arrays in v0.48
interpreter does not support extern phrase calls in v0.48
```

## Supported statements

A phrase body may use:

- `Let name be expression` and typed let bindings
- scalar, enum, record, and union rebinding
- record field assignment
- `When`/`Otherwise`
- counted `For` loops
- `While` loops
- step `Match`
- `Require` and `Check` as interpreted boolean assertions
- final `Give expression`

The interpreter uses a deterministic step/fuel limit, defaulting to 100000 steps. Exhaustion reports:

```text
interpreter step limit exceeded
```

## Pure phrase restrictions

A phrase is interpretable only when:

- all parameter and return types are supported value types
- every body statement and expression is in the supported pure subset
- every called phrase is also interpretable
- no extern, storage, owned-buffer, view, layout read/write, test-only `Expect`, or side-effecting does phrase is used

Storage and ownership features remain compiler/runtime features in v0.48; they are deliberately not interpreted.

## Non-goals

v0.48 does not add `build.ins`, `comptime`, interpreter-backed package loading, source-level I/O, strings, file system access, environment access, networking, process spawning, extern execution, owned-buffer interpretation, view/buffer mutation interpretation, heap allocation, a general VM, or a stable user-facing interpreter API.
