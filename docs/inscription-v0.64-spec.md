# Inscription v0.64 structured JSON diagnostics

Inscription v0.64 makes compiler, package, build, formatter, release, and test diagnostics machine-readable. It adds `--diagnostic-format text|json` to diagnostic-producing commands while keeping the v0.63 text renderer as the default.

No source-language syntax changes are introduced in v0.64.

## Command-line option

Diagnostic-producing commands accept:

```sh
--diagnostic-format text
--diagnostic-format json
```

`text` is the default and preserves human-readable diagnostics with stable codes, file/line/column spans, source excerpts, and caret markers. `json` emits structured diagnostics to stderr when a command fails. Successful artifact output remains unchanged; this option serializes diagnostics, not normal command results.

The option is supported by `compile`, `run`, `test`, `format`, `package check`, `package test`, `package build`, `package format`, `package clean`, `package release`, and `build`. Commands that already have result JSON modes, such as `version --json`, `doctor --json`, and `explain --list --json`, keep their existing JSON contracts.

## JSON schema

Ordinary diagnostic failures render a deterministic object:

```json
{
  "ok": false,
  "diagnostics": [
    {
      "severity": "error",
      "code": "INS-SEM-0001",
      "message": "unknown binding missing",
      "span": {
        "path": "/tmp/bad.ins",
        "line": 2,
        "column": 6,
        "end_line": 2,
        "end_column": 13
      },
      "notes": []
    }
  ]
}
```

Rules:

- `ok` is `false` whenever diagnostics are emitted.
- `severity` is currently always `error`.
- `code` is a diagnostic code string or `null`.
- `message` is the plain diagnostic message without `error[CODE]:`.
- `span` is `null` when no source location is available.
- `notes` is a deterministic list and may be empty.
- Paths follow the same absolute-or-relative choice as text diagnostics.
- JSON output has no source excerpts, ANSI color, timestamps, usernames, hostnames, git hashes, or trailing human text.

## Test diagnostics

`inscription test --diagnostic-format json` and package/build test failures may include a test summary:

```json
{
  "ok": false,
  "summary": {
    "passed": 0,
    "failed": 1
  },
  "tests": [
    {
      "name": "root::failure",
      "status": "failed",
      "diagnostics": [
        {
          "severity": "error",
          "code": "INS-TEST-0001",
          "message": "expect failed",
          "span": null,
          "notes": []
        }
      ]
    }
  ],
  "diagnostics": [
    {
      "severity": "error",
      "code": "INS-TEST-0001",
      "message": "expect failed",
      "span": null,
      "notes": []
    }
  ]
}
```

Test exit codes are unchanged: 0 when all tests pass, 1 for runtime expectation failures, and 2 for compiler, package, or tool diagnostics.

## Non-goals

V0.64 does not add LSP, editor integration, SARIF, JUnit, GitHub annotations, warnings, lints, fix-its, suggestions, multi-error recovery, telemetry, localization, color output, or structured success output for all commands.
