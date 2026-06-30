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
    ConstantDecl,
    EnumCase,
    EnumCaseDecl,
    EnumDecl,
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
    LengthOf,
    LengthOfBytes,
    LayoutRead,
    LayoutWriteStmt,
    MatchExpr,
    MatchExprArm,
    MatchStep,
    MatchStepArm,
    OffsetOfField,
    Parameter,
    Program,
    RecordConstructor,
    RecordDecl,
    RecordFieldDecl,
    RecordFieldInit,
    RecordType,
    RequireStmt,
    ReturnType,
    ReturnStmt,
    SetStmt,
    SizeOfType,
    StorageAliasBinding,
    StorageElement,
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
    "address", "alignment", "and", "arguments", "array", "as", "at", "be", "becomes", "bitwise", "buffer", "by", "call",
    "check", "constant", "containing", "divided", "do", "does", "each", "else", "equal", "export", "extern", "false", "filled", "float", "for", "from",
    "enum", "function", "gives", "greater", "f32", "f64", "i1", "i32", "i64", "if", "in", "index", "input", "into", "import",
    "i8", "i16", "is", "layout", "length", "less", "let", "match", "memref", "minus", "module", "no", "not", "or", "otherwise", "output", "packed", "parameters",
    "pointer", "plus", "print", "read", "remainder", "require", "return", "set", "shifted", "size", "takes", "than", "then", "times", "to",
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


ParsedTopLevel = RecordDecl | EnumDecl | UnionDecl | TypeAliasDecl | ConstantDecl | CheckStmt | Function


class Parser:
    def __init__(
        self,
        source: str,
        *,
        external_phrases: tuple[PhraseTemplate, ...] = (),
        symbol_prefix: str | None = None,
    ):
        self.lines = self._preprocess(source)
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
        imports: list[ImportDecl] = []
        module_name: str | None = None
        index = 0
        while index < len(self.lines):
            line = self.lines[index]
            if line.indent == 0 and line.text.startswith("module "):
                if line.is_header:
                    raise InscriptionError("malformed module declaration", line.number)
                if module_name is not None:
                    raise InscriptionError("program can declare only one module", line.number)
                module_name = self._module_name(line.text[len("module ") :].strip(), line.number)
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
                    )
                )
                continue
            if line.text.startswith("require "):
                raise InscriptionError("require may only appear inside phrase bodies", line.number)
            if not self._looks_like_phrase_header(line):
                raise InscriptionError("expected phrase definition, record declaration, enum declaration, union declaration, type alias, constant declaration, check, extern, export, module, or import", line.number)
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
                )
            )
        seen_imports: set[str] = set()
        for imported in imports:
            if imported.module in seen_imports:
                raise InscriptionError(f"module {imported.module} is already imported", imported.line)
            seen_imports.add(imported.module)
        return Program(tuple(records), tuple(enums), tuple(unions), tuple(type_aliases), tuple(constants), tuple(checks), tuple(functions), module_name, tuple(imports))

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

    def _looks_like_top_level_item(self, line: Line) -> bool:
        return (
            self._looks_like_phrase_header(line)
            or self._looks_like_record_header(line)
            or self._looks_like_enum_header(line)
            or self._looks_like_union_header(line)
            or (line.indent == 0 and (line.text.startswith("constant ") or line.text.startswith("check ") or line.text.startswith("extern ") or line.text.startswith("export ") or line.text.startswith("module ") or line.text.startswith("import ") or line.text.startswith("require ") or line.text.startswith("enum ") or line.text.startswith("union ") or line.text.startswith("type ")))
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
        return RecordDecl(name, tuple(fields), line.number, layout_kind), field_index

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
        return EnumDecl(name, underlying_type, tuple(cases), line.number), case_index

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
        return UnionDecl(name, tuple(variants), line.number), variant_index

    def _parse_type_alias_decl(self, line: Line) -> TypeAliasDecl:
        match = re.fullmatch(rf"type ([A-Za-z][A-Za-z0-9_]*) be ({TYPE_PATTERN})", line.text)
        if line.is_header or match is None:
            raise InscriptionError("malformed type alias declaration", line.number)
        return TypeAliasDecl(
            self._record_name(match.group(1), line.number),
            self._value_type(match.group(2), line.number),
            line.number,
        )

    def _parse_constant_decl(self, line: Line) -> ConstantDecl:
        match = re.fullmatch(rf"constant ([A-Za-z][A-Za-z0-9_]*):\s*({TYPE_PATTERN}) be (.+)", line.text)
        if line.is_header or match is None:
            raise InscriptionError("malformed constant declaration", line.number)
        raw_name = match.group(1)
        name = self._name(raw_name, line.number) if NAME_RE.fullmatch(raw_name) else raw_name
        return ConstantDecl(name, self._return_type(match.group(2), line.number), self._parse_expression(match.group(3), line.number), line.number)

    def _parse_constant_match_decl(self, index: int) -> tuple[ConstantDecl, int]:
        line = self.lines[index]
        match = re.fullmatch(rf"constant ([A-Za-z][A-Za-z0-9_]*):\s*({TYPE_PATTERN}) be match (.+)", line.text)
        if not line.is_header or match is None:
            raise InscriptionError("malformed constant declaration", line.number)
        raw_name = match.group(1)
        name = self._name(raw_name, line.number) if NAME_RE.fullmatch(raw_name) else raw_name
        expr, next_index = self._parse_match_expression(index, scrutinee_text=match.group(3))
        return ConstantDecl(name, self._return_type(match.group(2), line.number), expr, line.number), next_index

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
            rf"extern (.+?) gives ({TYPE_PATTERN}) as ({EXTERNAL_SYMBOL_PATTERN})",
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
            rf"export (.+?) gives ({TYPE_PATTERN}) as ({EXTERNAL_SYMBOL_PATTERN})",
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
                rf"\b([a-z][a-z0-9_]*):\s*({TYPE_PATTERN})\b",
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
        return (not first_child.is_header) and (" gives " in first_child.text or first_child.text.startswith("otherwise gives "))

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
            arms.append(
                MatchExprArm(
                    self._parse_pattern(pattern_text.strip(), current.number),
                    self._parse_expression(expr_text.strip(), current.number),
                    current.number,
                )
            )
            current_index += 1
        if otherwise is None:
            raise InscriptionError("match expression requires otherwise", header.number)
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
            arms.append(MatchStepArm(self._parse_pattern(current.text, current.number), tuple(body), current.number))
            current_index = next_index
        if otherwise_body is None:
            raise InscriptionError("match block requires otherwise", header.number)
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

    def _parse_let(self, line: Line) -> SetStmt | BufferBinding | ArrayBinding | StorageAliasBinding | ViewBinding:
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
        match = re.fullmatch(r"((?:[A-Za-z][A-Za-z0-9_]*\.)*[A-Z][A-Za-z0-9_]*)\.([a-z][a-z0-9_]*)(?: with (.+))?", text.strip())
        if match is not None and match.group(3) is not None:
            bindings: list[UnionPatternBinding] = []
            for binding_text in match.group(3).split(" and "):
                binding_match = re.fullmatch(r"([a-z][a-z0-9_]*)(?: as ([a-z][a-z0-9_]*))?", binding_text.strip())
                if binding_match is None:
                    raise InscriptionError("malformed union pattern", line)
                bindings.append(
                    UnionPatternBinding(
                        self._field_name(binding_match.group(1), line),
                        None if binding_match.group(2) is None else self._field_name(binding_match.group(2), line),
                        line,
                    )
                )
            return UnionPattern(match.group(1), self._field_name(match.group(2), line), tuple(bindings), line)
        return self._parse_expression(text, line)

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
        if token == "check":
            raise InscriptionError("check is a step and cannot be used as an expression", self.line)
        if token == "require":
            raise InscriptionError("require is a step and cannot be used as an expression", self.line)
        if token == "write":
            raise InscriptionError("write is a step and cannot be used as an expression", self.line)
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

    def _match_phrase_template(self, template: PhraseTemplate, stop: set[str]) -> list[Expr] | None:
        args: list[Expr] = []
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
            args.append(parse_expression_tokens(arg_tokens, self.line, self.phrases))
            part_index += 1
        return args

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
