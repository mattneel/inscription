# Source Symbols

Inscription v0.65 can emit a deterministic source symbol/reference index for source files and packages. The index is JSON for tooling, docs generators, package inspection, and future editor/LSP work.

Index one source entry:

```sh
PYTHONPATH=src python -m inscription symbols tests/fixtures/positive/phrase_max.ins --pretty
```

Index a package:

```sh
PYTHONPATH=src python -m inscription package symbols tests/fixtures/packages/basic_package --pretty
```

Include local path dependency packages:

```sh
PYTHONPATH=src python -m inscription package symbols tests/fixtures/packages/app_with_dependency --include-dependencies --pretty
```

The JSON starts with:

```json
{
  "format": "inscription-symbol-index-v1",
  "source": "package.ins",
  "package": {
    "name": "ProtocolTools",
    "version": "0.1.0",
    "root": "."
  },
  "files": [],
  "symbols": [],
  "references": []
}
```

Symbols cover modules, type aliases, constants, records and fields, layout records, enums and cases, unions and variants, phrases, exported/external phrases, phrase parameters, tests, package declarations, dependencies, exposed modules, and `build.ins` steps/groups/defaults.

References cover imports, type uses, phrase calls, constants, enum cases, union constructors and patterns, field access, package dependencies, and build group/default step dependencies. Each symbol/reference carries a source span when available. Invalid programs do not produce partial indexes; they emit normal diagnostics, and `--diagnostic-format json` works for index commands.

The symbol index is not the same as interface JSON. Interface JSON describes the exported integration surface for host tools. The symbol index describes source declarations and references for navigation and inspection. v0.65 does not include symbol indexes in release bundles and does not add LSP, autocomplete, hover, rename, file watching, or incremental indexing.
