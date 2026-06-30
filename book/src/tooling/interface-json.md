# Interface JSON

`compile --emit interface-json` emits deterministic metadata for host tooling. It includes modules, type aliases, constants, enums, unions, records, layout records, exported phrases, and extern phrases.

```sh
PYTHONPATH=src python -m inscription compile source.ins --emit interface-json -o interface.json
```

The output contains no timestamps, absolute source paths, usernames, hostnames, or git hashes.
