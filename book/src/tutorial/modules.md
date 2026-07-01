# Modules

A module file starts with `Module Name.`. Importing a module does not add unqualified names; use qualified calls and qualified type names.

`Math.ins`:

```inscription,no-check
Module Math.

To add left: i32 and right: i32, giving i32.
Give left plus right.
```

`main.ins`:

```inscription,no-check
Import Math.

To main, giving i32.
Give Math.add 20 and 22.
```

Compile from the root file and point `--module-root` at the directory containing module files when needed:

```sh
PYTHONPATH=src python -m inscription compile main.ins --module-root . --verify
```

Nested module names resolve to nested paths, so `Import geometry.points.` looks for `geometry/points.ins` under the module root.


## Package module roots

A `package.ins` manifest can declare the package source root so package commands do not need a manual `--module-root`:

```inscription,manifest
Package MathTools.

Sources are in "src".
Tests are in "tests".

Root module is MathTools.

Expose module MathTools.
```

With that manifest, `inscription package test` resolves imports from `src/` even when tests live under `tests/`.


## Path dependencies

A package can import exposed modules from a direct local path dependency declared in `package.ins`:

```inscription,manifest
Package App.

Sources are in "src".
Tests are in "tests".

Root module is App.

Expose module App.

Depend on Checksums from path "../checksums".
```

`App` source and tests may import `Checksums` and any modules exposed by that dependency. Modules inside `Checksums` that are not its root module or an `Expose module ... .` entry remain internal to that dependency.
