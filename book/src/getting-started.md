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
