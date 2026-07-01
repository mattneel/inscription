# Testing

Inscription v0.44 adds first-class source tests. A test is a top-level declaration whose body uses normal step sentences plus `Expect` assertions.

```inscription,check
To add left: i32 and right: i32, giving i32.
Give left plus right.

/// Verifies integer addition.
Test addition works.
Expect add 20 and 22 is equal to 42.
```

Run tests with:

```sh
PYTHONPATH=src python -m inscription test SOURCE
```

`Test ... .` declarations are not phrases, are not callable from Inscription code, are not exported, and do not require a `main` phrase. Documentation comments may attach to tests and are preserved by the formatter, but tests are not emitted in C headers or interface JSON. Ordinary `run` ignores tests and still executes `main` when one exists.

`Expect condition.` is valid only inside tests. The condition must have type `i1`; unlike `Check`, it is evaluated at test runtime. `Require` remains a program contract and can still be used in test bodies. `Give` is not valid inside a test.

Useful runner options:

```sh
PYTHONPATH=src python -m inscription test SOURCE --list
PYTHONPATH=src python -m inscription test SOURCE --filter text
PYTHONPATH=src python -m inscription test SOURCE --runtime-checks
PYTHONPATH=src python -m inscription test SOURCE -O1
PYTHONPATH=src python -m inscription test SOURCE --save-temps /tmp/inscription-test-temps
```

Tests in imported modules are discovered when the root imports the module. Display names use `root::name` for an unmoduled root and `Module::name` for module tests.
