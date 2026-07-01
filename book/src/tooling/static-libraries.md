# Static Libraries

Static libraries are deterministic archives built from generated objects:

```sh
PYTHONPATH=src python -m inscription compile source.ins --emit static-library -o libsource.a
```

When a compilation contains exported phrases, the root `main` entry point is omitted from the archive object so a C caller can provide its own `main`. Additional objects can be archived with repeated `--archive-object PATH`.

Package builds default to static-library emission:

```sh
PYTHONPATH=src python -m inscription package build path/to/package
PYTHONPATH=src python -m inscription package build path/to/package --emit static-library -o libPackage.a
```

When `-o` is omitted, the package output path is `build/lib<Package>.a`. Exposed modules are included in package static libraries.
