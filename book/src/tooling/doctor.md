# Doctor and Version

Inscription v0.61 added deterministic version reporting and health checks. v0.62 adds source-span diagnostic excerpts across common compiler/package/build errors, and v0.63 adds stable diagnostic codes plus `inscription explain`.

Print the short tool version:

```sh
PYTHONPATH=src python -m inscription --version
```

Print all version metadata:

```sh
PYTHONPATH=src python -m inscription version
PYTHONPATH=src python -m inscription version --json
```

`version --json` includes the Inscription tool version, language version, required LLVM/MLIR major version, interface JSON format, release format, package manifest format, and build script format. It does not include timestamps, hostnames, usernames, git hashes, or dirty-state checks.

Run doctor checks with:

```sh
PYTHONPATH=src python -m inscription doctor
PYTHONPATH=src python -m inscription doctor path/to/package
PYTHONPATH=src python -m inscription doctor path/to/package --json
```

Doctor is read-only. It does not build artifacts, run tests, mutate files, contact the network, install tools, or repair the environment.

Default checks include:

- version metadata
- Python version
- core package import
- required LLVM/MLIR tools: `mlir-opt`, `mlir-translate`, and `lli`
- optional tools: `llc`, `clang`, `llvm-ar`, and `mdbook`
- package manifest, source layout, exposed modules, dependencies, and build script when `package.ins` exists

Optional tools can be required for a specific workflow:

```sh
PYTHONPATH=src python -m inscription doctor --require-object
PYTHONPATH=src python -m inscription doctor --require-executable
PYTHONPATH=src python -m inscription doctor --require-static-library
PYTHONPATH=src python -m inscription doctor --require-book
```

If no package manifest exists, doctor reports `package: not found` and still succeeds when all selected environment checks pass. Use `--no-package` to skip package checks explicitly.

The Pages workflow check is local-only:

```sh
PYTHONPATH=src python -m inscription doctor --check-pages-workflow
```

It checks `.github/workflows/book.yml` for the expected Pages actions and checks `book/book.toml`. It does not contact GitHub and does not validate repository settings.

`check-tools` remains available for focused LLVM/MLIR pipeline discovery. `doctor` is broader environment and package health reporting.
