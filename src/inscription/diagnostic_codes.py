from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

CODE_RE = re.compile(r"INS-(?:PARSE|SEM|OWN|PKG|BUILD|COMP|TOOL|FMT|TEST|REL|INT)-\d{4}\Z")


@dataclass(frozen=True)
class DiagnosticCode:
    code: str
    category: str
    title: str
    summary: str
    explanation: str
    example: str | None = None


def _entry(
    code: str,
    category: str,
    title: str,
    summary: str,
    explanation: str,
    example: str | None = None,
) -> DiagnosticCode:
    return DiagnosticCode(code, category, title, summary, explanation, example)


_CODES: tuple[DiagnosticCode, ...] = (
    _entry(
        "INS-BUILD-0001",
        "BUILD",
        "Duplicate build step",
        "A build.ins script declares the same build step name more than once.",
        "Build step names share one namespace. Rename one step or remove the duplicate declaration.",
        'Build.static library named "library".\nBuild.c header named "library".',
    ),
    _entry(
        "INS-BUILD-0002",
        "BUILD",
        "Unknown Build API phrase",
        "A build.ins script calls a Build phrase that the current restricted Build API does not define.",
        "Use one of the documented Build API phrases, or keep custom workflow logic outside build.ins.",
        'Build.docs named "docs".',
    ),
    _entry(
        "INS-BUILD-0003",
        "BUILD",
        "Build step dependency cycle",
        "Build step groups form a dependency cycle.",
        "Break the cycle by making at least one group depend on a non-cyclic set of steps.",
        'Build.group named "a" with steps "b".\nBuild.group named "b" with steps "a".',
    ),
    _entry(
        "INS-BUILD-0004",
        "BUILD",
        "Invalid build script",
        "A build.ins script violates the restricted build-script shape.",
        "Ensure the script imports Build and defines exactly `To build package package: Build.Package.` before Build API calls.",
        "Import Build.\n\nTo build package package: Build.Package.",
    ),
    _entry(
        "INS-BUILD-0005",
        "BUILD",
        "Build tool missing",
        "A build step requires an external documentation or artifact tool that was not found.",
        "Install the required tool or choose a build step that does not require it.",
        'Build.book named "book".',
    ),
    _entry(
        "INS-COMP-0001",
        "COMP",
        "Unknown diagnostic code",
        "The requested diagnostic code is not in the local Inscription catalog.",
        "Check the spelling with `inscription explain --list`. Diagnostic lookup is local and deterministic.",
        "inscription explain INS-NOPE-9999",
    ),
    _entry(
        "INS-FMT-0001",
        "FMT",
        "Formatting check failed",
        "A source, package manifest, or build script is not in canonical formatter output.",
        "Run the formatter in-place or update the file to match canonical formatting.",
        "inscription package format . --in-place",
    ),
    _entry(
        "INS-INT-0001",
        "INT",
        "Comptime evaluation failed",
        "A comptime expression could not be evaluated by the pure interpreter.",
        "Restrict comptime calls to supported pure scalar/enum computations.",
        "Constant x: i32 be comptime bad value.",
    ),
    _entry(
        "INS-INT-0002",
        "INT",
        "Interpreter step limit exceeded",
        "Pure interpretation exceeded the deterministic step limit.",
        "Check for non-terminating loops or reduce compile-time work.",
        "While true: value becomes value plus 1.",
    ),
    _entry(
        "INS-INT-0003",
        "INT",
        "Unsupported interpreter feature",
        "The pure interpreter encountered a feature it intentionally does not execute.",
        "Avoid storage, extern calls, runtime buffers, or other unsupported features inside interpreted phrases.",
        "Let cells be array of 4 i32 containing 1, 2, 3, 4.",
    ),
    _entry(
        "INS-OWN-0001",
        "OWN",
        "Owned buffer was moved",
        "An owned buffer is used after its ownership has been moved.",
        "Use the moved value only through its new owner, or copy before moving when the type supports it.",
        "Call consuming phrase move cells.\nGive length of cells.",
    ),
    _entry(
        "INS-OWN-0002",
        "OWN",
        "Partial move across control flow",
        "Control-flow paths leave ownership in incompatible states.",
        "Ensure all branches move or preserve an owned value consistently before later use.",
        "When flag is equal to true: consume move cells.",
    ),
    _entry(
        "INS-OWN-0003",
        "OWN",
        "Invalid move target",
        "A move expression targets something that cannot transfer ownership.",
        "Move only owned values or supported owned-value temporaries.",
        "move 42",
    ),
    _entry(
        "INS-OWN-0004",
        "OWN",
        "Cannot copy or rebind owned buffer",
        "An owned buffer operation would duplicate or overwrite ownership unsafely.",
        "Use explicit move/copy forms supported by the owned-buffer rules.",
        "cells becomes other_cells.",
    ),
    _entry(
        "INS-PARSE-0001",
        "PARSE",
        "Expected period",
        "A punctuation sentence is missing its terminating period.",
        "End every Inscription punctuation sentence with a period.",
        "To main, giving i32.\nGive 42",
    ),
    _entry(
        "INS-PARSE-0002",
        "PARSE",
        "Unexpected token",
        "The parser found syntax that does not match the expected grammar form.",
        "Check punctuation, keywords, phrase-call spelling, and declaration shape near the highlighted source.",
        "Give (1 plus).",
    ),
    _entry(
        "INS-PARSE-0003",
        "PARSE",
        "Unterminated string literal",
        "A string or byte string literal ends before its closing quote.",
        "Add the closing quote or escape embedded quotes correctly.",
        'Give length of bytes "abc.',
    ),
    _entry(
        "INS-PARSE-0004",
        "PARSE",
        "Invalid escape sequence",
        "A string or byte literal contains an unsupported escape sequence.",
        "Use a supported escape such as `\\n`, `\\t`, `\\\"`, `\\\\`, or a valid hex byte escape.",
        'Give length of bytes "\\q".',
    ),
    _entry(
        "INS-PARSE-0005",
        "PARSE",
        "Legacy syntax not supported",
        "The parser found old pre-punctuation syntax.",
        "Rewrite the source using v0.32+ prose punctuation syntax.",
        "main gives i32:",
    ),
    _entry(
        "INS-PKG-0001",
        "PKG",
        "Invalid package manifest",
        "package.ins is missing required declarations or contains an unsupported manifest sentence.",
        "Use Package, Version, Sources, Tests, Root module, Expose module, and Depend on declarations only.",
        'Package ProtocolTools.\nSources are in "src".\nRoot module is ProtocolTools.',
    ),
    _entry(
        "INS-PKG-0002",
        "PKG",
        "Duplicate package declaration",
        "package.ins declares a singleton field more than once.",
        "Remove one duplicate Package, Version, Sources, Tests, or Root module declaration.",
        'Sources are in "src".\nSources are in "source".',
    ),
    _entry(
        "INS-PKG-0003",
        "PKG",
        "Package path invalid",
        "A package source/test/dependency path violates manifest path rules.",
        "Use deterministic relative paths. Source/test paths may not be absolute, empty, or contain `..`.",
        'Sources are in "../src".',
    ),
    _entry(
        "INS-PKG-0004",
        "PKG",
        "Package dependency cycle",
        "Local path package dependencies form a cycle.",
        "Remove or restructure one dependency so the package graph is acyclic.",
        "App -> Checksums -> App",
    ),
    _entry(
        "INS-PKG-0005",
        "PKG",
        "Package module not exposed",
        "A package imports a dependency module that the dependency does not expose.",
        "Expose the module in the dependency manifest or import only the dependency root/exposed modules.",
        "Import Checksums.Internal.",
    ),
    _entry(
        "INS-REL-0001",
        "REL",
        "Release output exists",
        "A release output directory already exists and is nonempty.",
        "Choose a new output directory or pass `--clean` to replace the release output.",
        "inscription package release . --clean",
    ),
    _entry(
        "INS-REL-0002",
        "REL",
        "Release archive failed",
        "A deterministic release archive could not be created.",
        "Check filesystem permissions and that the archive path is not an invalid directory conflict.",
        "inscription package release . --archive",
    ),
    _entry(
        "INS-REL-0003",
        "REL",
        "Checksum failed",
        "A release checksum manifest or archive checksum could not be written.",
        "Check filesystem permissions and rerun the release command.",
        "inscription package release . --checksum",
    ),
    _entry(
        "INS-SEM-0001",
        "SEM",
        "Unknown binding",
        "The compiler could not find a binding with the requested name in the current scope.",
        "Declare the binding before using it, or use the correct in-scope name.",
        "To main, giving i32.\nGive missing.",
    ),
    _entry(
        "INS-SEM-0002",
        "SEM",
        "Unknown phrase",
        "A phrase call does not match any phrase visible in the current compilation.",
        "Check phrase spelling, imported modules, and argument labels.",
        "Give addd 20 and 22.",
    ),
    _entry(
        "INS-SEM-0003",
        "SEM",
        "Type mismatch",
        "An expression has a different type than the surrounding context requires.",
        "Adjust the expression, cast explicitly where allowed, or change the expected type.",
        "To main, giving i32.\nGive true.",
    ),
    _entry(
        "INS-SEM-0004",
        "SEM",
        "Invalid return value",
        "A phrase returns no value or a value incompatible with its declared return type.",
        "Ensure `giving` phrases end with a value of the declared type.",
        "To main, giving i32.\nGive true.",
    ),
    _entry(
        "INS-SEM-0005",
        "SEM",
        "Match is not exhaustive",
        "A match expression or step does not cover every possible input value.",
        "Add the missing case, range, alternative, or an `anything` arm.",
        "Give match mode: Mode.idle gives 0.",
    ),
    _entry(
        "INS-SEM-0006",
        "SEM",
        "Duplicate or unreachable match pattern",
        "A match arm can never be selected because an earlier arm already covers it.",
        "Remove the redundant arm or make an earlier pattern narrower.",
        "anything gives 0; 1 gives 1.",
    ),
    _entry(
        "INS-SEM-0007",
        "SEM",
        "Unsupported type in this context",
        "A type appears in a language position that the current language does not support.",
        "Use one of the supported scalar/storage/value types for that context.",
        "To main, giving buffer of 4 i32.",
    ),
    _entry(
        "INS-TEST-0001",
        "TEST",
        "Expect failed",
        "A source-level test expectation evaluated to false at runtime.",
        "Inspect the failing test, then fix the tested phrase or the expected value.",
        "Expect add 20 and 22 is equal to 41.",
    ),
    _entry(
        "INS-TOOL-0001",
        "TOOL",
        "Required tool not found",
        "A required external LLVM/MLIR or documentation tool was not found.",
        "Install the required toolchain or set the appropriate environment path.",
        "MLIR_TOOLCHAIN=/usr/lib/llvm-22/bin inscription check-tools",
    ),
    _entry(
        "INS-TOOL-0002",
        "TOOL",
        "Tool version mismatch",
        "An external tool exists but does not report the required version.",
        "Install the required LLVM/MLIR major version or point Inscription at the matching toolchain.",
        "required LLVM/MLIR: 22.x",
    ),
)

DIAGNOSTIC_CODES: dict[str, DiagnosticCode] = {entry.code: entry for entry in sorted(_CODES, key=lambda item: item.code)}


def lookup_diagnostic_code(code: str) -> DiagnosticCode | None:
    return DIAGNOSTIC_CODES.get(code.upper())


def sorted_diagnostic_codes() -> tuple[DiagnosticCode, ...]:
    return tuple(DIAGNOSTIC_CODES[code] for code in sorted(DIAGNOSTIC_CODES))


def diagnostic_catalog_payload() -> list[dict[str, object]]:
    return [asdict(entry) for entry in sorted_diagnostic_codes()]


def diagnostic_catalog_json() -> str:
    return json.dumps(diagnostic_catalog_payload(), indent=2, ensure_ascii=False) + "\n"


def explain_diagnostic_code(entry: DiagnosticCode) -> str:
    parts = [f"{entry.code}: {entry.title}", "", entry.summary]
    if entry.explanation and entry.explanation != entry.summary:
        parts.extend(["", entry.explanation])
    if entry.example:
        parts.extend(["", "Example:", "", *[f"  {line}" for line in entry.example.splitlines()]])
    return "\n".join(parts) + "\n"


def diagnostic_code_for_message(message: str) -> str | None:
    text = message.strip()
    lower = text.lower()
    first_line = lower.splitlines()[0] if lower else lower

    if "formatting check failed" in lower or "not formatted" in lower:
        return "INS-FMT-0001"
    if "release output directory already exists" in lower or "release output path exists" in lower:
        return "INS-REL-0001"
    if "release archive path" in lower or "failed to create release archive" in lower:
        return "INS-REL-0002"
    if "checksum" in lower and ("failed" in lower or "write" in lower):
        return "INS-REL-0003"
    if "required llvm" in lower and "not found" in lower:
        return "INS-TOOL-0001"
    if "required tool" in lower and "not found" in lower:
        return "INS-TOOL-0001"
    if "mdbook" in lower and "not found" in lower:
        return "INS-TOOL-0001"
    if "does not report llvm" in lower:
        return "INS-TOOL-0002"

    if first_line.startswith("unknown diagnostic code"):
        return "INS-COMP-0001"

    if "build step" in lower and "already defined" in lower:
        return "INS-BUILD-0001"
    if "unknown build api phrase" in lower or "malformed build artifact request" in lower:
        return "INS-BUILD-0002"
    if "build step dependency cycle detected" in lower:
        return "INS-BUILD-0003"
    if "build script" in lower or first_line.startswith("build phrase") or "build group" in lower:
        return "INS-BUILD-0004"
    if "book step requires mdbook" in lower or "book check step" in lower:
        return "INS-BUILD-0005"

    if "package dependency cycle detected" in lower:
        return "INS-PKG-0004"
    if "not exposed by package" in lower:
        return "INS-PKG-0005"
    if "declares" in lower and "more than once" in lower and ("package manifest" in lower or "dependency" in lower):
        return "INS-PKG-0002"
    if "package path" in lower or "package paths" in lower or "dependency path" in lower or "dependency paths" in lower:
        return "INS-PKG-0003"
    if first_line.startswith("package") or first_line.startswith("dependency") or first_line.startswith("root module") or first_line.startswith("exposed module"):
        return "INS-PKG-0001"

    if "comptime evaluation failed" in lower:
        return "INS-INT-0001"
    if "interpreter step limit exceeded" in lower:
        return "INS-INT-0002"
    if "interpreter does not support" in lower:
        return "INS-INT-0003"

    if "owned buffer" in lower and "was moved" in lower:
        return "INS-OWN-0001"
    if "partial move" in lower or "different ownership" in lower:
        return "INS-OWN-0002"
    if "invalid move" in lower or "cannot move" in lower:
        return "INS-OWN-0003"
    if "owned buffer" in lower and ("copy" in lower or "rebind" in lower or "assignment" in lower):
        return "INS-OWN-0004"

    if "missing period" in lower:
        return "INS-PARSE-0001"
    if "unterminated string literal" in lower:
        return "INS-PARSE-0003"
    if "invalid escape" in lower or "hex escape" in lower:
        return "INS-PARSE-0004"
    if "legacy" in lower:
        return "INS-PARSE-0005"
    if first_line.startswith("unexpected token") or first_line.startswith("expected ") or "malformed" in lower:
        return "INS-PARSE-0002"

    if "unknown binding" in lower:
        return "INS-SEM-0001"
    if "unknown phrase" in lower or "cannot find phrase" in lower:
        return "INS-SEM-0002"
    if "match" in lower and ("missing" in lower or "not exhaustive" in lower):
        return "INS-SEM-0005"
    if "match pattern" in lower and ("unreachable" in lower or "duplicate" in lower):
        return "INS-SEM-0006"
    if "must have type" in lower or ", got " in lower or "must be" in lower and "type" in lower:
        if "return" in lower or "give" in lower or "main" in lower:
            return "INS-SEM-0004"
        return "INS-SEM-0003"
    if "not supported" in lower and "type" in lower:
        return "INS-SEM-0007"

    return None
