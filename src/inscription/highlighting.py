from __future__ import annotations

from typing import Literal

OutputFormat = Literal["terminal", "html"]


class HighlightError(Exception):
    """Raised when source highlighting cannot be produced."""


def _missing_pygments() -> HighlightError:
    return HighlightError("highlight command requires Pygments; install project dependencies")


def _make_lexer():
    try:
        from pygments.lexer import RegexLexer, bygroups
        from pygments.token import Error, Keyword, Name, Number, Operator, Punctuation, Text
    except ModuleNotFoundError as exc:
        if exc.name == "pygments":
            raise _missing_pygments() from exc
        raise

    class InscriptionLexer(RegexLexer):
        name = "Inscription"
        aliases = ["inscription", "ins"]
        filenames = ["*.ins"]
        mimetypes = ["text/x-inscription"]
        tokens = {
            "root": [
                (r"\s+", Text.Whitespace),
                (r"([a-z][a-z0-9_]*)(:)(\s*)(i1|i8|i16|i32|i64|u8|u16|u32|u64)\b", bygroups(
                    Name.Variable,
                    Punctuation,
                    Text.Whitespace,
                    Keyword.Type,
                )),
                (r"\b(gives)(\s+)(i1|i8|i16|i32|i64|u8|u16|u32|u64)\b", bygroups(Keyword.Declaration, Text.Whitespace, Keyword.Type)),
                (r"\b(if|let|be|from|when|while|otherwise|zero|buffer|filled|with|at)\b", Keyword),
                (r"\b(true|false)\b", Keyword.Constant),
                (r"\b(becomes|plus|minus|times|divided|by|remainder|and|or|not|as|bitwise|shifted|left|right|xor)\b", Operator.Word),
                (r"\b(is|equal|less|greater|than)\b", Operator.Word),
                (r"-?\d+", Number.Integer),
                (r"[:,()]", Punctuation),
                (r"[a-z][a-z0-9_]*", Name.Variable),
                (r".", Error),
            ]
        }

    return InscriptionLexer()


def highlight_source(
    source: str,
    *,
    output_format: OutputFormat = "terminal",
    style: str = "default",
    full: bool = False,
) -> str:
    try:
        from pygments import highlight as pygments_highlight
        from pygments.formatters import HtmlFormatter, Terminal256Formatter
        from pygments.util import ClassNotFound
    except ModuleNotFoundError as exc:
        if exc.name == "pygments":
            raise _missing_pygments() from exc
        raise

    try:
        if output_format == "terminal":
            formatter = Terminal256Formatter(style=style)
        elif output_format == "html":
            formatter = HtmlFormatter(style=style, full=full)
        else:
            raise HighlightError(f"unsupported highlight format '{output_format}'")
    except ClassNotFound as exc:
        raise HighlightError(f"unknown Pygments style '{style}'") from exc

    return pygments_highlight(source, _make_lexer(), formatter)
