from __future__ import annotations

import re
from dataclasses import dataclass

from .ast import (
    ArrayBinding,
    ArrayType,
    AssignStmt,
    Binary,
    BodyStmt,
    Boolean,
    ByteLiteral,
    ByteString,
    BufferBinding,
    BufferLoad,
    BufferStoreStmt,
    BufferType,
    Call,
    CallStmt,
    Cast,
    CheckStmt,
    Comparison,
    ComptimeExpr,
    ConstantDecl,
    EnumCase,
    EnumCaseDecl,
    EnumDecl,
    ExpectStmt,
    Expr,
    FieldAccess,
    FieldAssignStmt,
    Float,
    ForEachStmt,
    ForStmt,
    Function,
    IfStmt,
    ImportDecl,
    Integer,
    AlignmentOfType,
    AlternativePattern,
    AnythingPattern,
    LengthOf,
    LengthOfBytes,
    LayoutRead,
    LayoutWriteStmt,
    MatchExpr,
    MatchExprArm,
    MatchStep,
    MatchStepArm,
    MoveArg,
    OffsetOfField,
    OwnedBufferBinding,
    OwnedBufferType,
    Parameter,
    Program,
    RecordConstructor,
    RecordDecl,
    RecordFieldDecl,
    RecordFieldInit,
    RecordType,
    RangePattern,
    RequireStmt,
    ReturnType,
    ReturnStmt,
    SetStmt,
    SizeOfType,
    StorageAliasBinding,
    StorageElement,
    TestDecl,
    TypeAliasDecl,
    TypeName,
    Unary,
    UnionConstructor,
    UnionDecl,
    UnionFieldInit,
    UnionPattern,
    UnionPatternBinding,
    UnionPayloadField,
    UnionVariantDecl,
    ValueType,
    Variable,
    ViewBinding,
    ViewType,
    WhenCase,
    WhenExpr,
    WhileStmt,
)
from .diagnostics import InscriptionError

NAME_RE = re.compile(r"[a-z][a-z0-9_]*")
RECORD_NAME_RE = re.compile(r"[A-Z][A-Za-z0-9_]*")
QUALIFIED_RECORD_NAME_RE = re.compile(r"(?:[A-Za-z][A-Za-z0-9_]*\.)*[A-Z][A-Za-z0-9_]*")
FLOAT_LITERAL_RE = r"(?:\d+\.\d+(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)"
STRING_LITERAL_RE = r'"(?:\\.|[^"\\])*"'
TOKEN_RE = re.compile(rf"\s*({STRING_LITERAL_RE}|{FLOAT_LITERAL_RE}|-?\d+|[A-Z][A-Za-z0-9_]*|[a-z][a-z0-9_]*|[().,])")
RESERVED = {
    "address", "alignment", "and", "anything", "arguments", "array", "as", "at", "be", "becomes", "bitwise", "buffer", "by", "call",
    "check", "comptime", "constant", "containing", "divided", "do", "does", "each", "else", "equal", "expect", "export", "extern", "false", "filled", "float", "for", "from",
    "enum", "function", "gives", "greater", "f32", "f64", "i1", "i32", "i64", "if", "in", "index", "input", "into", "import",
    "i8", "i16", "is", "layout", "length", "less", "let", "match", "memref", "minus", "module", "move", "no", "not", "or", "otherwise", "output", "packed", "parameters",
    "pointer", "plus", "print", "read", "remainder", "require", "return", "set", "shifted", "size", "takes", "test", "than", "then", "through", "times", "to",
    "track", "true", "type", "u8", "u16", "u32", "u64", "union", "up", "record", "view", "when", "while", "with", "write", "xor", "zero",
}
TYPE_NAMES: set[str] = {"i1", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "f32", "f64"}
COMPARATORS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("equal", "to"), "eq"),
    (("not", "equal", "to"), "ne"),
    (("less", "than", "or", "equal", "to"), "sle"),
    (("less", "than"), "slt"),
    (("greater", "than", "or", "equal", "to"), "sge"),
    (("greater", "than"), "sgt"),
)
CONNECTOR_WORDS = {"of", "from", "to", "at", "in", "into", "between", "and", "with", "by"}
BUFFER_LENGTH_PATTERN = r"(?:-?\d+|[a-z][a-z0-9_]*|\([^)]*\))"
TYPE_REF_PATTERN = r"(?:(?:[A-Za-z][A-Za-z0-9_]*\.)*[A-Z][A-Za-z0-9_]*|[a-z][a-z0-9_]*)"
TYPE_PATTERN = rf"(?:buffer\s+of\s+{BUFFER_LENGTH_PATTERN}\s+{TYPE_REF_PATTERN}|array\s+of\s+{BUFFER_LENGTH_PATTERN}\s+{TYPE_REF_PATTERN}|view\s+of\s+{TYPE_REF_PATTERN}|(?:[A-Za-z][A-Za-z0-9_]*\.)*[A-Z][A-Za-z0-9_]*|[a-z][a-z0-9_]*)"
OWNED_BUFFER_RETURN_PATTERN = rf"owned\s+buffer\s+of\s+{TYPE_REF_PATTERN}"
PHRASE_HOLE_TYPE_PATTERN = rf"(?:{OWNED_BUFFER_RETURN_PATTERN}|{TYPE_PATTERN})"
MODULE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*")
EXTERNAL_SYMBOL_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"


def parse_source(
    source: str,
    *,
    external_phrases: tuple["PhraseTemplate", ...] = (),
    symbol_prefix: str | None = None,
) -> Program:
    return Parser(source, external_phrases=external_phrases, symbol_prefix=symbol_prefix).parse_program()


@dataclass(frozen=True)
class Line:
    number: int
    text: str
    is_header: bool
    indent: int


@dataclass(frozen=True)
class PhraseHole:
    name: str
    type_name: ValueType


PhrasePart = str | PhraseHole


@dataclass(frozen=True)
class PhraseTemplate:
    symbol: str
    parts: tuple[PhrasePart, ...]
    params: tuple[Parameter, ...]
    line: int
    return_type: ReturnType
    display_name: str


def decode_byte_string_token(token: str, line: int) -> tuple[int, ...]:
    if not (len(token) >= 2 and token[0] == '"' and token[-1] == '"'):
        raise InscriptionError("unterminated string literal", line)
    body = token[1:-1]
    out: list[int] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char != "\\":
            out.extend(char.encode("utf-8"))
            index += 1
            continue
        if index + 1 >= len(body):
            raise InscriptionError("unterminated string literal", line)
        escaped = body[index + 1]
        if escaped == "\\":
            out.append(ord("\\"))
            index += 2
            continue
        if escaped == '"':
            out.append(ord('"'))
            index += 2
            continue
        if escaped == "n":
            out.append(10)
            index += 2
            continue
        if escaped == "r":
            out.append(13)
            index += 2
            continue
        if escaped == "t":
            out.append(9)
            index += 2
            continue
        if escaped == "0":
            out.append(0)
            index += 2
            continue
        if escaped == "x":
            digits = body[index + 2 : index + 4]
            if len(digits) != 2:
                raise InscriptionError("hex escape must contain exactly two hexadecimal digits", line)
            if not re.fullmatch(r"[0-9A-Fa-f]{2}", digits):
                raise InscriptionError("hex escape contains non-hexadecimal digit", line)
            out.append(int(digits, 16))
            index += 4
            continue
        raise InscriptionError(f"invalid escape sequence \\{escaped}", line)
    return tuple(out)


def _is_string_token(token: str) -> bool:
    return len(token) >= 2 and token[0] == '"' and token[-1] == '"'


ParsedTopLevel = RecordDecl | EnumDecl | UnionDecl | TypeAliasDecl | ConstantDecl | CheckStmt | Function | TestDecl


TOP_LEVEL_SENTENCE_PREFIXES = (
    "Module ",
    "Import ",
    "Type ",
    "Constant ",
    "Check ",
    "Record ",
    "Layout record ",
    "Packed layout record ",
    "Enum ",
    "Union ",
    "External ",
    "To ",
    "Test ",
)

DOCUMENTABLE_SENTENCE_PREFIXES = (
    "Module ",
    "Type ",
    "Constant ",
    "Record ",
    "Layout record ",
    "Packed layout record ",
    "Enum ",
    "Union ",
    "External ",
    "To ",
    "Test ",
)

LEGACY_TOP_LEVEL_RE = re.compile(
    rf"(?:module|import|type|constant|check|record|layout record|packed layout record|enum|union|extern|export)\b|.+\s+gives\s+.+:|.+\s+does:"
)


@dataclass(frozen=True)
class PunctuationSentence:
    text: str
    line: int


@dataclass(frozen=True)
class SourceComment:
    line: int
    kind: str
    text: str
    trailing: bool = False


@dataclass(frozen=True)
class SourceCommentInfo:
    source: str
    comments: tuple[SourceComment, ...]
    module_documentation: str | None
    declaration_docs: dict[int, str]


@dataclass(frozen=True)
class NormalizedSource:
    text: str
    module_documentation: str | None
    declaration_docs: dict[int, str]


def normalize_punctuation_source(source: str) -> str:
    return normalize_punctuation_source_with_docs(source).text


def normalize_punctuation_source_with_docs(source: str) -> NormalizedSource:
    comments = collect_source_comments(source)
    return _normalize_punctuation_source_from_comments(comments)


def _normalize_punctuation_source_from_comments(comments: SourceCommentInfo) -> NormalizedSource:
    source = comments.source
    _reject_legacy_surface_no_comments(source)
    if _uses_line_oriented_punctuation(source):
        text, docs = _normalize_line_punctuation_source(source, comments.declaration_docs)
        return NormalizedSource(text, comments.module_documentation, docs)
    sentences = _split_punctuation_sentences_no_comments(source)
    aliases = _import_aliases(sentences)
    output: list[str] = []
    docs_by_line: dict[int, str] = {}
    index = 0
    while index < len(sentences):
        sentence = sentences[index]
        text = _apply_import_aliases(sentence.text, aliases)
        if text.startswith("Module "):
            _attach_doc_for_output_line(docs_by_line, comments.declaration_docs, sentence.line, len(output) + 1)
            output.append(f"module {text[len('Module '):].strip()}")
            index += 1
            continue
        if text.startswith("Import "):
            output.append(_translate_import_sentence(text))
            index += 1
            continue
        if text.startswith("Record ") or text.startswith("Layout record ") or text.startswith("Packed layout record "):
            _attach_doc_for_output_line(docs_by_line, comments.declaration_docs, sentence.line, len(output) + 1)
            output.extend(_translate_record_sentence(text, sentence.line))
            index += 1
            continue
        if text.startswith("Enum "):
            _attach_doc_for_output_line(docs_by_line, comments.declaration_docs, sentence.line, len(output) + 1)
            output.extend(_translate_enum_sentence(text, sentence.line))
            index += 1
            continue
        if text.startswith("Union "):
            _attach_doc_for_output_line(docs_by_line, comments.declaration_docs, sentence.line, len(output) + 1)
            output.extend(_translate_union_sentence(text, sentence.line))
            index += 1
            continue
        if text.startswith("Type "):
            _attach_doc_for_output_line(docs_by_line, comments.declaration_docs, sentence.line, len(output) + 1)
            output.append("type " + text[len("Type "):].strip())
            index += 1
            continue
        if text.startswith("Constant "):
            _attach_doc_for_output_line(docs_by_line, comments.declaration_docs, sentence.line, len(output) + 1)
            output.extend(_translate_top_level_match_line("constant " + text[len("Constant "):].strip(), 0))
            index += 1
            continue
        if text.startswith("Check "):
            output.extend(_translate_top_level_match_line("check " + text[len("Check "):].strip(), 0))
            index += 1
            continue
        if text.startswith("External "):
            _attach_doc_for_output_line(docs_by_line, comments.declaration_docs, sentence.line, len(output) + 1)
            output.append(_translate_external_sentence(text, sentence.line))
            index += 1
            continue
        if text.startswith("To "):
            _attach_doc_for_output_line(docs_by_line, comments.declaration_docs, sentence.line, len(output) + 1)
            header = _translate_to_sentence(text, sentence.line)
            output.append(header)
            is_gives = " gives " in header
            index += 1
            body: list[PunctuationSentence] = []
            while index < len(sentences):
                candidate = sentences[index]
                candidate_text = _apply_import_aliases(candidate.text, aliases)
                if _is_phrase_boundary_sentence(candidate_text):
                    break
                body.append(PunctuationSentence(candidate_text, candidate.line))
                index += 1
                if is_gives and candidate_text.startswith("Give "):
                    break
            body_lines = _translate_body_sentences(body, is_gives=is_gives, indent=2)
            output.extend(body_lines)
            continue
        if text.startswith("Test "):
            _attach_doc_for_output_line(docs_by_line, comments.declaration_docs, sentence.line, len(output) + 1)
            output.append(_translate_test_sentence(text, sentence.line))
            index += 1
            body: list[PunctuationSentence] = []
            while index < len(sentences):
                candidate = sentences[index]
                candidate_text = _apply_import_aliases(candidate.text, aliases)
                if _is_phrase_boundary_sentence(candidate_text):
                    break
                body.append(PunctuationSentence(candidate_text, candidate.line))
                index += 1
            output.extend(_translate_test_body_sentences(body, indent=2))
            continue
        if text.startswith("Depend "):
            raise InscriptionError("Depend declarations are only valid in package manifests", sentence.line)
        raise InscriptionError(
            "expected top-level declaration sentence starting with Module, Import, Type, Constant, Check, Record, Layout record, Packed layout record, Enum, Union, External, To, or Test",
            sentence.line,
        )
    return NormalizedSource("\n".join(output) + ("\n" if output else ""), comments.module_documentation, docs_by_line)


def _attach_doc_for_output_line(
    docs_by_line: dict[int, str],
    declaration_docs: dict[int, str],
    source_line: int,
    output_line: int,
) -> None:
    documentation = declaration_docs.get(source_line)
    if documentation is not None:
        docs_by_line[output_line] = documentation


def collect_source_comments(source: str) -> SourceCommentInfo:
    stripped_lines: list[str] = []
    comments: list[SourceComment] = []
    doc_blocks: list[tuple[int, int, str]] = []
    module_doc_lines: list[str] = []
    module_doc_start: int | None = None
    pending_doc_lines: list[str] = []
    pending_doc_start: int | None = None
    pending_doc_end: int | None = None
    saw_non_comment_declaration = False

    for number, raw in enumerate(source.splitlines(), start=1):
        code, kind, text = _split_line_comment(raw, number)
        stripped_lines.append(code)
        if code.strip():
            if pending_doc_lines:
                doc_blocks.append((pending_doc_start or number, pending_doc_end or pending_doc_start or number, "\n".join(pending_doc_lines)))
                pending_doc_lines = []
                pending_doc_start = None
                pending_doc_end = None
            saw_non_comment_declaration = True
        if kind is None:
            if pending_doc_lines and not code.strip():
                raise InscriptionError("documentation comment must be followed by a declaration", number)
            continue
        trailing = bool(code.strip())
        comments.append(SourceComment(number, kind, text, trailing))
        if kind == "ordinary":
            if pending_doc_lines and not code.strip():
                raise InscriptionError("documentation comment must be followed by a declaration", number)
            continue
        if trailing:
            if kind == "module":
                raise InscriptionError("module documentation comments must appear before the first declaration", number)
            raise InscriptionError("documentation comments are only supported before top-level declarations", number)
        if kind == "module":
            if saw_non_comment_declaration:
                raise InscriptionError("module documentation comments must appear before the first declaration", number)
            if pending_doc_lines:
                raise InscriptionError("documentation comment must be followed by a declaration", pending_doc_start)
            if module_doc_start is None:
                module_doc_start = number
            module_doc_lines.append(text)
            continue
        if kind == "doc":
            if pending_doc_start is None:
                pending_doc_start = number
            pending_doc_end = number
            pending_doc_lines.append(text)
            continue

    if pending_doc_lines:
        doc_blocks.append((pending_doc_start or 1, pending_doc_end or pending_doc_start or 1, "\n".join(pending_doc_lines)))

    stripped_source = "\n".join(stripped_lines) + ("\n" if source.endswith("\n") else "")
    declaration_docs: dict[int, str] = {}
    if doc_blocks:
        sentences = _split_punctuation_sentences_no_comments(stripped_source)
        declaration_docs = _attach_documentation_blocks(doc_blocks, sentences, stripped_lines)
    module_documentation = "\n".join(module_doc_lines) if module_doc_lines else None
    return SourceCommentInfo(stripped_source, tuple(comments), module_documentation, declaration_docs)


def _split_line_comment(raw: str, line: int) -> tuple[str, str | None, str]:
    in_string = False
    escaped = False
    index = 0
    while index < len(raw):
        char = raw[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "/" and index + 1 < len(raw):
            nxt = raw[index + 1]
            if nxt == "*":
                raise InscriptionError("block comments are not supported; use //", line)
            if nxt == "/":
                marker_len = 2
                kind = "ordinary"
                if index + 2 < len(raw) and raw[index + 2] == "/":
                    marker_len = 3
                    kind = "doc"
                elif index + 2 < len(raw) and raw[index + 2] == "!":
                    marker_len = 3
                    kind = "module"
                text = raw[index + marker_len :]
                if text.startswith(" "):
                    text = text[1:]
                return raw[:index].rstrip(), kind, text.rstrip()
        index += 1
    return raw, None, ""


def _attach_documentation_blocks(
    doc_blocks: list[tuple[int, int, str]],
    sentences: list[PunctuationSentence],
    stripped_lines: list[str],
) -> dict[int, str]:
    declaration_docs: dict[int, str] = {}
    for start, end, text in doc_blocks:
        target = next((sentence for sentence in sentences if sentence.line > end), None)
        if target is None:
            raise InscriptionError("documentation comment must be followed by a declaration", start)
        for line_no in range(end + 1, target.line):
            if line_no - 1 < len(stripped_lines) and not stripped_lines[line_no - 1].strip():
                raise InscriptionError("documentation comment must be followed by a declaration", line_no)
        if not _is_top_level_sentence(target.text):
            raise InscriptionError("documentation comments are only supported before top-level declarations", start)
        if target.text.startswith("Import "):
            raise InscriptionError("documentation comments cannot attach to imports", start)
        if not target.text.startswith(DOCUMENTABLE_SENTENCE_PREFIXES):
            raise InscriptionError("documentation comments are only supported before documentable top-level declarations", start)
        declaration_docs[target.line] = text
    return declaration_docs


def scan_punctuation_module_header(source: str) -> tuple[str | None, tuple[ImportDecl, ...]] | None:
    comments = collect_source_comments(source)
    source = comments.source
    _reject_legacy_surface_no_comments(source)
    try:
        sentences = _split_punctuation_sentences_no_comments(source)
    except InscriptionError:
        raise
    module_name: str | None = None
    imports: list[ImportDecl] = []
    for sentence in sentences:
        text = sentence.text
        if text.startswith("Module "):
            if module_name is not None:
                raise InscriptionError("program can declare only one module", sentence.line)
            module_name = text[len("Module ") :].strip()
            continue
        if text.startswith("Import "):
            module_text = text[len("Import ") :].strip()
            if " as " in module_text:
                module_text = module_text.split(" as ", 1)[0].strip()
            imports.append(ImportDecl(module_text, sentence.line))
            continue
        if _is_top_level_sentence(text):
            break
    return module_name, tuple(imports)




def _uses_line_oriented_punctuation(source: str) -> bool:
    for raw in source.splitlines():
        if raw.strip() == ".":
            return True
    return False


def _normalize_line_punctuation_source(source: str, declaration_docs: dict[int, str] | None = None) -> tuple[str, dict[int, str]]:
    declaration_docs = declaration_docs or {}
    docs_by_line: dict[int, str] = {}
    aliases: dict[str, str] = {}
    raw_lines = source.splitlines()
    for number, raw in enumerate(raw_lines, start=1):
        text = raw.strip()
        if text.startswith("Import ") and " as " in text:
            cleaned = text[:-1] if text.endswith(".") else text
            module_text = cleaned[len("Import ") :].strip()
            module_name, alias = module_text.split(" as ", 1)
            aliases[alias.strip()] = module_name.strip()
    lines: list[str] = []
    for number, raw in enumerate(raw_lines, start=1):
        if "\t" in raw:
            raise InscriptionError("tabs are not valid indentation", number)
        indent = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()
        if not text or text == ".":
            continue
        if text.endswith("."):
            text = text[:-1].strip()
        text = _apply_import_aliases(text, aliases)
        prefix = " " * indent
        if indent == 0 and text.startswith("Module "):
            _attach_doc_for_output_line(docs_by_line, declaration_docs, number, len(lines) + 1)
            lines.append(f"module {text[len('Module '):].strip()}")
            continue
        if indent == 0 and text.startswith("Import "):
            lines.append(_translate_import_sentence(text))
            continue
        if indent == 0 and (text.startswith("Record ") or text.startswith("Layout record ") or text.startswith("Packed layout record ")):
            _attach_doc_for_output_line(docs_by_line, declaration_docs, number, len(lines) + 1)
            lines.extend(_translate_record_sentence(text, number))
            continue
        if indent == 0 and text.startswith("Enum "):
            _attach_doc_for_output_line(docs_by_line, declaration_docs, number, len(lines) + 1)
            lines.extend(_translate_enum_sentence(text, number))
            continue
        if indent == 0 and text.startswith("Union "):
            _attach_doc_for_output_line(docs_by_line, declaration_docs, number, len(lines) + 1)
            lines.extend(_translate_union_sentence(text, number))
            continue
        if indent == 0 and text.startswith("Type "):
            _attach_doc_for_output_line(docs_by_line, declaration_docs, number, len(lines) + 1)
            lines.append("type " + text[len("Type "):].strip())
            continue
        if indent == 0 and text.startswith("Constant "):
            _attach_doc_for_output_line(docs_by_line, declaration_docs, number, len(lines) + 1)
            lines.extend(_translate_top_level_match_line("constant " + text[len("Constant "):].strip(), 0))
            continue
        if indent == 0 and text.startswith("Check "):
            _attach_doc_for_output_line(docs_by_line, declaration_docs, number, len(lines) + 1)
            lines.extend(_translate_top_level_match_line("check " + text[len("Check "):].strip(), 0))
            continue
        if indent == 0 and text.startswith("External "):
            _attach_doc_for_output_line(docs_by_line, declaration_docs, number, len(lines) + 1)
            lines.append(_translate_external_sentence(text, number))
            continue
        if indent == 0 and text.startswith("To "):
            _attach_doc_for_output_line(docs_by_line, declaration_docs, number, len(lines) + 1)
            lines.append(_translate_to_sentence(text, number))
            continue
        if indent == 0 and text.startswith("Test "):
            _attach_doc_for_output_line(docs_by_line, declaration_docs, number, len(lines) + 1)
            lines.append(_translate_test_sentence(text, number))
            continue
        if text.startswith("Expect "):
            lines.extend(_translate_expect_sentence(text, number, indent))
            continue
        if text.startswith("Give "):
            lines.extend(_translate_give_sentence(text, number, indent))
            continue
        if text.startswith("Let "):
            lines.extend(_translate_match_expression_line("let " + text[len("Let ") :].strip(), indent))
            continue
        if text.startswith("Require "):
            lines.extend(_translate_match_expression_line("require " + text[len("Require ") :].strip(), indent))
            continue
        if text.startswith("Check "):
            lines.extend(_translate_match_expression_line("check " + text[len("Check ") :].strip(), indent))
            continue
        if text.startswith("Write "):
            lines.append(prefix + "write " + text[len("Write ") :].strip())
            continue
        if text.startswith("When "):
            lines.append(prefix + "if " + text[len("When ") :].strip())
            continue
        if text.startswith("Otherwise"):
            rest = text[len("Otherwise") :].strip()
            if not rest or rest == ":":
                lines.append(prefix + "otherwise:")
            elif rest.startswith(":"):
                lines.append(prefix + "otherwise:")
                lines.extend(_translate_clause_body(rest[1:].strip(), number, indent + 2))
            elif rest.startswith(","):
                lines.extend(_translate_clause_body(rest[1:].strip(), number, indent))
            else:
                lines.append(prefix + "otherwise " + rest)
            continue
        if text.startswith("While "):
            lines.append(prefix + "while " + text[len("While ") :].strip())
            continue
        if text.startswith("For "):
            lines.append(prefix + "for " + text[len("For ") :].strip())
            continue
        if text.startswith("Match "):
            lines.append(prefix + "match " + text[len("Match ") :].strip())
            continue
        lines.extend(_translate_match_expression_line(prefix + text, 0))
    return "\n".join(lines) + ("\n" if lines else ""), docs_by_line

def _reject_legacy_surface(source: str) -> None:
    _reject_legacy_surface_no_comments(collect_source_comments(source).source)


def _reject_legacy_surface_no_comments(source: str) -> None:
    for number, raw in enumerate(source.splitlines(), start=1):
        text = raw.strip()
        if not text:
            continue
        if re.fullmatch(r"[a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*|\s+[a-z][a-z0-9_]*:\s*[^:]+)*\s+gives\s+.+:", text):
            raise InscriptionError("legacy phrase syntax is not supported; use `To main, giving i32.`", number)
        if re.fullmatch(r"(?:record|layout record|packed layout record)\s+[A-Za-z][A-Za-z0-9_]*:", text):
            raise InscriptionError("legacy record syntax is not supported; use `Record Point has ... .`", number)
        if re.fullmatch(r"(?:if|while|for|match)\b.*:", text):
            raise InscriptionError("legacy block syntax is not supported", number)
        if re.fullmatch(r"(?:module|import|type|constant|check|enum|union|extern|export)\b.*", text):
            raise InscriptionError("legacy syntax is not supported; use v0.34 punctuation sentences", number)


def _split_punctuation_sentences(source: str) -> list[PunctuationSentence]:
    return _split_punctuation_sentences_no_comments(collect_source_comments(source).source)


def _split_punctuation_sentences_no_comments(source: str) -> list[PunctuationSentence]:
    sentences: list[PunctuationSentence] = []
    start = 0
    start_line = 1
    current_sentence_line: int | None = None
    line = 1
    in_string = False
    escaped = False
    for index, char in enumerate(source):
        if char == "\n":
            line += 1
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            if current_sentence_line is None:
                current_sentence_line = line
            in_string = True
            continue
        if current_sentence_line is None and not char.isspace():
            current_sentence_line = line
        if char != ".":
            continue
        prev = source[index - 1] if index > 0 else ""
        nxt = source[index + 1] if index + 1 < len(source) else ""
        if prev.isdigit() and nxt.isdigit():
            continue
        if nxt and not nxt.isspace():
            continue
        text = source[start:index].strip()
        if text:
            sentences.append(PunctuationSentence(_collapse_sentence_whitespace(text), current_sentence_line or start_line))
        start = index + 1
        start_line = line
        current_sentence_line = None
    if in_string:
        raise InscriptionError("unterminated string literal", line)
    if source[start:].strip():
        raise InscriptionError("missing period at end of sentence", current_sentence_line or start_line)
    return sentences


def _collapse_sentence_whitespace(text: str) -> str:
    pieces: list[str] = []
    current: list[str] = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            current.append(char)
            in_string = True
            continue
        if char.isspace():
            if current and current[-1] != " ":
                current.append(" ")
            continue
        current.append(char)
    return "".join(current).strip()


def _is_top_level_sentence(text: str) -> bool:
    return text.startswith(TOP_LEVEL_SENTENCE_PREFIXES)


def _is_phrase_boundary_sentence(text: str) -> bool:
    return text.startswith(
        (
            "Module ",
            "Import ",
            "Type ",
            "Constant ",
            "Record ",
            "Layout record ",
            "Packed layout record ",
            "Enum ",
            "Union ",
            "External ",
            "To ",
            "Test ",
        )
    )


def _import_aliases(sentences: list[PunctuationSentence]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for sentence in sentences:
        text = sentence.text
        if not text.startswith("Import "):
            continue
        module_text = text[len("Import ") :].strip()
        if " as " not in module_text:
            continue
        module_name, alias = module_text.split(" as ", 1)
        alias = alias.strip()
        if not re.fullmatch(r"[A-Z][A-Za-z0-9_]*", alias):
            raise InscriptionError(f"invalid import alias '{alias}'", sentence.line)
        aliases[alias] = module_name.strip()
    return aliases


def _apply_import_aliases(text: str, aliases: dict[str, str]) -> str:
    if not aliases:
        return text
    out = text
    for alias, module_name in aliases.items():
        out = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(alias)}\.", f"{module_name}.", out)
    return out


def _translate_import_sentence(text: str) -> str:
    module_text = text[len("Import ") :].strip()
    if " as " in module_text:
        module_text = module_text.split(" as ", 1)[0].strip()
    return f"import {module_text}"


def _split_top_level(text: str, separator: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == separator and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
        index += 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def _split_commas(text: str) -> list[str]:
    return _split_top_level(text, ",")


def _split_semicolons(text: str) -> list[str]:
    return _split_top_level(text, ";")


def _translate_record_sentence(text: str, line: int) -> list[str]:
    match = re.fullmatch(r"(Record|Layout record|Packed layout record) ([A-Za-z][A-Za-z0-9_]*) has(?: (.*))?", text)
    if match is None:
        raise InscriptionError("malformed record declaration", line)
    kind = {"Record": "record", "Layout record": "layout record", "Packed layout record": "packed layout record"}[match.group(1)]
    lines = [f"{kind} {match.group(2)}:"]
    fields = match.group(3)
    if fields:
        lines.extend(f"  {field}" for field in _split_semicolons(fields))
    return lines


def _translate_enum_sentence(text: str, line: int) -> list[str]:
    match = re.fullmatch(r"Enum ([A-Za-z][A-Za-z0-9_]*) backed by (.+?) has(?: (.*))?", text)
    if match is None:
        raise InscriptionError("malformed enum declaration", line)
    lines = [f"enum {match.group(1)}: {match.group(2).strip()}:"]
    cases = match.group(3)
    if cases:
        lines.extend(f"  {case}" for case in _split_semicolons(cases))
    return lines


def _translate_union_sentence(text: str, line: int) -> list[str]:
    match = re.fullmatch(r"Union ([A-Za-z][A-Za-z0-9_]*) has(?: (.*))?", text)
    if match is None:
        raise InscriptionError("malformed union declaration", line)
    lines = [f"union {match.group(1)}:"]
    variants = match.group(2)
    if variants:
        lines.extend(f"  {variant}" for variant in _split_semicolons(variants))
    return lines


def _translate_external_sentence(text: str, line: int) -> str:
    parts = _split_commas(text[len("External ") :].strip())
    phrase = parts[0]
    giving: str | None = None
    symbol: str | None = None
    for part in parts[1:]:
        if part.startswith("giving "):
            giving = part[len("giving ") :].strip()
        elif part.startswith("as "):
            symbol = part[len("as ") :].strip()
        else:
            raise InscriptionError("malformed external phrase declaration", line)
    if symbol is None:
        raise InscriptionError("external phrase declaration requires `as symbol`", line)
    if giving is None:
        return f"extern {phrase} does as {symbol}"
    return f"extern {phrase} gives {giving} as {symbol}"


def _translate_to_sentence(text: str, line: int) -> str:
    parts = _split_commas(text[len("To ") :].strip())
    phrase = parts[0]
    giving: str | None = None
    exported: str | None = None
    for part in parts[1:]:
        if part.startswith("giving "):
            giving = part[len("giving ") :].strip()
        elif part.startswith("exported as "):
            exported = part[len("exported as ") :].strip()
        else:
            raise InscriptionError("malformed phrase declaration", line)
    if exported is not None:
        if giving is None:
            return f"export {phrase} does as {exported}:"
        return f"export {phrase} gives {giving} as {exported}:"
    if giving is None:
        return f"{phrase} does:"
    return f"{phrase} gives {giving}:"


def _translate_test_sentence(text: str, line: int) -> str:
    name = text[len("Test ") :].strip()
    if not name:
        raise InscriptionError("malformed test declaration", line)
    for word in name.split():
        if not NAME_RE.fullmatch(word):
            raise InscriptionError(f"invalid test word '{word}'", line)
    return f"test {name}:"


def _translate_expect_sentence(text: str, line: int, indent: int) -> list[str]:
    expr = text[len("Expect ") :].strip()
    if not expr:
        raise InscriptionError("malformed expect", line)
    return _translate_match_expression_line("expect " + expr, indent)


def _translate_test_body_sentences(sentences: list[PunctuationSentence], *, indent: int) -> list[str]:
    lines: list[str] = []
    index = 0
    while index < len(sentences):
        sentence = sentences[index]
        text = sentence.text
        if text.startswith("Otherwise"):
            raise InscriptionError("Otherwise cannot appear without a preceding When", sentence.line)
        if text.startswith("When "):
            if index + 1 >= len(sentences) or not sentences[index + 1].text.startswith("Otherwise"):
                raise InscriptionError("When requires an immediately following Otherwise", sentence.line)
            lines.extend(_translate_when_pair(text, sentences[index + 1].text, sentence.line, indent))
            index += 2
            continue
        if text.startswith("Expect "):
            lines.extend(_translate_expect_sentence(text, sentence.line, indent))
            index += 1
            continue
        if text.startswith("Give "):
            raise InscriptionError("Give is not valid inside a test", sentence.line)
        lines.extend(_translate_step_sentence(text, sentence.line, indent))
        index += 1
    return lines


def _translate_body_sentences(sentences: list[PunctuationSentence], *, is_gives: bool, indent: int) -> list[str]:
    lines: list[str] = []
    index = 0
    saw_give = False
    while index < len(sentences):
        sentence = sentences[index]
        text = sentence.text
        if saw_give:
            raise InscriptionError("Give must be the final phrase body sentence", sentence.line)
        if text.startswith("Otherwise"):
            raise InscriptionError("Otherwise cannot appear without a preceding When", sentence.line)
        if text.startswith("When "):
            if index + 1 >= len(sentences) or not sentences[index + 1].text.startswith("Otherwise"):
                raise InscriptionError("When requires an immediately following Otherwise", sentence.line)
            lines.extend(_translate_when_pair(text, sentences[index + 1].text, sentence.line, indent))
            index += 2
            continue
        if text.startswith("Give "):
            if not is_gives:
                raise InscriptionError("Give is valid only inside returning phrases", sentence.line)
            lines.extend(_translate_give_sentence(text, sentence.line, indent))
            saw_give = True
            index += 1
            continue
        lines.extend(_translate_step_sentence(text, sentence.line, indent))
        index += 1
    if is_gives and not saw_give:
        line = sentences[-1].line if sentences else None
        raise InscriptionError("gives phrase body must end with a Give sentence", line)
    return lines


def _translate_top_level_match_line(line: str, indent: int) -> list[str]:
    return _translate_match_expression_line(line, indent)


def _translate_give_sentence(text: str, line: int, indent: int) -> list[str]:
    expr = text[len("Give ") :].strip()
    guarded = _split_guarded_value_clauses(expr)
    if guarded is not None:
        return [" " * indent + clause for clause in guarded]
    return _translate_match_expression_line(expr, indent)


def _split_guarded_value_clauses(expr: str) -> list[str] | None:
    if expr.startswith("match ") or ";" not in expr:
        return None
    clauses = _split_semicolons(expr)
    if len(clauses) < 2:
        return None
    if not clauses[-1].startswith("otherwise "):
        return None
    if not all(" when " in clause for clause in clauses[:-1]):
        return None
    return clauses


def _translate_step_sentence(text: str, line: int, indent: int) -> list[str]:
    if _starts_then_marker(text):
        raise InscriptionError("then may only resume a parent clause after nested control", line)
    if text.startswith("comptime "):
        raise InscriptionError("comptime may only be used as an expression", line)
    if text.startswith("Let "):
        if _contains_then_marker(text):
            raise InscriptionError("then may only resume a parent clause after nested control", line)
        return _translate_match_expression_line("let " + text[len("Let ") :].strip(), indent)
    if text.startswith("Require "):
        if _contains_then_marker(text):
            raise InscriptionError("then may only resume a parent clause after nested control", line)
        return _translate_match_expression_line("require " + text[len("Require ") :].strip(), indent)
    if text.startswith("Expect "):
        if _contains_then_marker(text):
            raise InscriptionError("then may only resume a parent clause after nested control", line)
        return _translate_expect_sentence(text, line, indent)
    if text.startswith("Check "):
        if _contains_then_marker(text):
            raise InscriptionError("then may only resume a parent clause after nested control", line)
        return _translate_match_expression_line("check " + text[len("Check ") :].strip(), indent)
    if text.startswith("Write "):
        if _contains_then_marker(text):
            raise InscriptionError("then may only resume a parent clause after nested control", line)
        return [" " * indent + "write " + text[len("Write ") :].strip()]
    if text.startswith("While "):
        return _translate_loop_sentence("while", text[len("While ") :].strip(), line, indent)
    if text.startswith("For "):
        return _translate_loop_sentence("for", text[len("For ") :].strip(), line, indent)
    if text.startswith("Match "):
        return _translate_match_step_sentence(text, line, indent)
    if _contains_then_marker(text):
        raise InscriptionError("then may only resume a parent clause after nested control", line)
    if ";" in text:
        raise InscriptionError("semicolon is only valid inside a colon-introduced clause list", line)
    return _translate_match_expression_line(text, indent)


def _translate_when_pair(when_text: str, otherwise_text: str, line: int, indent: int) -> list[str]:
    condition, then_body = _split_control_head_body(when_text[len("When ") :].strip(), line, "When")
    else_rest = otherwise_text[len("Otherwise") :].strip()
    if not else_rest:
        raise InscriptionError("Otherwise requires a branch body", line)
    if else_rest.startswith(":"):
        else_body = else_rest[1:].strip()
    elif else_rest.startswith(","):
        else_body = else_rest[1:].strip()
    else:
        raise InscriptionError("Otherwise must use `Otherwise, step` or `Otherwise: steps`", line)
    lines = [" " * indent + f"if {condition}:"]
    lines.extend(_translate_clause_body(then_body, line, indent + 2))
    lines.append(" " * indent + "otherwise:")
    lines.extend(_translate_clause_body(else_body, line, indent + 2))
    return lines


def _translate_loop_sentence(kind: str, rest: str, line: int, indent: int) -> list[str]:
    head, body = _split_control_head_body(rest, line, kind.capitalize())
    lines = [" " * indent + f"{kind} {head}:"]
    lines.extend(_translate_clause_body(body, line, indent + 2))
    return lines


def _split_control_head_body(rest: str, line: int, keyword: str) -> tuple[str, str]:
    colon = _find_top_level_char(rest, ":")
    comma = _find_top_level_char(rest, ",")
    if colon == -1 and comma == -1:
        raise InscriptionError(f"{keyword} requires a comma or colon body", line)
    if colon != -1 and (comma == -1 or colon < comma):
        head = rest[:colon].strip()
        body = rest[colon + 1 :].strip()
    else:
        head = rest[:comma].strip()
        body = rest[comma + 1 :].strip()
    if not head or not body:
        raise InscriptionError(f"malformed {keyword} sentence", line)
    return head, body


def _find_top_level_char(text: str, target: str) -> int:
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == target and depth == 0:
            return index
    return -1


def _find_top_level_keyword(text: str, keyword: str) -> int:
    depth = 0
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "(":
            depth += 1
            index += 1
            continue
        if char == ")":
            depth -= 1
            index += 1
            continue
        if depth == 0 and text.startswith(keyword, index):
            before = text[index - 1] if index > 0 else " "
            after_index = index + len(keyword)
            after = text[after_index] if after_index < len(text) else " "
            if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                return index
        index += 1
    return -1


def _translate_clause_body(body: str, line: int, indent: int) -> list[str]:
    clauses = _split_step_clauses(body, line)
    if not clauses:
        raise InscriptionError("clause list must contain at least one step", line)
    lines: list[str] = []
    index = 0
    while index < len(clauses):
        clause = clauses[index]
        if _starts_then_marker(clause):
            raise InscriptionError("then may only resume a parent clause after nested control", line)
        if clause.startswith("When "):
            if index + 1 >= len(clauses) or not clauses[index + 1].startswith("Otherwise"):
                raise InscriptionError("When requires an immediately following Otherwise", line)
            lines.extend(_translate_when_pair(clause, clauses[index + 1], line, indent))
            index += 2
            continue
        lines.extend(_translate_step_sentence(clause, line, indent))
        index += 1
    return lines


def _is_nested_control_clause(text: str) -> bool:
    return text.startswith(("While ", "For ", "Match "))


def _starts_then_marker(text: str) -> bool:
    return text == "then" or text.startswith("then ")


def _contains_then_marker(text: str) -> bool:
    parts = _split_top_level(text, ";")
    return any(_starts_then_marker(part.strip()) for part in parts[1:])


def _strip_then_marker(text: str, line: int) -> str:
    if text == "then":
        raise InscriptionError("then must be followed by a parent clause", line)
    if not text.startswith("then "):
        return text
    rest = text[len("then ") :].strip()
    if not rest:
        raise InscriptionError("then must be followed by a parent clause", line)
    return rest


def _split_step_clauses(body: str, line: int) -> list[str]:
    clauses: list[str] = []
    rest = body.strip()
    while rest:
        if _starts_then_marker(rest):
            raise InscriptionError("then may only resume a parent clause after nested control", line)
        if _is_nested_control_clause(rest):
            control_clause, continuation = _split_nested_control_continuation(rest, line)
            clauses.append(control_clause)
            if continuation is None:
                break
            rest = continuation.strip()
            continue
        parts = _split_top_level(rest, ";")
        if len(parts) <= 1:
            clauses.append(rest)
            break
        first = parts[0].strip()
        if first:
            clauses.append(first)
        semicolon = _find_top_level_char(rest, ";")
        if semicolon == -1:
            break
        rest = rest[semicolon + 1 :].strip()
        if _starts_then_marker(rest):
            raise InscriptionError("then may only resume a parent clause after nested control", line)
    return [clause for clause in clauses if clause]


def _nested_control_start_count(text: str) -> int:
    return len(re.findall(r"(?:^|:\s+)(?:While|For|Match)\b", text))


def _split_nested_control_continuation(text: str, line: int) -> tuple[str, str | None]:
    parts = _split_top_level(text, ";")
    if len(parts) <= 1:
        return text.strip(), None
    depth = max(1, _nested_control_start_count(parts[0]))
    for index, raw_part in enumerate(parts[1:], start=1):
        part = raw_part.strip()
        if _starts_then_marker(part):
            resumed = _strip_then_marker(part, line)
            depth -= 1
            if depth == 0:
                control = "; ".join(piece.strip() for piece in parts[:index] if piece.strip()).strip()
                continuation_parts = [resumed, *(piece.strip() for piece in parts[index + 1 :] if piece.strip())]
                continuation = "; ".join(piece for piece in continuation_parts if piece).strip()
                return control, continuation
            depth += _nested_control_start_count(resumed)
            continue
        depth += _nested_control_start_count(part)
    return text.strip(), None


def _translate_match_expression_line(text: str, indent: int) -> list[str]:
    marker = "match "
    match_index = text.find(marker)
    if match_index == -1 or not text[match_index:].startswith("match ") or ":" not in text[match_index:]:
        return [" " * indent + text]
    prefix = text[:match_index]
    match_text = text[match_index:]
    colon = _find_top_level_char(match_text, ":")
    if colon == -1:
        return [" " * indent + text]
    header = prefix + match_text[:colon]
    arms_text = match_text[colon + 1 :].strip()
    lines = [" " * indent + header.strip() + ":"]
    for arm in _split_semicolons(arms_text):
        lines.append(" " * (indent + 2) + arm)
    return lines


def _translate_match_step_sentence(text: str, line: int, indent: int) -> list[str]:
    rest = text[len("Match ") :].strip()
    colon = _find_top_level_char(rest, ":")
    if colon == -1:
        raise InscriptionError("malformed match block", line)
    scrutinee = rest[:colon].strip()
    arms_text = rest[colon + 1 :].strip()
    lines = [" " * indent + f"match {scrutinee}:"]
    for arm in _split_match_step_arms(arms_text):
        arm_colon = _find_top_level_char(arm, ":")
        if arm_colon == -1:
            raise InscriptionError("match block arms must use `pattern: steps`", line)
        pattern = arm[:arm_colon].strip()
        body = arm[arm_colon + 1 :].strip()
        lines.append(" " * (indent + 2) + f"{pattern}:")
        lines.extend(_translate_clause_body(body, line, indent + 4))
    return lines


def _split_match_step_arms(arms_text: str) -> list[str]:
    arms: list[str] = []
    start = 0
    depth = 0
    in_string = False
    escaped = False
    index = 0
    while index < len(arms_text):
        char = arms_text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == ";" and depth == 0:
            remainder = arms_text[index + 1 :].lstrip()
            if _looks_like_match_arm_start(remainder):
                arm = arms_text[start:index].strip()
                if arm:
                    arms.append(arm)
                start = index + 1
        index += 1
    final = arms_text[start:].strip()
    if final:
        arms.append(final)
    return arms


def _looks_like_match_arm_start(text: str) -> bool:
    colon = _find_top_level_char(text, ":")
    if colon == -1:
        return False
    prefix = text[:colon].strip()
    if not prefix:
        return False
    first = prefix.split()[0]
    if first in {"otherwise", "anything", "true", "false", "byte"}:
        return True
    if re.fullmatch(r"-?\d+", first):
        return True
    return re.match(r"[A-Z][A-Za-z0-9_.]*", first) is not None


def _split_top_level_keyword(text: str, keyword: str) -> list[str]:
    parts: list[str] = []
    start = 0
    index = 0
    depth = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "(":
            depth += 1
            index += 1
            continue
        if char == ")":
            depth -= 1
            index += 1
            continue
        if depth == 0 and text.startswith(keyword, index):
            before = text[index - 1] if index > 0 else " "
            after_index = index + len(keyword)
            after = text[after_index] if after_index < len(text) else " "
            if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                parts.append(text[start:index].strip())
                start = after_index
                index = after_index
                continue
        index += 1
    if not parts:
        return [text.strip()]
    parts.append(text[start:].strip())
    return parts


class Parser:
    def __init__(
        self,
        source: str,
        *,
        external_phrases: tuple[PhraseTemplate, ...] = (),
        symbol_prefix: str | None = None,
    ):
        normalized = normalize_punctuation_source_with_docs(source)
        self.lines = self._preprocess(normalized.text)
        self.module_documentation = normalized.module_documentation
        self.declaration_docs = normalized.declaration_docs
        self.symbol_prefix = symbol_prefix
        self.external_phrases = external_phrases
        self.local_phrases: tuple[PhraseTemplate, ...] = ()
        self.phrases: tuple[PhraseTemplate, ...] = ()
        self.local_phrases = self._collect_phrase_templates()
        self.phrases = tuple(sorted((*self.local_phrases, *self.external_phrases), key=lambda template: len(template.parts), reverse=True))

    def _preprocess(self, source: str) -> list[Line]:
        lines: list[Line] = []
        for number, raw in enumerate(source.splitlines(), start=1):
            if "\t" in raw:
                raise InscriptionError("tabs are not valid indentation", number)
            indent = len(raw) - len(raw.lstrip(" "))
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped.endswith(":"):
                body = stripped[:-1].strip()
                is_header = True
            else:
                body = stripped
                is_header = False
            if not body:
                raise InscriptionError("empty line is not valid syntax", number)
            lines.append(Line(number, body, is_header, indent))
        return lines

    def _collect_phrase_templates(self) -> tuple[PhraseTemplate, ...]:
        templates: list[PhraseTemplate] = []
        for line in self.lines:
            if line.indent == 0 and line.text.startswith("extern "):
                template, _return_type, _external_symbol = self._parse_extern_decl(line)
                templates.append(template)
                continue
            if line.indent == 0 and line.text.startswith("export "):
                template, _return_type, _external_symbol = self._parse_export_header(line)
                templates.append(template)
                continue
            if not self._looks_like_phrase_header(line):
                continue
            template, _return_type = self._parse_phrase_header(line)
            templates.append(template)
        return tuple(sorted(templates, key=lambda template: len(template.parts), reverse=True))

    def parse_program(self) -> Program:
        records: list[RecordDecl] = []
        enums: list[EnumDecl] = []
        unions: list[UnionDecl] = []
        type_aliases: list[TypeAliasDecl] = []
        constants: list[ConstantDecl] = []
        checks: list[CheckStmt] = []
        functions: list[Function] = []
        tests: list[TestDecl] = []
        imports: list[ImportDecl] = []
        module_name: str | None = None
        module_declaration_documentation: str | None = None
        index = 0
        while index < len(self.lines):
            line = self.lines[index]
            if line.indent == 0 and line.text.startswith("module "):
                if line.is_header:
                    raise InscriptionError("malformed module declaration", line.number)
                if module_name is not None:
                    raise InscriptionError("program can declare only one module", line.number)
                module_name = self._module_name(line.text[len("module ") :].strip(), line.number)
                module_declaration_documentation = self._doc_for(line)
                index += 1
                continue
            if line.indent == 0 and line.text.startswith("import "):
                if line.is_header:
                    raise InscriptionError("malformed import declaration", line.number)
                imports.append(ImportDecl(self._module_name(line.text[len("import ") :].strip(), line.number), line.number))
                index += 1
                continue
            if self._looks_like_record_header(line):
                record, index = self._parse_record_decl(index)
                records.append(record)
                continue
            if self._looks_like_enum_header(line):
                enum, index = self._parse_enum_decl(index)
                enums.append(enum)
                continue
            if self._looks_like_union_header(line):
                union, index = self._parse_union_decl(index)
                unions.append(union)
                continue
            if line.indent == 0 and line.text.startswith("type "):
                type_aliases.append(self._parse_type_alias_decl(line))
                index += 1
                continue
            if line.text.startswith("constant "):
                if line.is_header and re.fullmatch(rf"constant [a-z][a-z0-9_]*:\s*{TYPE_REF_PATTERN} be match .+", line.text):
                    constant, index = self._parse_constant_match_decl(index)
                    constants.append(constant)
                else:
                    constants.append(self._parse_constant_decl(line))
                    index += 1
                continue
            if line.text.startswith("check "):
                if line.is_header and line.text.startswith("check match "):
                    check, index = self._parse_check_match_stmt(index)
                    checks.append(check)
                else:
                    checks.append(self._parse_check_stmt(line))
                    index += 1
                continue
            if line.text.startswith("extern "):
                template, return_type, external_symbol = self._parse_extern_decl(line)
                functions.append(
                    Function(
                        template.symbol,
                        template.params,
                        return_type,
                        (),
                        line.number,
                        template.display_name,
                        external_symbol,
                        "extern",
                        self._doc_for(line),
                    )
                )
                index += 1
                continue
            if line.text.startswith("export "):
                template, return_type, external_symbol = self._parse_export_header(line)
                body, index = self._parse_phrase_body(index + 1, template, line.number)
                functions.append(
                    Function(
                        template.symbol,
                        template.params,
                        return_type,
                        tuple(body),
                        line.number,
                        template.display_name,
                        external_symbol,
                        "export",
                        self._doc_for(line),
                    )
                )
                continue
            if line.text.startswith("require "):
                raise InscriptionError("require may only appear inside phrase bodies", line.number)
            if line.text.startswith("expect "):
                raise InscriptionError("Expect is only valid inside tests", line.number)
            if line.indent == 0 and line.text.startswith("test "):
                test, index = self._parse_test_decl(index)
                if any(existing.display_name == test.display_name for existing in tests):
                    raise InscriptionError(f"test `{test.display_name}` is already defined", test.line)
                tests.append(test)
                continue
            if not self._looks_like_phrase_header(line):
                raise InscriptionError("expected phrase definition, test declaration, record declaration, enum declaration, union declaration, type alias, constant declaration, check, extern, export, module, or import", line.number)
            template, return_type = self._parse_phrase_header(line)
            body, index = self._parse_phrase_body(index + 1, template, line.number)
            functions.append(
                Function(
                    template.symbol,
                    template.params,
                    return_type,
                    tuple(body),
                    line.number,
                    template.display_name,
                    documentation=self._doc_for(line),
                )
            )
        seen_imports: set[str] = set()
        for imported in imports:
            if imported.module in seen_imports:
                raise InscriptionError(f"module {imported.module} is already imported", imported.line)
            seen_imports.add(imported.module)
        return Program(
            tuple(records),
            tuple(enums),
            tuple(unions),
            tuple(type_aliases),
            tuple(constants),
            tuple(checks),
            tuple(functions),
            module_name,
            tuple(imports),
            self.module_documentation or module_declaration_documentation,
            tuple(tests),
        )

    def _doc_for(self, line: Line) -> str | None:
        return self.declaration_docs.get(line.number)

    def _looks_like_record_header(self, line: Line) -> bool:
        return (
            line.is_header
            and re.fullmatch(r"(?:record|layout record|packed layout record) [A-Za-z][A-Za-z0-9_]*", line.text)
            is not None
        )

    def _looks_like_enum_header(self, line: Line) -> bool:
        return line.is_header and re.fullmatch(rf"enum [A-Za-z][A-Za-z0-9_]*:\s*{TYPE_PATTERN}", line.text) is not None

    def _looks_like_union_header(self, line: Line) -> bool:
        return line.is_header and re.fullmatch(r"union [A-Za-z][A-Za-z0-9_]*", line.text) is not None

    def _parse_test_decl(self, index: int) -> tuple[TestDecl, int]:
        line = self.lines[index]
        match = re.fullmatch(r"test (.+)", line.text)
        if not line.is_header or match is None:
            raise InscriptionError("malformed test declaration", line.number)
        display_name = match.group(1).strip()
        if not display_name:
            raise InscriptionError("malformed test declaration", line.number)
        words = display_name.split()
        for word in words:
            if not NAME_RE.fullmatch(word):
                raise InscriptionError(f"invalid test word '{word}'", line.number)
        body, next_index = self._parse_test_body(index + 1, line.number, display_name)
        return TestDecl("_".join(words), display_name, tuple(body), line.number, self._doc_for(line)), next_index

    def _looks_like_top_level_item(self, line: Line) -> bool:
        return (
            self._looks_like_phrase_header(line)
            or self._looks_like_record_header(line)
            or self._looks_like_enum_header(line)
            or self._looks_like_union_header(line)
            or (line.indent == 0 and (line.text.startswith("constant ") or line.text.startswith("check ") or line.text.startswith("extern ") or line.text.startswith("export ") or line.text.startswith("module ") or line.text.startswith("import ") or line.text.startswith("require ") or line.text.startswith("expect ") or line.text.startswith("test ") or line.text.startswith("enum ") or line.text.startswith("union ") or line.text.startswith("type ")))
        )

    def _parse_record_decl(self, index: int) -> tuple[RecordDecl, int]:
        line = self.lines[index]
        match = re.fullmatch(r"(record|layout record|packed layout record) ([A-Za-z][A-Za-z0-9_]*)", line.text)
        if not line.is_header or match is None:
            raise InscriptionError("malformed record declaration", line.number)
        layout_kind = {"record": "value", "layout record": "natural", "packed layout record": "packed"}[match.group(1)]
        name = self._record_name(match.group(2), line.number)
        fields: list[RecordFieldDecl] = []
        field_index = index + 1
        while field_index < len(self.lines):
            current = self.lines[field_index]
            if current.indent <= line.indent:
                break
            field_match = re.fullmatch(rf"([a-z][a-z0-9_]*):\s*({TYPE_PATTERN})", current.text)
            if current.is_header or field_match is None:
                raise InscriptionError("malformed record field declaration", current.number)
            fields.append(
                RecordFieldDecl(
                    self._field_name(field_match.group(1), current.number),
                    self._value_type(field_match.group(2), current.number),
                    current.number,
                )
            )
            field_index += 1
        if not fields:
            prefix = "record" if layout_kind == "value" else "layout record"
            raise InscriptionError(f"{prefix} {name} must declare at least one field", line.number)
        return RecordDecl(name, tuple(fields), line.number, layout_kind, documentation=self._doc_for(line)), field_index

    def _parse_enum_decl(self, index: int) -> tuple[EnumDecl, int]:
        line = self.lines[index]
        match = re.fullmatch(rf"enum ([A-Za-z][A-Za-z0-9_]*):\s*({TYPE_PATTERN})", line.text)
        if not line.is_header or match is None:
            raise InscriptionError("malformed enum declaration", line.number)
        name = self._record_name(match.group(1), line.number)
        underlying_type = self._value_type(match.group(2), line.number)
        cases: list[EnumCaseDecl] = []
        case_index = index + 1
        while case_index < len(self.lines):
            current = self.lines[case_index]
            if current.indent <= line.indent:
                break
            case_match = re.fullmatch(r"([a-z][a-z0-9_]*) be (.+)", current.text)
            if current.is_header or case_match is None:
                raise InscriptionError("malformed enum case declaration", current.number)
            cases.append(
                EnumCaseDecl(
                    self._field_name(case_match.group(1), current.number),
                    self._parse_expression(case_match.group(2), current.number),
                    current.number,
                )
            )
            case_index += 1
        if not cases:
            raise InscriptionError(f"enum {name} must declare at least one case", line.number)
        return EnumDecl(name, underlying_type, tuple(cases), line.number, self._doc_for(line)), case_index

    def _parse_union_decl(self, index: int) -> tuple[UnionDecl, int]:
        line = self.lines[index]
        match = re.fullmatch(r"union ([A-Za-z][A-Za-z0-9_]*)", line.text)
        if not line.is_header or match is None:
            raise InscriptionError("malformed union declaration", line.number)
        name = self._record_name(match.group(1), line.number)
        variants: list[UnionVariantDecl] = []
        variant_index = index + 1
        while variant_index < len(self.lines):
            current = self.lines[variant_index]
            if current.indent <= line.indent:
                break
            if current.is_header:
                raise InscriptionError("malformed union variant declaration", current.number)
            payload_match = re.fullmatch(r"([a-z][a-z0-9_]*)(?:\s+(.+))?", current.text)
            if payload_match is not None and payload_match.group(2) is not None:
                payload_fields: list[UnionPayloadField] = []
                for field_text in payload_match.group(2).split(" and "):
                    field_match = re.fullmatch(rf"([a-z][a-z0-9_]*):\s*({TYPE_PATTERN})", field_text)
                    if field_match is None:
                        raise InscriptionError("malformed union variant declaration", current.number)
                    payload_fields.append(
                        UnionPayloadField(
                            self._field_name(field_match.group(1), current.number),
                            self._value_type(field_match.group(2), current.number),
                            current.number,
                        )
                    )
                variants.append(
                    UnionVariantDecl(
                        self._field_name(payload_match.group(1), current.number),
                        tuple(payload_fields),
                        current.number,
                    )
                )
                variant_index += 1
                continue
            no_payload_match = re.fullmatch(r"([a-z][a-z0-9_]*)", current.text)
            if no_payload_match is not None:
                variants.append(
                    UnionVariantDecl(
                        self._field_name(no_payload_match.group(1), current.number),
                        (),
                        current.number,
                    )
                )
                variant_index += 1
                continue
            raise InscriptionError("malformed union variant declaration", current.number)
        if not variants:
            raise InscriptionError(f"union {name} must declare at least one variant", line.number)
        return UnionDecl(name, tuple(variants), line.number, self._doc_for(line)), variant_index

    def _parse_type_alias_decl(self, line: Line) -> TypeAliasDecl:
        match = re.fullmatch(rf"type ([A-Za-z][A-Za-z0-9_]*) be ({TYPE_PATTERN})", line.text)
        if line.is_header or match is None:
            raise InscriptionError("malformed type alias declaration", line.number)
        return TypeAliasDecl(
            self._record_name(match.group(1), line.number),
            self._value_type(match.group(2), line.number),
            line.number,
            self._doc_for(line),
        )

    def _parse_constant_decl(self, line: Line) -> ConstantDecl:
        match = re.fullmatch(rf"constant ([A-Za-z][A-Za-z0-9_]*):\s*({TYPE_PATTERN}) be (.+)", line.text)
        if line.is_header or match is None:
            raise InscriptionError("malformed constant declaration", line.number)
        raw_name = match.group(1)
        name = self._name(raw_name, line.number) if NAME_RE.fullmatch(raw_name) else raw_name
        return ConstantDecl(name, self._return_type(match.group(2), line.number), self._parse_expression(match.group(3), line.number), line.number, self._doc_for(line))

    def _parse_constant_match_decl(self, index: int) -> tuple[ConstantDecl, int]:
        line = self.lines[index]
        match = re.fullmatch(rf"constant ([A-Za-z][A-Za-z0-9_]*):\s*({TYPE_PATTERN}) be match (.+)", line.text)
        if not line.is_header or match is None:
            raise InscriptionError("malformed constant declaration", line.number)
        raw_name = match.group(1)
        name = self._name(raw_name, line.number) if NAME_RE.fullmatch(raw_name) else raw_name
        expr, next_index = self._parse_match_expression(index, scrutinee_text=match.group(3))
        return ConstantDecl(name, self._return_type(match.group(2), line.number), expr, line.number, self._doc_for(line)), next_index

    def _parse_check_stmt(self, line: Line) -> CheckStmt:
        if line.is_header:
            raise InscriptionError("malformed check", line.number)
        if not line.text.startswith("check "):
            raise InscriptionError("malformed check", line.number)
        return CheckStmt(self._parse_expression(line.text[len("check ") :], line.number), line.number)

    def _parse_check_match_stmt(self, index: int) -> tuple[CheckStmt, int]:
        line = self.lines[index]
        if not line.is_header or not line.text.startswith("check match "):
            raise InscriptionError("malformed check", line.number)
        expr, next_index = self._parse_match_expression(index, scrutinee_text=line.text[len("check match ") :])
        return CheckStmt(expr, line.number), next_index

    def _parse_require_stmt(self, line: Line) -> RequireStmt:
        if line.is_header:
            raise InscriptionError("malformed require", line.number)
        if not line.text.startswith("require "):
            raise InscriptionError("malformed require", line.number)
        return RequireStmt(self._parse_expression(line.text[len("require ") :], line.number), line.number)

    def _parse_require_match_stmt(self, index: int) -> tuple[RequireStmt, int]:
        line = self.lines[index]
        if not line.is_header or not line.text.startswith("require match "):
            raise InscriptionError("malformed require", line.number)
        expr, next_index = self._parse_match_expression(index, scrutinee_text=line.text[len("require match ") :])
        return RequireStmt(expr, line.number), next_index

    def _parse_expect_stmt(self, line: Line) -> ExpectStmt:
        if line.is_header:
            raise InscriptionError("malformed expect", line.number)
        if not line.text.startswith("expect "):
            raise InscriptionError("malformed expect", line.number)
        return ExpectStmt(self._parse_expression(line.text[len("expect ") :], line.number), line.number)

    def _parse_expect_match_stmt(self, index: int) -> tuple[ExpectStmt, int]:
        line = self.lines[index]
        if not line.is_header or not line.text.startswith("expect match "):
            raise InscriptionError("malformed expect", line.number)
        expr, next_index = self._parse_match_expression(index, scrutinee_text=line.text[len("expect match ") :])
        return ExpectStmt(expr, line.number), next_index

    def _looks_like_phrase_header(self, line: Line) -> bool:
        return line.is_header and re.fullmatch(r".+? (?:gives .+|does)", line.text) is not None

    def _parse_phrase_header(self, line: Line) -> tuple[PhraseTemplate, ReturnType]:
        match = re.fullmatch(r"(.+?) (?:gives (.+)|does)", line.text)
        if not line.is_header or not match:
            raise InscriptionError("expected phrase definition", line.number)
        phrase_text = match.group(1).strip()
        return_type = self._return_type(match.group(2), line.number) if match.group(2) is not None else None
        template = self._parse_phrase_template(phrase_text, line.number, return_type)
        return template, return_type

    def _parse_extern_decl(self, line: Line) -> tuple[PhraseTemplate, ReturnType, str]:
        if line.is_header:
            raise InscriptionError("extern phrase declarations cannot have bodies", line.number)
        gives_match = re.fullmatch(
                rf"extern (.+?) gives ({PHRASE_HOLE_TYPE_PATTERN}) as ({EXTERNAL_SYMBOL_PATTERN})",
            line.text,
        )
        if gives_match is not None:
            return_type = self._return_type(gives_match.group(2), line.number)
            template = self._parse_phrase_template(gives_match.group(1).strip(), line.number, return_type)
            return template, return_type, gives_match.group(3)
        does_match = re.fullmatch(
            rf"extern (.+?) does as ({EXTERNAL_SYMBOL_PATTERN})",
            line.text,
        )
        if does_match is not None:
            template = self._parse_phrase_template(does_match.group(1).strip(), line.number, None)
            return template, None, does_match.group(2)
        raise InscriptionError("malformed extern phrase declaration", line.number)


    def _parse_export_header(self, line: Line) -> tuple[PhraseTemplate, ReturnType, str]:
        if not line.is_header:
            raise InscriptionError("exported phrase definitions require a body", line.number)
        gives_match = re.fullmatch(
                rf"export (.+?) gives ({PHRASE_HOLE_TYPE_PATTERN}) as ({EXTERNAL_SYMBOL_PATTERN})",
            line.text,
        )
        if gives_match is not None:
            return_type = self._return_type(gives_match.group(2), line.number)
            template = self._parse_phrase_template(gives_match.group(1).strip(), line.number, return_type)
            return template, return_type, gives_match.group(3)
        does_match = re.fullmatch(
            rf"export (.+?) does as ({EXTERNAL_SYMBOL_PATTERN})",
            line.text,
        )
        if does_match is not None:
            template = self._parse_phrase_template(does_match.group(1).strip(), line.number, None)
            return template, None, does_match.group(2)
        raise InscriptionError("malformed exported phrase definition", line.number)

    def _parse_phrase_template(self, text: str, line: int, return_type: ReturnType) -> PhraseTemplate:
        parts: list[PhrasePart] = []
        params: list[Parameter] = []
        param_names: set[str] = set()
        pos = 0
        holes = list(
            re.finditer(
                rf"\b([a-z][a-z0-9_]*):\s*({PHRASE_HOLE_TYPE_PATTERN})\b",
                text,
            )
        )
        for match in holes:
            self._append_literal_parts(parts, text[pos : match.start()], line)
            name = self._name(match.group(1), line)
            type_name = self._value_type(match.group(2), line)
            if name in param_names:
                raise InscriptionError(f"duplicate parameter '{name}'", line)
            param_names.add(name)
            params.append(Parameter(name, type_name))
            parts.append(PhraseHole(name, type_name))
            pos = match.end()
        self._append_literal_parts(parts, text[pos:], line)
        if not parts or all(isinstance(part, PhraseHole) for part in parts):
            raise InscriptionError("phrase definition must include literal words", line)
        symbol = self._phrase_symbol(parts, line)
        if self.symbol_prefix is not None:
            symbol = f"{self.symbol_prefix}__{symbol}"
        display_name = " ".join("_" if isinstance(part, PhraseHole) else part for part in parts)
        return PhraseTemplate(symbol, tuple(parts), tuple(params), line, return_type, display_name)

    def _append_literal_parts(self, parts: list[PhrasePart], text: str, line: int) -> None:
        stripped = text.strip()
        if not stripped:
            return
        for word in stripped.split():
            if not NAME_RE.fullmatch(word):
                raise InscriptionError(f"invalid phrase word '{word}'", line)
            parts.append(word)

    def _phrase_symbol(self, parts: list[PhrasePart], line: int) -> str:
        leading: list[str] = []
        for part in parts:
            if isinstance(part, PhraseHole):
                break
            leading.append(part)
        if not leading:
            raise InscriptionError("phrase definition must start with literal words", line)
        while len(leading) > 1 and leading[-1] in CONNECTOR_WORDS:
            leading.pop()
        symbol = "_".join(leading)
        if not NAME_RE.fullmatch(symbol):
            raise InscriptionError(f"invalid generated function name '{symbol}'", line)
        return symbol

    def _parse_phrase_body(
        self, index: int, template: PhraseTemplate, line: int
    ) -> tuple[list[BodyStmt | ReturnStmt], int]:
        if template.return_type is None:
            return self._parse_does_body(index, line)
        return self._parse_gives_body(index, template.symbol, line)

    def _parse_test_body(self, index: int, line: int, display_name: str) -> tuple[list[BodyStmt], int]:
        body_items: list[BodyStmt] = []
        while index < len(self.lines):
            current = self.lines[index]
            if self._looks_like_top_level_item(current):
                break
            if current.text.startswith("return "):
                raise InscriptionError("Give is not valid inside a test", current.number)
            if not self._is_body_item_start(current, include_phrase_calls=True):
                if current.is_header:
                    raise InscriptionError("unexpected ':' inside test body", current.number)
                if self._parse_phrase_call_expr(current) is not None:
                    item, index = self._parse_body_item(index, include_phrase_calls=True)
                    body_items.append(item)
                    continue
                raise InscriptionError("test body only supports steps and Expect sentences", current.number)
            item, index = self._parse_body_item(index, include_phrase_calls=True)
            body_items.append(item)
        if not body_items:
            raise InscriptionError(f"test `{display_name}` must contain at least one Expect", line)
        return body_items, index

    def _parse_does_body(self, index: int, line: int) -> tuple[list[BodyStmt | ReturnStmt], int]:
        body_items: list[BodyStmt] = []
        while index < len(self.lines):
            current = self.lines[index]
            if self._looks_like_top_level_item(current):
                break
            if not self._is_body_item_start(current, include_phrase_calls=True):
                if current.is_header:
                    raise InscriptionError("unexpected ':' inside does phrase body", current.number)
                if self._parse_phrase_call_expr(current) is not None:
                    item, index = self._parse_body_item(index, include_phrase_calls=True)
                    body_items.append(item)
                    continue
                raise InscriptionError("does phrase body cannot end with a value expression", current.number)
            item, index = self._parse_body_item(index, include_phrase_calls=True)
            body_items.append(item)
        if not body_items:
            raise InscriptionError("does phrase body must contain at least one step", line)
        return body_items, index

    def _parse_gives_body(self, index: int, name: str, line: int) -> tuple[list[BodyStmt | ReturnStmt], int]:
        body_items: list[BodyStmt] = []
        value_lines: list[Line] = []
        while index < len(self.lines):
            current = self.lines[index]
            if self._looks_like_top_level_item(current):
                break
            if self._is_match_expression_start(index):
                if value_lines:
                    raise InscriptionError("value block can contain only one unconditional expression", current.number)
                value_lines, index = self._collect_match_expression_lines(index)
                continue
            if self._is_gives_body_item_start(current, index):
                if value_lines:
                    if current.text.startswith("let "):
                        raise InscriptionError("let bindings must appear before the value block", current.number)
                    raise InscriptionError("body items must appear before the value block", current.number)
                item, index = self._parse_body_item(index, include_phrase_calls=True)
                body_items.append(item)
            else:
                if current.is_header:
                    raise InscriptionError("unexpected ':' inside phrase body", current.number)
                value_lines.append(current)
                index += 1
        if not value_lines:
            raise InscriptionError("gives phrase body must end with a value expression", line)
        return [*body_items, ReturnStmt(self._parse_value_block(value_lines), value_lines[-1].number)], index

    def _is_gives_body_item_start(self, line: Line, index: int) -> bool:
        if line.is_header and line.text.startswith("match ") and self._is_match_expression_start(index):
            return False
        if self._is_body_item_start(line, include_phrase_calls=False):
            return True
        call = self._parse_phrase_call_expr(line)
        if call is None:
            return False
        target = self._template_for_call(call)
        if target is not None and target.return_type is None:
            return True
        return self._has_following_body_line(index + 1, line.indent)

    def _has_following_body_line(self, index: int, indent: int) -> bool:
        while index < len(self.lines):
            current = self.lines[index]
            if self._looks_like_top_level_item(current):
                return False
            if current.indent < indent:
                return False
            return True
        return False

    def _is_body_item_start(self, line: Line, *, include_phrase_calls: bool) -> bool:
        return (
            line.text.startswith("check ")
            or line.text.startswith("require ")
            or line.text.startswith("expect ")
            or line.text.startswith("let ")
            or line.text.startswith("track ")
            or self._layout_write_match(line) is not None
            or self._field_assignment_match(line) is not None
            or self._field_match_assignment_match(line) is not None
            or self._buffer_store_match(line) is not None
            or self._buffer_match_store_match(line) is not None
            or self._assignment_match(line) is not None
            or self._match_assignment_match(line) is not None
            or (line.is_header and line.text.startswith("if "))
            or (line.is_header and line.text.startswith("while "))
            or (line.is_header and line.text.startswith("for "))
            or (line.is_header and line.text.startswith("match "))
            or (include_phrase_calls and self._parse_phrase_call_expr(line) is not None)
        )

    def _parse_body_item(self, index: int, *, include_phrase_calls: bool) -> tuple[BodyStmt, int]:
        current = self.lines[index]
        if current.text.startswith("check "):
            if current.is_header and current.text.startswith("check match "):
                return self._parse_check_match_stmt(index)
            return self._parse_check_stmt(current), index + 1
        if current.text.startswith("require "):
            if current.is_header and current.text.startswith("require match "):
                return self._parse_require_match_stmt(index)
            if include_phrase_calls:
                call = self._parse_phrase_call_expr(current)
                target = self._template_for_call(call) if call is not None else None
                if target is not None and target.return_type is None:
                    return CallStmt(call, current.number), index + 1
            return self._parse_require_stmt(current), index + 1
        if current.text.startswith("expect "):
            if current.is_header and current.text.startswith("expect match "):
                return self._parse_expect_match_stmt(index)
            return self._parse_expect_stmt(current), index + 1
        if current.text.startswith("let "):
            if current.is_header and " be match " in current.text:
                return self._parse_let_match(index)
            return self._parse_let(current), index + 1
        if current.text.startswith("track "):
            raise InscriptionError("`track` is not valid Inscription syntax; use `let name be ...`", current.number)
        layout_write = self._layout_write_match(current)
        if layout_write is not None:
            return self._parse_layout_write(current, layout_write), index + 1
        field_assignment = self._field_assignment_match(current)
        if field_assignment is not None:
            return self._parse_field_assignment(current, field_assignment), index + 1
        field_match_assignment = self._field_match_assignment_match(current)
        if field_match_assignment is not None:
            return self._parse_field_match_assignment(index, field_match_assignment)
        buffer_store = self._buffer_store_match(current)
        if buffer_store is not None:
            return self._parse_buffer_store(current, buffer_store), index + 1
        buffer_match_store = self._buffer_match_store_match(current)
        if buffer_match_store is not None:
            return self._parse_buffer_match_store(index, buffer_match_store)
        assignment = self._assignment_match(current)
        if assignment is not None:
            return self._parse_assignment(current, assignment), index + 1
        match_assignment = self._match_assignment_match(current)
        if match_assignment is not None:
            return self._parse_match_assignment(index, match_assignment)
        if current.is_header and current.text.startswith("if "):
            return self._parse_if(index)
        if current.is_header and current.text.startswith("while "):
            return self._parse_while(index)
        if current.is_header and current.text.startswith("for "):
            return self._parse_for(index)
        if current.is_header and current.text.startswith("match "):
            return self._parse_match_step(index)
        if include_phrase_calls:
            call = self._parse_phrase_call_expr(current)
            if call is not None:
                return CallStmt(call, current.number), index + 1
        raise InscriptionError("expected phrase body item", current.number)

    def _parse_while(self, index: int) -> tuple[WhileStmt, int]:
        line = self.lines[index]
        match = re.fullmatch(r"while (.+)", line.text)
        if not line.is_header or not match:
            raise InscriptionError("malformed while loop", line.number)
        condition = self._parse_expression(match.group(1), line.number)
        body, body_index = self._parse_step_block(index + 1, line.indent, "while body")
        if not body:
            raise InscriptionError("while loop requires an indented body", line.number)
        return WhileStmt(condition, tuple(body), line.number), body_index

    def _parse_for(self, index: int) -> tuple[ForStmt | ForEachStmt, int]:
        line = self.lines[index]
        if not line.is_header:
            raise InscriptionError("malformed for loop", line.number)
        each_match = re.fullmatch(r"for each index ([a-z][a-z0-9_]*) of ([a-z][a-z0-9_]*)", line.text)
        if each_match:
            body, body_index = self._parse_step_block(index + 1, line.indent, "for loop body")
            if not body:
                raise InscriptionError("for loop body must contain at least one step", line.number)
            return (
                ForEachStmt(
                    self._name(each_match.group(1), line.number),
                    self._name(each_match.group(2), line.number),
                    tuple(body),
                    line.number,
                ),
                body_index,
            )

        match = re.fullmatch(r"for ([a-z][a-z0-9_]*) from (.+) up to (.+?)(?: by (-?\d+))?", line.text)
        if not match:
            raise InscriptionError("malformed for loop", line.number)
        step = int(match.group(4)) if match.group(4) is not None else 1
        body, body_index = self._parse_step_block(index + 1, line.indent, "for loop body")
        if not body:
            raise InscriptionError("for loop body must contain at least one step", line.number)
        return (
            ForStmt(
                self._name(match.group(1), line.number),
                self._parse_expression(match.group(2), line.number),
                self._parse_expression(match.group(3), line.number),
                step,
                tuple(body),
                line.number,
            ),
            body_index,
        )

    def _parse_if(self, index: int) -> tuple[IfStmt, int]:
        line = self.lines[index]
        match = re.fullmatch(r"if (.+)", line.text)
        if not line.is_header or not match:
            raise InscriptionError("malformed if block", line.number)
        condition = self._parse_expression(match.group(1), line.number)
        then_body, otherwise_index = self._parse_step_block(index + 1, line.indent, "if branch")
        if not then_body:
            raise InscriptionError("if branch must contain at least one step", line.number)
        if otherwise_index >= len(self.lines):
            raise InscriptionError("if block requires otherwise", line.number)
        otherwise = self.lines[otherwise_index]
        if not otherwise.is_header or otherwise.text != "otherwise" or otherwise.indent != line.indent:
            raise InscriptionError("if block requires otherwise", line.number)
        else_body, next_index = self._parse_step_block(otherwise_index + 1, otherwise.indent, "otherwise branch")
        if not else_body:
            raise InscriptionError("otherwise branch must contain at least one step", otherwise.number)
        return IfStmt(condition, tuple(then_body), tuple(else_body), line.number), next_index

    def _parse_step_block(self, index: int, parent_indent: int, name: str) -> tuple[list[BodyStmt], int]:
        body: list[BodyStmt] = []
        body_index = index
        while body_index < len(self.lines):
            current = self.lines[body_index]
            if current.indent <= parent_indent:
                break
            if self._looks_like_top_level_item(current):
                raise InscriptionError(f"phrase definitions cannot appear inside {name}", current.number)
            if not self._is_body_item_start(current, include_phrase_calls=True):
                raise InscriptionError(
                    f"{name} only supports let bindings, assignments, phrase calls, while loops, for loops, and if blocks",
                    current.number,
                )
            item, body_index = self._parse_body_item(body_index, include_phrase_calls=True)
            body.append(item)
        return body, body_index

    def _is_match_expression_start(self, index: int) -> bool:
        if index >= len(self.lines):
            return False
        line = self.lines[index]
        if not line.is_header or not line.text.startswith("match "):
            return False
        first_child_index = index + 1
        if first_child_index >= len(self.lines) or self.lines[first_child_index].indent <= line.indent:
            return False
        first_child = self.lines[first_child_index]
        return (not first_child.is_header) and (
            " gives " in first_child.text or first_child.text.startswith("otherwise gives ")
        )

    def _collect_match_expression_lines(self, index: int) -> tuple[list[Line], int]:
        header = self.lines[index]
        lines = [header]
        current_index = index + 1
        while current_index < len(self.lines):
            current = self.lines[current_index]
            if current.indent <= header.indent:
                break
            lines.append(current)
            current_index += 1
        return lines, current_index

    def _parse_match_expression(self, index: int, *, scrutinee_text: str | None = None) -> tuple[MatchExpr, int]:
        header = self.lines[index]
        if not header.is_header:
            raise InscriptionError("malformed match expression", header.number)
        if scrutinee_text is None:
            match = re.fullmatch(r"match (.+)", header.text)
            if match is None:
                raise InscriptionError("malformed match expression", header.number)
            scrutinee_text = match.group(1)
        scrutinee = self._parse_expression(scrutinee_text, header.number)
        arms: list[MatchExprArm] = []
        otherwise: Expr | None = None
        current_index = index + 1
        while current_index < len(self.lines):
            current = self.lines[current_index]
            if current.indent <= header.indent:
                break
            if current.is_header:
                raise InscriptionError("match expression arms must use `pattern gives expression`", current.number)
            if current.text.startswith("otherwise when "):
                raise InscriptionError("otherwise cannot have a match guard", current.number)
            if current.text.startswith("otherwise gives "):
                if otherwise is not None:
                    raise InscriptionError("match expression can contain only one otherwise", current.number)
                otherwise = self._parse_expression(current.text[len("otherwise gives ") :], current.number)
                current_index += 1
                if current_index < len(self.lines) and self.lines[current_index].indent > header.indent:
                    raise InscriptionError("otherwise must be the final match arm", self.lines[current_index].number)
                break
            if otherwise is not None:
                raise InscriptionError("otherwise must be the final match arm", current.number)
            if " gives " not in current.text:
                raise InscriptionError("match expression arms must use `pattern gives expression`", current.number)
            pattern_text, expr_text = current.text.split(" gives ", 1)
            pattern_text, guard_text = self._split_match_guard(pattern_text.strip(), current.number)
            arms.append(
                MatchExprArm(
                    self._parse_pattern(pattern_text, current.number),
                    None if guard_text is None else self._parse_expression(guard_text, current.number),
                    self._parse_expression(expr_text.strip(), current.number),
                    current.number,
                )
            )
            current_index += 1
        return MatchExpr(scrutinee, tuple(arms), otherwise, header.number), current_index

    def _parse_match_step(self, index: int) -> tuple[MatchStep, int]:
        header = self.lines[index]
        match = re.fullmatch(r"match (.+)", header.text)
        if not header.is_header or match is None:
            raise InscriptionError("malformed match block", header.number)
        scrutinee = self._parse_expression(match.group(1), header.number)
        arms: list[MatchStepArm] = []
        otherwise_body: tuple[BodyStmt, ...] | None = None
        current_index = index + 1
        while current_index < len(self.lines):
            current = self.lines[current_index]
            if current.indent <= header.indent:
                break
            if not current.is_header:
                raise InscriptionError("match block arms must use `pattern:`", current.number)
            if current.text.startswith("otherwise when "):
                raise InscriptionError("otherwise cannot have a match guard", current.number)
            if current.text == "otherwise":
                if otherwise_body is not None:
                    raise InscriptionError("match block can contain only one otherwise", current.number)
                body, next_index = self._parse_step_block(current_index + 1, current.indent, "match arm")
                if not body:
                    raise InscriptionError("match arm must contain at least one step", current.number)
                otherwise_body = tuple(body)
                current_index = next_index
                if current_index < len(self.lines) and self.lines[current_index].indent > header.indent:
                    raise InscriptionError("otherwise must be the final match arm", self.lines[current_index].number)
                break
            if otherwise_body is not None:
                raise InscriptionError("otherwise must be the final match arm", current.number)
            body, next_index = self._parse_step_block(current_index + 1, current.indent, "match arm")
            if not body:
                raise InscriptionError("match arm must contain at least one step", current.number)
            pattern_text, guard_text = self._split_match_guard(current.text, current.number)
            arms.append(
                MatchStepArm(
                    self._parse_pattern(pattern_text, current.number),
                    None if guard_text is None else self._parse_expression(guard_text, current.number),
                    tuple(body),
                    current.number,
                )
            )
            current_index = next_index
        return MatchStep(scrutinee, tuple(arms), otherwise_body, header.number), current_index

    def _parse_let_match(self, index: int) -> tuple[SetStmt, int]:
        line = self.lines[index]
        match = re.fullmatch(rf"let ([a-z][a-z0-9_]*)(?::\s*({TYPE_REF_PATTERN}))? be match (.+)", line.text)
        if not line.is_header or match is None:
            raise InscriptionError("malformed let binding", line.number)
        expr, next_index = self._parse_match_expression(index, scrutinee_text=match.group(3))
        return (
            SetStmt(
                self._name(match.group(1), line.number),
                self._return_type(match.group(2), line.number) if match.group(2) is not None else None,
                expr,
                line.number,
            ),
            next_index,
        )

    def _parse_value_block(self, lines: list[Line]) -> Expr:
        if len(lines) > 1 and lines[0].is_header and lines[0].text.startswith("match "):
            expr, next_index = self._parse_match_expression_from_lines(lines)
            if next_index != len(lines):
                raise InscriptionError("unconditional value expression must be the final value block line", lines[next_index].number)
            return expr
        cases: list[WhenCase] = []
        otherwise: Expr | None = None
        unconditional: Expr | None = None
        for index, line in enumerate(lines):
            text = line.text
            if text.startswith("otherwise "):
                if otherwise is not None:
                    raise InscriptionError("value block can contain only one otherwise line", line.number)
                if not cases:
                    raise InscriptionError("otherwise requires at least one preceding when line", line.number)
                if index != len(lines) - 1:
                    raise InscriptionError("otherwise must be the final value block line", line.number)
                otherwise = self._parse_expression(text[len("otherwise ") :], line.number)
                continue
            if " when " in text:
                if unconditional is not None or otherwise is not None:
                    raise InscriptionError("conditional value lines must appear before otherwise", line.number)
                expr_text, condition_text = text.rsplit(" when ", 1)
                cases.append(
                    WhenCase(
                        self._parse_expression(expr_text, line.number),
                        self._parse_expression(condition_text, line.number),
                        line.number,
                    )
                )
                continue
            if cases:
                raise InscriptionError("conditional value block requires an otherwise line", line.number)
            if unconditional is not None:
                raise InscriptionError("value block can contain only one unconditional expression", line.number)
            if index != len(lines) - 1:
                raise InscriptionError("unconditional value expression must be the final value block line", line.number)
            unconditional = self._parse_expression(text, line.number)
        if cases:
            if otherwise is None:
                raise InscriptionError("conditional value block requires an otherwise line", lines[-1].number)
            return WhenExpr(tuple(cases), otherwise, lines[0].number)
        if unconditional is None:
            raise InscriptionError("value block must evaluate to an expression", lines[-1].number)
        return unconditional

    def _parse_match_expression_from_lines(self, lines: list[Line]) -> tuple[MatchExpr, int]:
        original_lines = self.lines
        self.lines = lines
        try:
            return self._parse_match_expression(0)
        finally:
            self.lines = original_lines

    def _parse_let(self, line: Line) -> SetStmt | BufferBinding | ArrayBinding | OwnedBufferBinding | StorageAliasBinding | ViewBinding:
        inferred_byte_buffer_match = re.fullmatch(r'let ([a-z][a-z0-9_]*) be buffer of bytes (".*")', line.text)
        if inferred_byte_buffer_match:
            values = decode_byte_string_token(inferred_byte_buffer_match.group(2), line.number)
            if not values:
                raise InscriptionError("byte buffer literal must contain at least one byte", line.number)
            return BufferBinding(
                self._name(inferred_byte_buffer_match.group(1), line.number),
                BufferType(len(values), "u8"),
                line.number,
                values=(ByteString(values, line.number),),
            )
        inferred_byte_array_match = re.fullmatch(r'let ([a-z][a-z0-9_]*) be array of bytes (".*")', line.text)
        if inferred_byte_array_match:
            values = decode_byte_string_token(inferred_byte_array_match.group(2), line.number)
            if not values:
                raise InscriptionError("byte array literal must contain at least one byte", line.number)
            return ArrayBinding(
                self._name(inferred_byte_array_match.group(1), line.number),
                ArrayType(len(values), "u8"),
                line.number,
                values=(ByteString(values, line.number),),
            )
        inferred_owned_byte_buffer_match = re.fullmatch(r'let ([a-z][a-z0-9_]*) be owned buffer of bytes (".*")', line.text)
        if inferred_owned_byte_buffer_match:
            values = decode_byte_string_token(inferred_owned_byte_buffer_match.group(2), line.number)
            if not values:
                raise InscriptionError("owned byte buffer literal must contain at least one byte", line.number)
            return OwnedBufferBinding(
                self._name(inferred_owned_byte_buffer_match.group(1), line.number),
                Integer(len(values), line.number),
                "u8",
                None,
                line.number,
                values=(ByteString(values, line.number),),
            )
        owned_copy_match = re.fullmatch(r"let ([a-z][a-z0-9_]*) be owned buffer copied from (.+)", line.text)
        if owned_copy_match:
            source_text = owned_copy_match.group(2).strip()
            if not NAME_RE.fullmatch(source_text):
                raise InscriptionError("owned buffer copy source must be a storage binding", line.number)
            return OwnedBufferBinding(
                self._name(owned_copy_match.group(1), line.number),
                None,
                None,
                None,
                line.number,
                copy_source_name=self._name(source_text, line.number),
            )
        owned_buffer_containing_match = re.fullmatch(
            rf"let ([a-z][a-z0-9_]*) be owned buffer of ({BUFFER_LENGTH_PATTERN}) ({TYPE_REF_PATTERN}) containing (.+)",
            line.text,
        )
        if owned_buffer_containing_match:
            return OwnedBufferBinding(
                self._name(owned_buffer_containing_match.group(1), line.number),
                self._parse_expression(owned_buffer_containing_match.group(2), line.number),
                self._return_type(owned_buffer_containing_match.group(3), line.number),
                None,
                line.number,
                values=self._parse_containing_list(owned_buffer_containing_match.group(4), line.number),
            )
        owned_buffer_match = re.fullmatch(
            rf"let ([a-z][a-z0-9_]*) be owned buffer of (.+) ({TYPE_REF_PATTERN}) filled with (.+)",
            line.text,
        )
        if owned_buffer_match:
            return OwnedBufferBinding(
                self._name(owned_buffer_match.group(1), line.number),
                self._parse_expression(owned_buffer_match.group(2), line.number),
                self._return_type(owned_buffer_match.group(3), line.number),
                self._parse_expression(owned_buffer_match.group(4), line.number),
                line.number,
            )
        buffer_match = re.fullmatch(
            rf"let ([a-z][a-z0-9_]*) be buffer of ({BUFFER_LENGTH_PATTERN}) ({TYPE_REF_PATTERN}) (filled with|containing) (.+)",
            line.text,
        )
        if buffer_match:
            initializer = buffer_match.group(4)
            initializer_text = buffer_match.group(5)
            buffer_type = BufferType(
                self._buffer_length(buffer_match.group(2), line.number),
                self._return_type(buffer_match.group(3), line.number),
            )
            if initializer == "containing":
                return BufferBinding(
                    self._name(buffer_match.group(1), line.number),
                    buffer_type,
                    line.number,
                    values=self._parse_containing_list(initializer_text, line.number),
                )
            return BufferBinding(
                self._name(buffer_match.group(1), line.number),
                buffer_type,
                line.number,
                fill=self._parse_expression(initializer_text, line.number),
            )
        array_match = re.fullmatch(
            rf"let ([a-z][a-z0-9_]*) be array of ({BUFFER_LENGTH_PATTERN}) ({TYPE_REF_PATTERN}) (filled with|containing) (.+)",
            line.text,
        )
        if array_match:
            initializer = array_match.group(4)
            initializer_text = array_match.group(5)
            array_type = ArrayType(
                self._buffer_length(array_match.group(2), line.number),
                self._return_type(array_match.group(3), line.number),
            )
            if initializer == "containing":
                return ArrayBinding(
                    self._name(array_match.group(1), line.number),
                    array_type,
                    line.number,
                    values=self._parse_containing_list(initializer_text, line.number),
                )
            return ArrayBinding(
                self._name(array_match.group(1), line.number),
                array_type,
                line.number,
                fill=self._parse_expression(initializer_text, line.number),
            )
        view_match = re.fullmatch(r"let ([a-z][a-z0-9_]*) be view of ([a-z][a-z0-9_]*) from (.+) for (.+)", line.text)
        if view_match:
            return ViewBinding(
                self._name(view_match.group(1), line.number),
                self._name(view_match.group(2), line.number),
                self._parse_expression(view_match.group(3), line.number),
                self._parse_expression(view_match.group(4), line.number),
                line.number,
            )
        storage_alias_match = re.fullmatch(
            rf"let ([a-z][a-z0-9_]*) be ((?:[A-Za-z][A-Za-z0-9_]*\.)*[A-Z][A-Za-z0-9_]*) (filled with|containing) (.+)",
            line.text,
        )
        if storage_alias_match:
            initializer = storage_alias_match.group(3)
            initializer_text = storage_alias_match.group(4)
            if initializer == "containing":
                return StorageAliasBinding(
                    self._name(storage_alias_match.group(1), line.number),
                    self._return_type(storage_alias_match.group(2), line.number),
                    line.number,
                    initializer,
                    values=self._parse_containing_list(initializer_text, line.number),
                )
            return StorageAliasBinding(
                self._name(storage_alias_match.group(1), line.number),
                self._return_type(storage_alias_match.group(2), line.number),
                line.number,
                initializer,
                fill=self._parse_expression(initializer_text, line.number),
            )
        match = re.fullmatch(rf"let ([a-z][a-z0-9_]*)(?::\s*({TYPE_REF_PATTERN}))? be (.+)", line.text)
        if not match:
            raise InscriptionError("malformed let binding", line.number)
        return SetStmt(
            self._name(match.group(1), line.number),
            self._return_type(match.group(2), line.number) if match.group(2) is not None else None,
            self._parse_expression(match.group(3), line.number),
            line.number,
        )

    def _parse_expression_list(self, text: str, line: int) -> tuple[Expr, ...]:
        return tuple(
            element if not isinstance(element, ByteString) else self._byte_string_as_value_error(element.line)
            for element in self._parse_containing_list(text, line)
        )

    def _byte_string_as_value_error(self, line: int) -> Expr:
        raise InscriptionError("byte string literal cannot be used as a value; use `array of bytes` or `buffer of bytes`", line)

    def _parse_containing_list(self, text: str, line: int) -> tuple[StorageElement, ...]:
        tokens = tokenize(text, line)
        parts: list[list[str]] = [[]]
        depth = 0
        for token in tokens:
            if token == "(":
                depth += 1
                parts[-1].append(token)
                continue
            if token == ")":
                if depth == 0:
                    raise InscriptionError("unexpected token ')' in expression", line)
                depth -= 1
                parts[-1].append(token)
                continue
            if token == "," and depth == 0:
                if not parts[-1]:
                    raise InscriptionError("expected expression", line)
                parts.append([])
                continue
            parts[-1].append(token)
        if depth != 0:
            raise InscriptionError("missing closing ')'", line)
        if not parts[-1]:
            raise InscriptionError("expected expression", line)
        elements: list[StorageElement] = []
        for part in parts:
            if len(part) == 2 and part[0] == "bytes" and _is_string_token(part[1]):
                elements.append(ByteString(decode_byte_string_token(part[1], line), line))
                continue
            elements.append(parse_expression_tokens(part, line, self.phrases))
        return tuple(elements)

    def _assignment_match(self, line: Line) -> re.Match[str] | None:
        if line.is_header:
            return None
        return re.fullmatch(r"([a-z][a-z0-9_]*) becomes (.+)", line.text)

    def _match_assignment_match(self, line: Line) -> re.Match[str] | None:
        if not line.is_header:
            return None
        return re.fullmatch(r"([a-z][a-z0-9_]*) becomes match (.+)", line.text)

    def _buffer_store_match(self, line: Line) -> re.Match[str] | None:
        if line.is_header:
            return None
        return re.fullmatch(r"([a-z][a-z0-9_]*) at (.+) becomes (.+)", line.text)

    def _buffer_match_store_match(self, line: Line) -> re.Match[str] | None:
        if not line.is_header:
            return None
        return re.fullmatch(r"([a-z][a-z0-9_]*) at (.+) becomes match (.+)", line.text)

    def _field_assignment_match(self, line: Line) -> re.Match[str] | None:
        if line.is_header:
            return None
        return re.fullmatch(r"([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*) becomes (.+)", line.text)

    def _field_match_assignment_match(self, line: Line) -> re.Match[str] | None:
        if not line.is_header:
            return None
        return re.fullmatch(r"([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*) becomes match (.+)", line.text)

    def _layout_write_match(self, line: Line) -> re.Match[str] | None:
        if line.is_header:
            return None
        return re.fullmatch(r"write ([a-z][a-z0-9_]*) into ([a-z][a-z0-9_]*) at (.+)", line.text)

    def _parse_assignment(self, line: Line, match: re.Match[str]) -> AssignStmt:
        return AssignStmt(
            self._name(match.group(1), line.number),
            self._parse_expression(match.group(2), line.number),
            line.number,
        )

    def _parse_match_assignment(self, index: int, match: re.Match[str]) -> tuple[AssignStmt, int]:
        line = self.lines[index]
        expr, next_index = self._parse_match_expression(index, scrutinee_text=match.group(2))
        return AssignStmt(self._name(match.group(1), line.number), expr, line.number), next_index

    def _parse_buffer_store(self, line: Line, match: re.Match[str]) -> BufferStoreStmt:
        return BufferStoreStmt(
            self._name(match.group(1), line.number),
            self._parse_expression(match.group(2), line.number),
            self._parse_expression(match.group(3), line.number),
            line.number,
        )

    def _parse_buffer_match_store(self, index: int, match: re.Match[str]) -> tuple[BufferStoreStmt, int]:
        line = self.lines[index]
        expr, next_index = self._parse_match_expression(index, scrutinee_text=match.group(3))
        return (
            BufferStoreStmt(
                self._name(match.group(1), line.number),
                self._parse_expression(match.group(2), line.number),
                expr,
                line.number,
            ),
            next_index,
        )

    def _parse_field_assignment(self, line: Line, match: re.Match[str]) -> FieldAssignStmt:
        return FieldAssignStmt(
            self._name(match.group(1), line.number),
            self._field_name(match.group(2), line.number),
            self._parse_expression(match.group(3), line.number),
            line.number,
        )

    def _parse_field_match_assignment(self, index: int, match: re.Match[str]) -> tuple[FieldAssignStmt, int]:
        line = self.lines[index]
        expr, next_index = self._parse_match_expression(index, scrutinee_text=match.group(3))
        return (
            FieldAssignStmt(
                self._name(match.group(1), line.number),
                self._field_name(match.group(2), line.number),
                expr,
                line.number,
            ),
            next_index,
        )

    def _parse_layout_write(self, line: Line, match: re.Match[str]) -> LayoutWriteStmt:
        return LayoutWriteStmt(
            self._name(match.group(1), line.number),
            self._name(match.group(2), line.number),
            self._parse_expression(match.group(3), line.number),
            line.number,
        )

    def _parse_pattern(self, text: str, line: int):
        text = text.strip()
        alternatives = _split_top_level_keyword(text, "or")
        if len(alternatives) > 1:
            return AlternativePattern(tuple(self._parse_pattern_atom(part, line) for part in alternatives), line)
        return self._parse_pattern_atom(text, line)

    def _parse_pattern_atom(self, text: str, line: int):
        text = text.strip()
        if text == "anything":
            return AnythingPattern(line)
        range_parts = _split_top_level_keyword(text, "through")
        if len(range_parts) == 2:
            return RangePattern(
                self._parse_expression(range_parts[0], line),
                self._parse_expression(range_parts[1], line),
                line,
            )
        if len(range_parts) > 2:
            raise InscriptionError("malformed range pattern", line)
        match = re.fullmatch(r"((?:[A-Za-z][A-Za-z0-9_]*\.)*[A-Z][A-Za-z0-9_]*)\.([a-z][a-z0-9_]*)(?: with (.+))?", text)
        if match is not None and match.group(3) is not None:
            bindings: list[UnionPatternBinding] = []
            for binding_text in match.group(3).split(" and "):
                binding_match = re.fullmatch(r"([a-z][a-z0-9_]*)(?:(?: as ([a-z][a-z0-9_]*))|(?: ignored))?", binding_text.strip())
                if binding_match is None:
                    raise InscriptionError("malformed union pattern", line)
                alias_name = binding_match.group(2)
                ignored = binding_text.strip().endswith(" ignored")
                if alias_name == "ignored":
                    raise InscriptionError("ignored is reserved in union payload patterns", line)
                bindings.append(
                    UnionPatternBinding(
                        self._field_name(binding_match.group(1), line),
                        None if alias_name is None else self._field_name(alias_name, line),
                        ignored,
                        line,
                    )
                )
            return UnionPattern(match.group(1), self._field_name(match.group(2), line), tuple(bindings), line)
        return self._parse_expression(text, line)

    def _split_match_guard(self, text: str, line: int) -> tuple[str, str | None]:
        index = _find_top_level_keyword(text, "when")
        if index == -1:
            return text.strip(), None
        pattern = text[:index].strip()
        guard = text[index + len("when") :].strip()
        if not pattern or not guard:
            raise InscriptionError("malformed match guard", line)
        return pattern, guard

    def _parse_expression(self, text: str, line: int) -> Expr:
        return parse_expression(text, line, self.phrases)

    def _parse_comparison(self, text: str, line: int) -> Comparison:
        return parse_comparison(text, line, self.phrases)

    def _parse_phrase_call_expr(self, line: Line) -> Call | None:
        if line.is_header:
            return None
        try:
            expr = self._parse_expression(line.text, line.number)
        except InscriptionError:
            return None
        if isinstance(expr, Call):
            return expr
        return None

    def _template_for_call(self, call: Call) -> PhraseTemplate | None:
        for template in self.phrases:
            if template.symbol == call.name:
                return template
        return None

    def _name(self, value: str, line: int) -> str:
        if not NAME_RE.fullmatch(value):
            raise InscriptionError(f"invalid identifier '{value}'", line)
        if value in RESERVED:
            raise InscriptionError(f"reserved word '{value}' cannot be an identifier", line)
        return value

    def _field_name(self, value: str, line: int) -> str:
        if not NAME_RE.fullmatch(value):
            raise InscriptionError(f"invalid field name '{value}'", line)
        return value

    def _module_name(self, value: str, line: int) -> str:
        if not MODULE_RE.fullmatch(value):
            raise InscriptionError(f"invalid module name '{value}'", line)
        for part in value.split("."):
            if part in RESERVED:
                raise InscriptionError(f"reserved word '{part}' cannot be a module name", line)
        return value

    def _record_name(self, value: str, line: int) -> str:
        if value in TYPE_NAMES:
            raise InscriptionError(f"record name {value} collides with scalar type", line)
        if not RECORD_NAME_RE.fullmatch(value):
            raise InscriptionError(f"invalid record name '{value}'", line)
        return value

    def _value_type(self, value: str, line: int) -> ValueType:
        value = " ".join(value.split())
        if value.startswith("owned buffer of "):
            element = value[len("owned buffer of ") :].strip()
            if not re.fullmatch(TYPE_REF_PATTERN, element):
                raise InscriptionError("malformed owned buffer type", line)
            return OwnedBufferType(self._return_type(element, line))
        buffer_match = re.fullmatch(rf"buffer of ({BUFFER_LENGTH_PATTERN}) ({TYPE_REF_PATTERN})", value)
        if buffer_match is not None:
            return BufferType(self._buffer_length(buffer_match.group(1), line), self._return_type(buffer_match.group(2), line))
        array_match = re.fullmatch(rf"array of ({BUFFER_LENGTH_PATTERN}) ({TYPE_REF_PATTERN})", value)
        if array_match is not None:
            return ArrayType(self._buffer_length(array_match.group(1), line), self._return_type(array_match.group(2), line))
        view_match = re.fullmatch(rf"view of ({TYPE_REF_PATTERN})", value)
        if view_match is not None:
            return ViewType(self._return_type(view_match.group(1), line))
        return self._return_type(value, line)

    def _buffer_length(self, value: str, line: int) -> int | Expr:
        value = value.strip()
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if NAME_RE.fullmatch(value):
            return Variable(value, line)
        if value.startswith("(") and value.endswith(")"):
            return self._parse_expression(value[1:-1].strip(), line)
        raise InscriptionError("malformed buffer length", line)

    def _return_type(self, value: str, line: int) -> ReturnType:
        if value.startswith("owned buffer of "):
            element = value[len("owned buffer of ") :].strip()
            if not re.fullmatch(TYPE_REF_PATTERN, element):
                raise InscriptionError("malformed owned buffer return type", line)
            return OwnedBufferType(self._return_type(element, line))
        if value.startswith("buffer of "):
            raise InscriptionError("buffer return types are not supported", line)
        if value.startswith("array of "):
            match = re.fullmatch(rf"array of ({BUFFER_LENGTH_PATTERN}) ({TYPE_REF_PATTERN})", value)
            if match is None:
                raise InscriptionError("malformed array type", line)
            return ArrayType(self._buffer_length(match.group(1), line), self._return_type(match.group(2), line))
        if value.startswith("view of "):
            return ViewType(self._return_type(value[len("view of ") :].strip(), line))
        if QUALIFIED_RECORD_NAME_RE.fullmatch(value):
            return RecordType(value)
        return self._type_name(value, line)

    def _type_name(self, value: str, line: int) -> TypeName:
        if value in TYPE_NAMES:
            return value  # type: ignore[return-value]
        raise InscriptionError("supported scalar types are i1, i8, i16, i32, i64, u8, u16, u32, u64, f32, and f64", line)


def tokenize(text: str, line: int) -> list[str]:
    tokens: list[str] = []
    pos = 0
    while pos < len(text):
        negative_float_match = re.match(rf"-(?:{FLOAT_LITERAL_RE})", text[pos:])
        if negative_float_match is not None:
            raise InscriptionError(f"invalid token near '{negative_float_match.group(0)}'", line)
        match = TOKEN_RE.match(text, pos)
        if not match:
            if text[pos:].strip() == "":
                break
            if text[pos:].lstrip().startswith('"'):
                raise InscriptionError("unterminated string literal", line)
            raise InscriptionError(f"invalid token near '{text[pos:].strip()}'", line)
        token_start = match.start(1)
        token = match.group(1)
        punctuation = {",", "(", ")", "."}
        if tokens and token_start == pos and tokens[-1] not in punctuation and token not in punctuation:
            raise InscriptionError("missing whitespace between expression tokens", line)
        tokens.append(token)
        pos = match.end()
    if not tokens:
        raise InscriptionError("expected expression", line)
    return tokens


def parse_expression(text: str, line: int, phrases: tuple[PhraseTemplate, ...] = ()) -> Expr:
    return parse_expression_tokens(tokenize(text, line), line, phrases)


def parse_expression_tokens(tokens: list[str], line: int, phrases: tuple[PhraseTemplate, ...] = ()) -> Expr:
    parser = ExpressionParser(tokens, line, phrases)
    expr = parser.parse_expression()
    if not parser.at_end():
        raise InscriptionError(f"unexpected token '{parser.peek()}' in expression", line)
    return expr


def _is_wrapped_by_single_parenthesized_group(tokens: list[str]) -> bool:
    if len(tokens) < 2 or tokens[0] != "(" or tokens[-1] != ")":
        return False
    depth = 0
    for index, token in enumerate(tokens):
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
            if depth == 0 and index != len(tokens) - 1:
                return False
        if depth < 0:
            return False
    return depth == 0


def parse_comparison(text: str, line: int, phrases: tuple[PhraseTemplate, ...] = ()) -> Comparison:
    expr = parse_expression(text, line, phrases)
    if not isinstance(expr, Comparison):
        raise InscriptionError("comparison must contain 'is'", line)
    return expr


class ExpressionParser:
    def __init__(self, tokens: list[str], line: int, phrases: tuple[PhraseTemplate, ...] = ()):
        self.tokens = tokens
        self.line = line
        self.phrases = phrases
        self.pos = 0

    def at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    def peek(self) -> str | None:
        if self.at_end():
            return None
        return self.tokens[self.pos]

    def pop(self) -> str:
        if self.at_end():
            raise InscriptionError("unexpected end of expression", self.line)
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def parse_expression(self, stop: set[str] | None = None) -> Expr:
        return self.parse_or(stop or set())

    def parse_or(self, stop: set[str]) -> Expr:
        left = self.parse_and(stop)
        while not self.at_end() and self.peek() == "or" and "or" not in stop:
            self.pop()
            right = self.parse_and(stop)
            left = Binary("or", left, right, self.line)
        return left

    def parse_and(self, stop: set[str]) -> Expr:
        left = self.parse_comparison(stop)
        while not self.at_end() and self.peek() == "and" and "and" not in stop:
            self.pop()
            right = self.parse_comparison(stop)
            left = Binary("and", left, right, self.line)
        return left

    def parse_comparison(self, stop: set[str]) -> Expr:
        comparison_stop = set(stop) | {"and", "or"}
        left = self.parse_bitwise_or(comparison_stop)
        if self.at_end() or self.peek() != "is" or "is" in stop:
            return left
        self.pop()
        rest = self.tokens[self.pos :]
        for phrase, predicate in COMPARATORS:
            phrase_len = len(phrase)
            if tuple(rest[:phrase_len]) == phrase:
                self.pos += phrase_len
                right = self.parse_bitwise_or(comparison_stop)
                return Comparison(predicate, left, right, self.line)
        raise InscriptionError("unsupported comparison operator", self.line)

    def parse_bitwise_or(self, stop: set[str]) -> Expr:
        left = self.parse_bitwise_xor(stop)
        while "bitwise" not in stop and self.match_sequence(("bitwise", "or")):
            right = self.parse_bitwise_xor(stop)
            left = Binary("bitwise or", left, right, self.line)
        return left

    def parse_bitwise_xor(self, stop: set[str]) -> Expr:
        left = self.parse_bitwise_and(stop)
        while "bitwise" not in stop and self.match_sequence(("bitwise", "xor")):
            right = self.parse_bitwise_and(stop)
            left = Binary("bitwise xor", left, right, self.line)
        return left

    def parse_bitwise_and(self, stop: set[str]) -> Expr:
        left = self.parse_shift(stop)
        while "bitwise" not in stop and self.match_sequence(("bitwise", "and")):
            right = self.parse_shift(stop)
            left = Binary("bitwise and", left, right, self.line)
        return left

    def parse_shift(self, stop: set[str]) -> Expr:
        left = self.parse_additive(stop)
        while not self.at_end() and self.peek() == "shifted" and "shifted" not in stop:
            if self.match_sequence(("shifted", "left", "by")):
                right = self.parse_additive(stop)
                left = Binary("shifted left by", left, right, self.line)
                continue
            if self.match_sequence(("shifted", "right", "by")):
                right = self.parse_additive(stop)
                left = Binary("shifted right by", left, right, self.line)
                continue
            raise InscriptionError("shift operator must be 'shifted left by' or 'shifted right by'", self.line)
        return left

    def parse_additive(self, stop: set[str]) -> Expr:
        left = self.parse_multiplicative(stop)
        while not self.at_end():
            token = self.peek()
            if token in stop or token in {",", ")", "is", "and", "or", "as", "shifted", "bitwise"}:
                break
            if token not in {"plus", "minus"}:
                break
            op = self.pop()
            right = self.parse_multiplicative(stop)
            left = Binary(op, left, right, self.line)  # type: ignore[arg-type]
        return left

    def parse_multiplicative(self, stop: set[str]) -> Expr:
        left = self.parse_unary(stop)
        while not self.at_end():
            token = self.peek()
            if token in stop or token in {",", ")", "is", "and", "or", "as", "shifted", "bitwise", "plus", "minus"}:
                break
            if token == "divided":
                if self.match_sequence(("divided", "by")):
                    op = "divided by"
                else:
                    raise InscriptionError("operator 'divided' must be followed by 'by'", self.line)
            elif token in {"times", "remainder"}:
                op = self.pop()
            else:
                break
            right = self.parse_unary(stop)
            left = Binary(op, left, right, self.line)  # type: ignore[arg-type]
        return left

    def parse_unary(self, stop: set[str]) -> Expr:
        if self.peek() == "not" and "not" not in stop:
            self.pop()
            return Unary("not", self.parse_unary(stop), self.line)
        if "bitwise" not in stop and self.match_sequence(("bitwise", "not")):
            return Unary("bitwise not", self.parse_unary(stop), self.line)
        return self.parse_postfix(stop)

    def parse_postfix(self, stop: set[str]) -> Expr:
        expr = self.parse_primary(stop)
        while not self.at_end():
            if self.peek() == "." and "." not in stop:
                if not isinstance(expr, Variable):
                    break
                self.pop()
                field = self.pop()
                if not NAME_RE.fullmatch(field):
                    raise InscriptionError(f"invalid field name '{field}'", self.line)
                expr = FieldAccess(expr.name, field, self.line)
                continue
            if self.peek() == "at" and "at" not in stop:
                if not isinstance(expr, Variable):
                    break
                self.pop()
                index = self.parse_primary(
                    set(stop)
                    | {
                        ",",
                        ")",
                        "is",
                        "and",
                        "or",
                        "as",
                        "shifted",
                        "bitwise",
                        "plus",
                        "minus",
                        "times",
                        "divided",
                        "remainder",
                    }
                )
                expr = BufferLoad(expr.name, index, self.line)
                continue
            if self.peek() == "as" and "as" not in stop:
                self.pop()
                expr = Cast(expr, self.parse_type_reference(), self.line)
                continue
            break
        return expr


    def parse_type_reference(self) -> ValueType:
        parts = [self.pop()]
        while self.pos + 1 < len(self.tokens) and self.tokens[self.pos] == "." and RECORD_NAME_RE.fullmatch(self.tokens[self.pos + 1]):
            self.pop()
            parts.append(self.pop())
        type_name = ".".join(parts)
        if type_name in TYPE_NAMES:
            return type_name  # type: ignore[return-value]
        if QUALIFIED_RECORD_NAME_RE.fullmatch(type_name):
            return RecordType(type_name)
        raise InscriptionError(f"unknown cast target type '{type_name}'", self.line)

    def parse_primary(self, stop: set[str]) -> Expr:
        token = self.peek()
        if token is None or token in stop or token == ",":
            raise InscriptionError("expected expression", self.line)
        if token == "size" and tuple(self.tokens[self.pos : self.pos + 2]) == ("size", "of"):
            self.pop()
            self.pop()
            type_name = self.pop()
            if not RECORD_NAME_RE.fullmatch(type_name):
                raise InscriptionError(f"invalid record name '{type_name}'", self.line)
            return SizeOfType(type_name, self.line)
        if token == "alignment" and tuple(self.tokens[self.pos : self.pos + 2]) == ("alignment", "of"):
            self.pop()
            self.pop()
            type_name = self.pop()
            if not RECORD_NAME_RE.fullmatch(type_name):
                raise InscriptionError(f"invalid record name '{type_name}'", self.line)
            return AlignmentOfType(type_name, self.line)
        if token == "offset" and tuple(self.tokens[self.pos : self.pos + 2]) == ("offset", "of"):
            self.pop()
            self.pop()
            field = self.pop()
            if not NAME_RE.fullmatch(field):
                raise InscriptionError(f"invalid field name '{field}'", self.line)
            if self.at_end() or self.pop() != "in":
                raise InscriptionError("offset expression must use 'in'", self.line)
            type_name = self.pop()
            if not RECORD_NAME_RE.fullmatch(type_name):
                raise InscriptionError(f"invalid record name '{type_name}'", self.line)
            return OffsetOfField(field, type_name, self.line)
        if token == "length" and tuple(self.tokens[self.pos : self.pos + 2]) == ("length", "of"):
            self.pop()
            self.pop()
            if self.peek() == "bytes" and self.pos + 1 < len(self.tokens) and _is_string_token(self.tokens[self.pos + 1]):
                self.pop()
                literal = self.pop()
                return LengthOfBytes(decode_byte_string_token(literal, self.line), self.line)
            name = self.pop()
            if not NAME_RE.fullmatch(name) or name in RESERVED:
                raise InscriptionError(f"invalid buffer name '{name}'", self.line)
            return LengthOf(name, self.line)
        if token == "read" and self.pos + 4 < len(self.tokens) and RECORD_NAME_RE.fullmatch(self.tokens[self.pos + 1]):
            return self.parse_layout_read(stop)
        if token is not None and RECORD_NAME_RE.fullmatch(token) and tuple(self.tokens[self.pos + 1 : self.pos + 2]) == ("with",):
            return self.parse_record_constructor(stop)
        if token == "comptime":
            self.pop()
            phrase_call = self.try_parse_phrase_call(stop)
            if phrase_call is None:
                raise InscriptionError("comptime must be followed by a phrase call", self.line)
            return ComptimeExpr(phrase_call, self.line)
        phrase_call = self.try_parse_phrase_call(stop)
        if phrase_call is not None:
            return phrase_call
        union_constructor = self.try_parse_union_constructor(stop)
        if union_constructor is not None:
            return union_constructor
        enum_case = self.try_parse_enum_case()
        if enum_case is not None:
            return enum_case
        token = self.pop()
        if token == "byte":
            if self.peek() is not None and _is_string_token(self.peek() or ""):
                literal = self.pop()
                values = decode_byte_string_token(literal, self.line)
                if len(values) != 1:
                    raise InscriptionError(f"byte literal must decode to exactly one byte, got {len(values)}", self.line)
                return ByteLiteral(values[0], self.line)
        if token == "bytes":
            if self.peek() is not None and _is_string_token(self.peek() or ""):
                literal = self.pop()
                decode_byte_string_token(literal, self.line)
                raise InscriptionError("byte string literal cannot be used as a value; use `array of bytes` or `buffer of bytes`", self.line)
        if token == "anything":
            raise InscriptionError("anything may only be used as a match pattern", self.line)
        if token == "ignored":
            raise InscriptionError("ignored may only be used in union payload patterns", self.line)
        if token == "check":
            raise InscriptionError("check is a step and cannot be used as an expression", self.line)
        if token == "require":
            raise InscriptionError("require is a step and cannot be used as an expression", self.line)
        if token == "write":
            raise InscriptionError("write is a step and cannot be used as an expression", self.line)
        if token == "move":
            raise InscriptionError("move may only be used as an argument to an owned buffer parameter", self.line)
        if token == "(":
            inner = self.parse_expression(stop={")"})
            if self.at_end() or self.pop() != ")":
                raise InscriptionError("missing closing ')'", self.line)
            return inner
        if token == ")":
            raise InscriptionError("unexpected token ')' in expression", self.line)
        if re.fullmatch(FLOAT_LITERAL_RE, token):
            return Float(token, self.line)
        if re.fullmatch(r"-?\d+", token):
            value = int(token)
            if not -(2**63) <= value <= 2**64 - 1:
                raise InscriptionError("integer literal is outside supported 64-bit range", self.line)
            return Integer(value, self.line)
        if token == "zero":
            return Integer(0, self.line, is_word_zero=True)
        if token == "true":
            return Boolean(True, self.line)
        if token == "false":
            return Boolean(False, self.line)
        if NAME_RE.fullmatch(token) and token not in RESERVED:
            return Variable(token, self.line)
        if RECORD_NAME_RE.fullmatch(token):
            raise InscriptionError(f"invalid token near '{token}'", self.line)
        raise InscriptionError(f"unexpected token '{token}' in expression", self.line)


    def try_parse_union_constructor(self, stop: set[str]) -> UnionConstructor | None:
        saved = self.pos
        member = self.try_parse_qualified_type_member()
        if member is None:
            return None
        type_name, variant_name = member
        if self.peek() != "with":
            self.pos = saved
            return None
        self.pop()
        if self.at_end():
            raise InscriptionError("union constructor payload is missing", self.line)
        fields: list[UnionFieldInit] = []
        while True:
            payload_name = self.pop()
            if not NAME_RE.fullmatch(payload_name):
                raise InscriptionError(f"invalid payload name '{payload_name}'", self.line)
            if self.at_end() or self.pop() != "be":
                raise InscriptionError("union constructor payload must use 'be'", self.line)
            payload_tokens = self.consume_union_payload_tokens(stop)
            if not payload_tokens:
                raise InscriptionError("union constructor payload requires an expression", self.line)
            fields.append(
                UnionFieldInit(
                    payload_name,
                    parse_expression_tokens(payload_tokens, self.line, self.phrases),
                    self.line,
                )
            )
            if not (
                self.peek() == "and"
                and self.pos + 2 < len(self.tokens)
                and NAME_RE.fullmatch(self.tokens[self.pos + 1])
                and self.tokens[self.pos + 2] == "be"
            ):
                break
            self.pop()
        return UnionConstructor(type_name, variant_name, tuple(fields), self.line)

    def try_parse_qualified_type_member(self) -> tuple[str, str] | None:
        if self.at_end():
            return None
        component_re = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
        pos = self.pos
        parts: list[str] = []
        if not component_re.fullmatch(self.tokens[pos]):
            return None
        parts.append(self.tokens[pos])
        pos += 1
        while pos + 1 < len(self.tokens) and self.tokens[pos] == "." and component_re.fullmatch(self.tokens[pos + 1]):
            pos += 1
            parts.append(self.tokens[pos])
            pos += 1
        if len(parts) < 2:
            return None
        type_name = ".".join(parts[:-1])
        member = parts[-1]
        if not QUALIFIED_RECORD_NAME_RE.fullmatch(type_name) or not NAME_RE.fullmatch(member):
            return None
        self.pos = pos
        return type_name, member

    def consume_union_payload_tokens(self, stop: set[str]) -> list[str]:
        start = self.pos
        end = self.pos
        depth = 0
        while end < len(self.tokens):
            token = self.tokens[end]
            if token == "(":
                depth += 1
            elif token == ")":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and token in stop | {",", ")"}:
                break
            elif (
                depth == 0
                and token == "and"
                and end + 2 < len(self.tokens)
                and NAME_RE.fullmatch(self.tokens[end + 1])
                and self.tokens[end + 2] == "be"
            ):
                break
            end += 1
        self.pos = end
        return self.tokens[start:end]


    def try_parse_enum_case(self) -> EnumCase | None:
        member = self.try_parse_qualified_type_member()
        if member is None:
            return None
        type_name, case_name = member
        return EnumCase(type_name, case_name, self.line)

    def parse_record_constructor(self, stop: set[str]) -> RecordConstructor:
        type_name = self.pop()
        self.pop()  # with
        fields: list[RecordFieldInit] = []
        while True:
            if self.at_end():
                raise InscriptionError("record constructor is missing a field initializer", self.line)
            field_name = self.pop()
            if not NAME_RE.fullmatch(field_name):
                raise InscriptionError(f"invalid record field '{field_name}'", self.line)
            if self.at_end() or self.pop() != "be":
                raise InscriptionError("record field initializer must use 'be'", self.line)
            expr_tokens = self.consume_record_initializer_tokens(stop)
            if not expr_tokens:
                raise InscriptionError("record field initializer requires an expression", self.line)
            fields.append(RecordFieldInit(field_name, parse_expression_tokens(expr_tokens, self.line, self.phrases), self.line))
            if self.match_sequence(("and",)):
                continue
            break
        return RecordConstructor(type_name, tuple(fields), self.line)

    def parse_layout_read(self, stop: set[str]) -> LayoutRead:
        self.pop()  # read
        type_name = self.pop()
        if self.at_end() or self.pop() != "from":
            raise InscriptionError("layout read expression must use 'from'", self.line)
        buffer_name = self.pop()
        if not NAME_RE.fullmatch(buffer_name) or buffer_name in RESERVED:
            raise InscriptionError(f"invalid buffer name '{buffer_name}'", self.line)
        if self.at_end() or self.pop() != "at":
            raise InscriptionError("layout read expression must use 'at'", self.line)
        index = self.parse_expression(stop)
        return LayoutRead(type_name, buffer_name, index, self.line)

    def consume_record_initializer_tokens(self, stop: set[str]) -> list[str]:
        start = self.pos
        end = self.pos
        depth = 0
        while end < len(self.tokens):
            token = self.tokens[end]
            if token == "(":
                depth += 1
            elif token == ")":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0:
                if token in stop or token in {",", ")"}:
                    break
                if (
                    token == "and"
                    and end + 2 < len(self.tokens)
                    and NAME_RE.fullmatch(self.tokens[end + 1])
                    and self.tokens[end + 2] == "be"
                ):
                    break
            end += 1
        self.pos = end
        return self.tokens[start:end]

    def try_parse_phrase_call(self, stop: set[str]) -> Call | None:
        for template in self.phrases:
            saved = self.pos
            try:
                args = self._match_phrase_template(template, stop)
            except InscriptionError:
                self.pos = saved
                raise
            if args is not None:
                return Call(template.symbol, tuple(args), self.line)
            self.pos = saved
        return None

    def _match_phrase_template(self, template: PhraseTemplate, stop: set[str]) -> list[Expr | MoveArg] | None:
        args: list[Expr | MoveArg] = []
        parts = template.parts
        part_index = 0
        while part_index < len(parts):
            part = parts[part_index]
            if isinstance(part, str):
                if self.at_end() or self.peek() != part:
                    return None
                self.pos += 1
                part_index += 1
                continue
            next_literals = self._next_literal_sequence(parts, part_index + 1)
            if next_literals:
                end = self._find_literal_sequence(next_literals, self.pos)
                if end is None:
                    return None
                arg_tokens = self.tokens[self.pos:end]
                self.pos = end
            else:
                end = self.pos
                depth = 0
                while end < len(self.tokens):
                    token = self.tokens[end]
                    if token == "(":
                        depth += 1
                    elif token == ")":
                        if depth == 0:
                            break
                        depth -= 1
                    elif depth == 0 and token == "and" and end + 2 < len(self.tokens) and NAME_RE.fullmatch(self.tokens[end + 1]) and self.tokens[end + 2] == "be":
                        end += 1
                        continue
                    elif depth == 0 and (token in stop or token in {",", "and", "or", "as", "is", "shifted", "bitwise"}):
                        break
                    end += 1
                arg_tokens = self.tokens[self.pos:end]
                self.pos = end
            if not arg_tokens:
                raise InscriptionError("phrase call is missing an argument", self.line)
            args.append(self._parse_call_actual(arg_tokens))
            part_index += 1
        return args

    def _parse_call_actual(self, arg_tokens: list[str]) -> Expr | MoveArg:
        if arg_tokens and arg_tokens[0] == "move":
            if len(arg_tokens) == 1:
                raise InscriptionError("move must name an owned buffer binding", self.line)
            if arg_tokens[1] == "(":
                if not _is_wrapped_by_single_parenthesized_group(arg_tokens[1:]):
                    raise InscriptionError("move expected an owned-buffer-returning phrase call", self.line)
                source = parse_expression_tokens(arg_tokens[2:-1], self.line, self.phrases)
                return MoveArg(source, self.line)
            if len(arg_tokens) > 2:
                raise InscriptionError("owned buffer phrase call in move argument must be parenthesized", self.line)
            source = parse_expression_tokens(arg_tokens[1:], self.line, self.phrases)
            return MoveArg(source, self.line)
        return parse_expression_tokens(arg_tokens, self.line, self.phrases)

    def _next_literal_sequence(self, parts: tuple[PhrasePart, ...], start: int) -> tuple[str, ...]:
        literals: list[str] = []
        for part in parts[start:]:
            if isinstance(part, PhraseHole):
                break
            literals.append(part)
        return tuple(literals)

    def _find_literal_sequence(self, literals: tuple[str, ...], start: int) -> int | None:
        if not literals:
            return None
        depth = 0
        for index in range(start, len(self.tokens) - len(literals) + 1):
            token = self.tokens[index]
            if token == "(":
                depth += 1
                continue
            if token == ")":
                depth -= 1
                continue
            if depth != 0:
                continue
            if tuple(self.tokens[index : index + len(literals)]) == literals:
                return index
        return None

    def match_sequence(self, sequence: tuple[str, ...]) -> bool:
        if tuple(self.tokens[self.pos : self.pos + len(sequence)]) == sequence:
            self.pos += len(sequence)
            return True
        return False
