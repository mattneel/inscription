# Inscription v0.65 source symbol index

Inscription v0.65 adds a deterministic source-index layer for source navigation, package inspection, documentation generation, and future editor/LSP tooling. It does not add source-language syntax, lowering, or runtime semantics.

## Commands

Single-source indexing:

```sh
PYTHONPATH=src python -m inscription symbols path/to/source.ins --pretty
```

Package indexing:

```sh
PYTHONPATH=src python -m inscription package symbols path/to/package --pretty
PYTHONPATH=src python -m inscription package symbols path/to/package --include-dependencies --pretty
```

Both commands emit JSON by default. `--diagnostic-format text|json` controls failure diagnostics. `symbols SOURCE --package` treats `SOURCE` as a package root and emits the package index.

## JSON format

The output format identifier is `inscription-symbol-index-v1`:

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

`--pretty` uses two-space indentation. Compact JSON is emitted otherwise. Output is deterministic: files, declarations, references, and object keys are ordered by package/compile load order and source position.

## Symbols

v0.65 indexes top-level source declarations and package/build declarations:

- `module`
- `type_alias`
- `constant`
- `record`, `layout_record`, `packed_layout_record`, and `record_field`
- `enum` and `enum_case`
- `union`, `union_variant`, and `union_payload`
- `phrase`, `exported_phrase`, `external_phrase`, and `phrase_parameter`
- `test`
- `package`, `package_dependency`, and `exposed_module`
- `build_step`, `build_group`, and `build_default`

Each symbol includes a deterministic `id`, kind, name, optional qualified name, module, path, source span, documentation text when available, type text when available, and a stable detail dictionary.

## References

v0.65 indexes representative source references:

- module imports
- type references
- phrase calls
- constant references
- enum case references
- union constructor and union pattern references
- field references
- package dependency references
- build group/default step references

References include their kind, source name, target symbol id when resolved, path, span, and stable detail dictionary. v0.65 does not provide partial indexes for invalid programs; ordinary diagnostics are emitted instead.

## Package behavior

`inscription package symbols ROOT` reads `package.ins`, validates the package graph, indexes manifest declarations, source modules, test files, and `build.ins` when present. Dependency package symbols are included only with `--include-dependencies`; root-package references to dependency modules may still appear without dependency symbols.

The symbol index is separate from interface JSON. Interface JSON describes exported host integration surfaces, while the source index describes source-navigation and developer-tooling surfaces. Release bundles do not include symbol indexes in v0.65.

## Non-goals

v0.65 does not add an LSP server, editor integration, hover text, completion, rename, incremental indexing, file watching, semantic tokens, release-bundle symbol indexes, or new source syntax.
