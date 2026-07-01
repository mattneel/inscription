# Interface JSON

`compile --emit interface-json` emits deterministic metadata for host tooling. It includes modules, type aliases, constants, enums, unions, records, layout records, exported phrases, and extern phrases.

```sh
PYTHONPATH=src python -m inscription compile source.ins --emit interface-json -o interface.json
```

The output contains no timestamps, absolute source paths, usernames, hostnames, or git hashes.

Documentation comments are included as `documentation` fields where the interface format already emits a module or declaration. Missing documentation is represented as `null`.

```inscription,format
//! Root module docs.

/// A count type.
Type Count be i32.

/// Adds counts.
To add counts left: Count and right: Count, giving Count, exported as ins_add_counts.
Give left plus right.
```

Ordinary `//` comments are not included in interface JSON. Documentation comments cannot attach to imports.
