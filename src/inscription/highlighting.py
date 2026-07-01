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
        from pygments.token import Comment, Error, Keyword, Name, Number, Operator, Punctuation, String, Text
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
                (r"///.*?$|//!.*?$", Comment.Special),
                (r"//.*?$", Comment.Single),
                (r"([a-z][a-z0-9_]*)(:)(\s*)(i1|i8|i16|i32|i64|u8|u16|u32|u64|f32|f64)\b", bygroups(
                    Name.Variable,
                    Punctuation,
                    Text.Whitespace,
                    Keyword.Type,
                )),
                (r"\b(giving|gives)(\s+)(owned\s+buffer\s+of\s+)?(i1|i8|i16|i32|i64|u8|u16|u32|u64|f32|f64|[A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)?)\b", bygroups(Keyword.Declaration, Text.Whitespace, Keyword.Declaration, Keyword.Type)),
                (r"\b(Packed|packed)(\s+)(layout)(\s+)(record)(\s+)([A-Z][A-Za-z0-9_]*)", bygroups(Keyword.Declaration, Text.Whitespace, Keyword.Declaration, Text.Whitespace, Keyword.Declaration, Text.Whitespace, Name.Class)),
                (r"\b(Layout|layout)(\s+)(record)(\s+)([A-Z][A-Za-z0-9_]*)", bygroups(Keyword.Declaration, Text.Whitespace, Keyword.Declaration, Text.Whitespace, Name.Class)),
                (r"\b(Record|record)(\s+)([A-Z][A-Za-z0-9_]*)", bygroups(Keyword.Declaration, Text.Whitespace, Name.Class)),
                (r"\b(i1|i8|i16|i32|i64|u8|u16|u32|u64|f32|f64)\b", Keyword.Type),
                (r"\b(Module|Import|Package|Version|Sources|Tests|Root|Expose|Type|Constant|Check|Record|Layout|Packed|Enum|Union|External|To|Test|Let|Require|Expect|Give|When|Otherwise|While|For|Match|be|has|backed|by|giving|exported|as|from|for|of|with|and|into|at|each|index|up|to|otherwise|anything|zero|buffer|array|view|filled|containing|copied|does|gives|length|record|layout|packed|size|alignment|offset|in|read|write|constant|check|require|module|import|extern|export|enum|union|match|type|byte|bytes|owned|then|move|when|through|ignored)\b", Keyword),
                (r"\b(true|false)\b", Keyword.Constant),
                (r"\b(becomes|plus|minus|times|divided|by|remainder|and|or|not|as|bitwise|shifted|left|right|xor)\b", Operator.Word),
                (r"\b(is|equal|less|greater|than)\b", Operator.Word),
                (r'"(?:\\.|[^"\\])*"', String.Double),
                (r"\d+\.\d+(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+", Number.Float),
                (r"-?\d+", Number.Integer),
                (r"[A-Z][A-Za-z0-9_]*", Name.Class),
                (r"[,:;().]", Punctuation),
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
    nowrap: bool = False,
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
            formatter = HtmlFormatter(style=style, full=full, nowrap=nowrap)
        else:
            raise HighlightError(f"unsupported highlight format '{output_format}'")
    except ClassNotFound as exc:
        raise HighlightError(f"unknown Pygments style '{style}'") from exc

    return pygments_highlight(source, _make_lexer(), formatter)
