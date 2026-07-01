# Executables

Executable emission lowers to LLVM IR, builds an object with LLVM 22 `llc`, and links with LLVM 22 `clang`.

```sh
PYTHONPATH=src python -m inscription compile source.ins --emit executable -o source
./source
```

The root program must provide a no-hole `main` returning an integer scalar. Additional objects can be linked with repeated `--link-object PATH`.

Package executables build the manifest root module:

```sh
PYTHONPATH=src python -m inscription package build path/to/package --emit executable -o app
./app
```

The root module must define runnable `main`. Exposed modules are included only when imported by the executable root.
