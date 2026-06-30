# Static Libraries

Static libraries are deterministic archives built from generated objects:

```sh
PYTHONPATH=src python -m inscription compile source.ins --emit static-library -o libsource.a
```

When a compilation contains exported phrases, the root `main` entry point is omitted from the archive object so a C caller can provide its own `main`. Additional objects can be archived with repeated `--archive-object PATH`.
