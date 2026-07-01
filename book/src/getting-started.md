# Getting Started

From a checkout, create an environment and install the package with documentation dependencies:

```sh
python -m pip install -e ".[docs]"
```

Inscription expects LLVM/MLIR 22 tools. Set `MLIR_TOOLCHAIN` if they are not under `/usr/lib/llvm-22/bin`:

```sh
export MLIR_TOOLCHAIN=/usr/lib/llvm-22/bin
PYTHONPATH=src python -m inscription check-tools --show-pipeline
```

Create `hello.ins`:

```inscription,check
To main, giving i32.
Give 7.
```

Compile frontend MLIR:

```sh
PYTHONPATH=src python -m inscription compile hello.ins --verify
```

Run through LLVM `lli`:

```sh
PYTHONPATH=src python -m inscription run hello.ins
```

Format source:

```sh
PYTHONPATH=src python -m inscription format hello.ins --check
PYTHONPATH=src python -m inscription format hello.ins --in-place
```

Emit LLVM IR or a native executable:

```sh
PYTHONPATH=src python -m inscription compile hello.ins --emit llvm-ir --verify -o hello.ll
PYTHONPATH=src python -m inscription compile hello.ins --emit executable -o hello
./hello
```

The process exit code is the integer returned by `main`.

## Start a package

For a package skeleton with `package.ins`, `build.ins`, source, and a test:

```sh
PYTHONPATH=src python -m inscription package new hello-inscription --name HelloInscription
PYTHONPATH=src python -m inscription package check hello-inscription
PYTHONPATH=src python -m inscription package test hello-inscription
PYTHONPATH=src python -m inscription build hello-inscription --list
PYTHONPATH=src python -m inscription build hello-inscription
```

The generated `build.ins` uses `Build.standard package workflow.` so a bare build runs the default `ci` group. Add `--with-book` to generate a minimal mdBook skeleton, or `--executable` to generate a root module with `main` returning `42`.
