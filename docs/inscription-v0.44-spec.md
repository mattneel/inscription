# Inscription v0.44 first-class tests and test runner

Inscription v0.44 adds source-level test declarations and the `inscription test` command. Tests use the same parser, type checker, ownership checks, MLIR lowering, LLVM lowering, and runtime assertion machinery as ordinary Inscription code, but they are not normal phrases and are ignored by `run`, C headers, and interface JSON.

No runtime library, source I/O, string values, package-manifest discovery, source-level assertion messages, mocking, expected failures, fuzzing, or parallel test execution are added.

## Test declarations

A test is a top-level declaration:

```inscription
Test addition works.
Expect add 20 and 22 is equal to 42.
```

Rules:

- `Test ... .` starts a test body.
- The test body continues until the next top-level declaration or EOF.
- Test names are phrase-shaped words and must be unique within a module.
- A test has no parameters and no return type.
- Tests have their own lexical scope.
- Test bodies may use ordinary step sentences such as `Let`, assignment, stores, `Require`, `Check`, `When`/`Otherwise`, loops, match step blocks, does phrase calls, storage declarations, owned buffers, and moves.
- Test bodies may use `Expect condition.`.
- A test must contain at least one `Expect`.
- `Give` is not valid inside a test.
- Tests are not phrases and cannot be called from Inscription code.
- Tests are not exported, are not emitted in C headers, and are not included in interface JSON in v0.44.

Documentation comments may attach to tests and are preserved by the formatter, but v0.44 does not expose test metadata in generated interface JSON.

## Expect sentences

`Expect` is a test-only runtime assertion:

```inscription
Expect total is equal to 10.
```

Rules:

- `Expect` is valid only inside test declarations.
- The condition must type-check as `i1`.
- The condition may depend on runtime values.
- Unlike `Check`, an `Expect` condition does not need to be compile-time evaluable.
- Unlike `Require`, `Expect` is for tests rather than program contracts.
- A false expectation fails the currently running test.
- `Expect` is not an expression and cannot appear at top level or in ordinary `To` phrase bodies.

The current lowering emits a deterministic runtime assertion message:

```text
expect failed
```

The test runner reports deterministic pass/fail summaries rather than relying on LLVM assertion output as the only result.

## Normal compile and run behavior

Normal compiler commands parse and type-check tests so test code does not rot. Normal compile artifacts do not emit test entry points, so existing non-test source MLIR goldens remain stable. `inscription run SOURCE` ignores tests and runs `main` exactly as before.

A source file may contain tests and helper phrases without a `main`; `inscription test` does not require `main`.

## Test discovery and modules

`inscription test SOURCE` discovers tests in the root source and in modules loaded by imports from that root. Unimported files are not discovered.

Display names are deterministic:

- unmoduled root tests use `root::test name`
- module tests use `Module::test name`
- nested module names use their qualified module path

Different modules may use the same test name; duplicate names in the same module are rejected.

## CLI

The test command is:

```sh
inscription test SOURCE
```

Supported options:

```text
--module-root DIR
--runtime-checks
--opt-level none|basic|aggressive
-O0 / -O1 / -O2
--save-temps DIR
--filter TEXT
--list
```

Behavior:

- Exits `0` when all selected tests pass.
- Exits `1` when one or more selected tests fail at runtime.
- Exits `2` for compiler diagnostics and tooling errors.
- `--list` prints discovered test display names and exits without running tests.
- `--filter TEXT` runs only tests whose display name contains `TEXT`.
- If no tests are discovered, the command prints `no tests found` and exits `0`.
- If a filter matches no tests, the command prints `no tests matched filter `<TEXT>`` and exits `0`.
- `--save-temps DIR` writes per-test artifacts using deterministic test slugs.

Example passing output:

```text
test root::addition works ... ok

test result: ok. 1 passed; 0 failed.
```

Example failure output:

```text
test root::failing expectation ... FAILED

test result: FAILED. 0 passed; 1 failed.
```

## Lowering strategy

For test mode, the compiler lowers each selected test independently behind a synthetic `main` entry point. Normal user `main` functions are not emitted in that per-test artifact, avoiding entry-symbol collisions. Helper phrases, imported functions, extern declarations, and ordinary module declarations are still available to the test body.

`Expect` lowers to runtime assertion logic using the existing `cf.assert`-based machinery. Test-local owned buffers use the same lexical cleanup, move, and return rules as ordinary phrase bodies.

## Formatter and highlighter

The canonical formatter emits tests like ordinary top-level declarations, with one blank line between top-level items and no blank line between a test header and its first body sentence:

```inscription
/// Verifies addition.
Test addition works.
Expect add 20 and 22 is equal to 42.
```

The highlighter recognizes `Test` and `Expect` as sentence-leading keywords.

## Diagnostics

Representative deterministic diagnostics include:

```text
Expect is only valid inside tests
Give is not valid inside a test
Expect condition must have type i1, got i32
test `duplicate` is already defined
test `empty` must contain at least one Expect
```
