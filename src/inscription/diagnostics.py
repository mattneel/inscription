from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .diagnostic_codes import diagnostic_code_for_message


@dataclass(frozen=True)
class SourceSpan:
    path: str | None
    line: int
    column: int = 1
    end_line: int | None = None
    end_column: int | None = None


@dataclass(frozen=True)
class DiagnosticNote:
    message: str
    span: SourceSpan | None = None


@dataclass(frozen=True)
class Diagnostic:
    message: str
    span: SourceSpan | None = None
    severity: str = "error"
    code: str | None = None
    notes: tuple[DiagnosticNote, ...] = ()


class InscriptionError(Exception):
    """Base diagnostic for deterministic compiler failures."""

    def __init__(
        self,
        message: str,
        line: int | None = None,
        *,
        column: int | None = None,
        end_line: int | None = None,
        end_column: int | None = None,
        path: str | Path | None = None,
        source: str | None = None,
        code: str | None = None,
        notes: tuple[DiagnosticNote, ...] = (),
    ):
        self.message = message
        self.line = line
        self.column = column
        self.end_line = end_line
        self.end_column = end_column
        self.path = _path_text(path)
        self.source = source
        self.code = code or diagnostic_code_for_message(message)
        self.notes = notes
        if line is None:
            super().__init__(message)
        else:
            super().__init__(f"line {line}: {message}")

    @property
    def span(self) -> SourceSpan | None:
        if self.line is None:
            return None
        return SourceSpan(
            self.path,
            self.line,
            self.column or 1,
            self.end_line,
            self.end_column,
        )

    def attach_source(
        self,
        source: str | None,
        path: str | Path | None = None,
        *,
        line: int | None = None,
        column: int | None = None,
    ) -> "InscriptionError":
        """Attach source context to an existing diagnostic without changing its text."""

        if source is not None and self.source is None:
            self.source = source
        if path is not None and self.path is None:
            self.path = _path_text(path)
        if line is not None and self.line is None:
            self.line = line
        if column is not None and self.column is None:
            self.column = column
        return self

    def to_diagnostic(self) -> Diagnostic:
        return Diagnostic(self.message, self.span, code=self.code, notes=self.notes)


def render_exception(exc: InscriptionError) -> str:
    return render_diagnostic(exc.to_diagnostic(), source=exc.source)


def diagnostic_to_payload(diagnostic: Diagnostic) -> dict[str, object]:
    return {
        "severity": diagnostic.severity or "error",
        "code": diagnostic.code,
        "message": diagnostic.message,
        "span": _span_payload(diagnostic.span),
        "notes": [
            {
                "message": note.message,
                "span": _span_payload(note.span),
            }
            for note in diagnostic.notes
        ],
    }


def diagnostics_payload(diagnostics: list[Diagnostic] | tuple[Diagnostic, ...]) -> dict[str, object]:
    return {
        "ok": False,
        "diagnostics": [diagnostic_to_payload(diagnostic) for diagnostic in diagnostics],
    }


def render_diagnostics_json(diagnostics: list[Diagnostic] | tuple[Diagnostic, ...]) -> str:
    """Render deterministic machine-readable diagnostics."""

    return json.dumps(diagnostics_payload(diagnostics), indent=2, ensure_ascii=False) + "\n"


def render_diagnostic(diagnostic: Diagnostic, *, source: str | None = None) -> str:
    """Render a deterministic, color-free diagnostic with a source excerpt."""

    severity = diagnostic.severity or "error"
    header = f"{severity}[{diagnostic.code}]" if diagnostic.code else severity
    out = [f"{header}: {diagnostic.message}"]
    if diagnostic.span is not None:
        _append_span(out, diagnostic.span, diagnostic.message, source)
    for note in diagnostic.notes:
        out.append(f"note: {note.message}")
        if note.span is not None:
            _append_span(out, note.span, note.message, source)
    return "\n".join(out)


def _append_span(out: list[str], span: SourceSpan, message: str, source: str | None) -> None:
    line = span.line
    column = span.column or 1
    source_line = _source_line(source, line)
    if source_line is not None:
        column, width = _resolve_caret(message, source_line, column, span)
    else:
        width = 1
    location = _format_location(span.path, line, column)
    out.append(f" --> {location}")
    if source_line is None:
        return
    line_no = str(line)
    gutter_width = len(line_no)
    out.append(f" {' ' * gutter_width} |")
    out.append(f" {line_no} | {source_line}")
    caret_column = max(1, min(column, len(source_line) + 1))
    caret_prefix = " " * (caret_column - 1)
    caret_width = max(1, width)
    out.append(f" {' ' * gutter_width} | {caret_prefix}{'^' * caret_width}")


def _format_location(path: str | None, line: int, column: int) -> str:
    if path:
        return f"{_display_path(path)}:{line}:{column}"
    return f"{line}:{column}"


def _span_payload(span: SourceSpan | None) -> dict[str, object] | None:
    if span is None:
        return None
    return {
        "path": _display_path(span.path) if span.path else None,
        "line": span.line,
        "column": span.column or 1,
        "end_line": span.end_line if span.end_line is not None else span.line,
        "end_column": span.end_column if span.end_column is not None else (span.column or 1),
    }


def _display_path(path: str) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        return path
    try:
        return candidate.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path


def _source_line(source: str | None, line: int) -> str | None:
    if source is None or line < 1:
        return None
    lines = source.splitlines()
    if line > len(lines):
        return None
    return lines[line - 1]


def _resolve_caret(message: str, line_text: str, column: int, span: SourceSpan) -> tuple[int, int]:
    if span.end_line in (None, span.line) and span.end_column is not None and span.end_column > column:
        return column, span.end_column - column
    if column != 1:
        return column, 1
    inferred = _infer_token_from_message(message, line_text)
    if inferred is not None:
        return inferred
    if "period" in message and line_text:
        return len(line_text) + 1, 1
    first_token = re.search(r"\S+", line_text)
    if first_token is not None:
        return first_token.start() + 1, max(1, len(first_token.group(0)))
    return 1, 1


def _infer_token_from_message(message: str, line_text: str) -> tuple[int, int] | None:
    tokens: list[str] = []
    patterns = (
        r"unknown binding ([A-Za-z_][A-Za-z0-9_\.]*)",
        r"owned buffer ([A-Za-z_][A-Za-z0-9_\.]*) was moved",
        r"argument ([A-Za-z_][A-Za-z0-9_\.]*) must have type",
        r"constant ([A-Za-z_][A-Za-z0-9_\.]*) ",
        r"build step ([A-Za-z_][A-Za-z0-9_-]*) is already defined",
        r"dependency ([A-Za-z_][A-Za-z0-9_\.]*) ",
        r"module ([A-Za-z_][A-Za-z0-9_\.]*) ",
        r"type ([A-Za-z_][A-Za-z0-9_\.]*) ",
        r"enum ([A-Za-z_][A-Za-z0-9_\.]*) ",
        r"record ([A-Za-z_][A-Za-z0-9_\.]*) ",
        r"union ([A-Za-z_][A-Za-z0-9_\.]*) ",
    )
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            tokens.append(match.group(1))
    quoted = re.findall(r"`([^`]+)`", message)
    tokens.extend(quoted)
    for token in tokens:
        if not token:
            continue
        index = line_text.find(token)
        if index >= 0:
            return index + 1, max(1, len(token))
    return None


def _path_text(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return path.as_posix() if isinstance(path, Path) else str(path)
