from __future__ import annotations

import re
from dataclasses import dataclass

from .ast import (
    AssignStmt,
    Binary,
    BodyStmt,
    Boolean,
    BufferBinding,
    BufferLoad,
    BufferStoreStmt,
    BufferType,
    Call,
    CallStmt,
    Cast,
    Comparison,
    Expr,
    Function,
    IfStmt,
    Integer,
    Parameter,
    Program,
    ReturnStmt,
    SetStmt,
    TypeName,
    Unary,
    ValueType,
    Variable,
    WhenCase,
    WhenExpr,
    WhileStmt,
)
from .diagnostics import InscriptionError

NAME_RE = re.compile(r"[a-z][a-z0-9_]*")
TOKEN_RE = re.compile(r"\s*(-?\d+|[a-z][a-z0-9_]*|[(),])")
RESERVED = {
    "address", "and", "arguments", "array", "as", "at", "be", "becomes", "bitwise", "buffer", "by", "call",
    "divided", "do", "does", "else", "end", "equal", "false", "filled", "float", "from", "function", "gives",
    "greater", "i1", "i32", "i64", "if", "input",
    "i8", "i16", "is", "less", "let", "memref", "minus", "no", "not", "or", "otherwise", "output", "parameters",
    "pointer", "plus", "print", "remainder", "return", "set", "shifted", "takes", "than", "then", "times", "to",
    "track", "true", "u8", "u16", "u32", "u64", "when", "while", "with", "xor", "zero",
}
TYPE_NAMES: set[str] = {"i1", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"}
COMPARATORS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("equal", "to"), "eq"),
    (("not", "equal", "to"), "ne"),
    (("less", "than", "or", "equal", "to"), "sle"),
    (("less", "than"), "slt"),
    (("greater", "than", "or", "equal", "to"), "sge"),
    (("greater", "than"), "sgt"),
)
CONNECTOR_WORDS = {"of", "from", "to", "at", "in", "into", "between", "and", "with", "by"}


def parse_source(source: str) -> Program:
    return Parser(source).parse_program()


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
    return_type: TypeName | None
    display_name: str


class Parser:
    def __init__(self, source: str):
        self.lines = self._preprocess(source)
        self.phrases = self._collect_phrase_templates()

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
            if not self._looks_like_phrase_header(line):
                continue
            template, _return_type = self._parse_phrase_header(line)
            templates.append(template)
        return tuple(sorted(templates, key=lambda template: len(template.parts), reverse=True))

    def parse_program(self) -> Program:
        functions: list[Function] = []
        index = 0
        while index < len(self.lines):
            line = self.lines[index]
            if not self._looks_like_phrase_header(line):
                raise InscriptionError("expected phrase definition", line.number)
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
        if not functions:
            raise InscriptionError("program must contain at least one phrase definition")
        return Program(tuple(functions))

    def _looks_like_phrase_header(self, line: Line) -> bool:
        return line.is_header and re.fullmatch(r".+? (?:gives [a-z][a-z0-9_]*|does)", line.text) is not None

    def _parse_phrase_header(self, line: Line) -> tuple[PhraseTemplate, TypeName | None]:
        match = re.fullmatch(r"(.+?) (?:gives ([a-z][a-z0-9_]*)|does)", line.text)
        if not line.is_header or not match:
            raise InscriptionError("expected phrase definition", line.number)
        phrase_text = match.group(1).strip()
        return_type = self._type_name(match.group(2), line.number) if match.group(2) is not None else None
        template = self._parse_phrase_template(phrase_text, line.number, return_type)
        return template, return_type

    def _parse_phrase_template(self, text: str, line: int, return_type: TypeName | None) -> PhraseTemplate:
        parts: list[PhrasePart] = []
        params: list[Parameter] = []
        param_names: set[str] = set()
        pos = 0
        holes = list(
            re.finditer(
                r"\b([a-z][a-z0-9_]*):\s*(buffer\s+of\s+-?\d+\s+[a-z][a-z0-9_]*|[a-z][a-z0-9_]*)\b",
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
            if self._looks_like_phrase_header(current):
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
            if self._looks_like_phrase_header(current):
                break
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
            raise InscriptionError(f"phrase '{name}' must evaluate to a value", line)
        return [*body_items, ReturnStmt(self._parse_value_block(value_lines), value_lines[-1].number)], index

    def _is_gives_body_item_start(self, line: Line, index: int) -> bool:
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
            if self._looks_like_phrase_header(current):
                return False
            if current.indent < indent:
                return False
            return True
        return False

    def _is_body_item_start(self, line: Line, *, include_phrase_calls: bool) -> bool:
        return (
            line.text.startswith("let ")
            or line.text.startswith("track ")
            or self._buffer_store_match(line) is not None
            or self._assignment_match(line) is not None
            or (line.is_header and line.text.startswith("if "))
            or (line.is_header and line.text.startswith("while "))
            or (include_phrase_calls and self._parse_phrase_call_expr(line) is not None)
        )

    def _parse_body_item(self, index: int, *, include_phrase_calls: bool) -> tuple[BodyStmt, int]:
        current = self.lines[index]
        if current.text.startswith("let "):
            return self._parse_let(current), index + 1
        if current.text.startswith("track "):
            raise InscriptionError("`track` is not valid Inscription syntax; use `let name be ...`", current.number)
        buffer_store = self._buffer_store_match(current)
        if buffer_store is not None:
            return self._parse_buffer_store(current, buffer_store), index + 1
        assignment = self._assignment_match(current)
        if assignment is not None:
            return self._parse_assignment(current, assignment), index + 1
        if current.is_header and current.text.startswith("if "):
            return self._parse_if(index)
        if current.is_header and current.text.startswith("while "):
            return self._parse_while(index)
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
            if self._looks_like_phrase_header(current):
                raise InscriptionError(f"phrase definitions cannot appear inside {name}", current.number)
            if not self._is_body_item_start(current, include_phrase_calls=True):
                raise InscriptionError(
                    f"{name} only supports let bindings, assignments, phrase calls, while loops, and if blocks",
                    current.number,
                )
            item, body_index = self._parse_body_item(body_index, include_phrase_calls=True)
            body.append(item)
        return body, body_index

    def _parse_value_block(self, lines: list[Line]) -> Expr:
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

    def _parse_let(self, line: Line) -> SetStmt | BufferBinding:
        buffer_match = re.fullmatch(
            r"let ([a-z][a-z0-9_]*) be buffer of (-?\d+) ([a-z][a-z0-9_]*) filled with (.+)",
            line.text,
        )
        if buffer_match:
            length = int(buffer_match.group(2))
            return BufferBinding(
                self._name(buffer_match.group(1), line.number),
                BufferType(length, self._type_name(buffer_match.group(3), line.number)),
                self._parse_expression(buffer_match.group(4), line.number),
                line.number,
            )
        match = re.fullmatch(r"let ([a-z][a-z0-9_]*)(?::\s*([a-z][a-z0-9_]*))? be (.+)", line.text)
        if not match:
            raise InscriptionError("malformed let binding", line.number)
        return SetStmt(
            self._name(match.group(1), line.number),
            self._type_name(match.group(2), line.number) if match.group(2) is not None else None,
            self._parse_expression(match.group(3), line.number),
            line.number,
        )

    def _assignment_match(self, line: Line) -> re.Match[str] | None:
        if line.is_header:
            return None
        return re.fullmatch(r"([a-z][a-z0-9_]*) becomes (.+)", line.text)

    def _buffer_store_match(self, line: Line) -> re.Match[str] | None:
        if line.is_header:
            return None
        return re.fullmatch(r"([a-z][a-z0-9_]*) at (.+) becomes (.+)", line.text)

    def _parse_assignment(self, line: Line, match: re.Match[str]) -> AssignStmt:
        return AssignStmt(
            self._name(match.group(1), line.number),
            self._parse_expression(match.group(2), line.number),
            line.number,
        )

    def _parse_buffer_store(self, line: Line, match: re.Match[str]) -> BufferStoreStmt:
        return BufferStoreStmt(
            self._name(match.group(1), line.number),
            self._parse_expression(match.group(2), line.number),
            self._parse_expression(match.group(3), line.number),
            line.number,
        )

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

    def _value_type(self, value: str, line: int) -> ValueType:
        value = " ".join(value.split())
        buffer_match = re.fullmatch(r"buffer of (-?\d+) ([a-z][a-z0-9_]*)", value)
        if buffer_match is not None:
            return BufferType(int(buffer_match.group(1)), self._type_name(buffer_match.group(2), line))
        return self._type_name(value, line)

    def _type_name(self, value: str, line: int) -> TypeName:
        if value in TYPE_NAMES:
            return value  # type: ignore[return-value]
        raise InscriptionError("supported scalar types are i1, i8, i16, i32, i64, u8, u16, u32, and u64", line)


def tokenize(text: str, line: int) -> list[str]:
    tokens: list[str] = []
    pos = 0
    while pos < len(text):
        match = TOKEN_RE.match(text, pos)
        if not match:
            if text[pos:].strip() == "":
                break
            raise InscriptionError(f"invalid token near '{text[pos:].strip()}'", line)
        token_start = match.start(1)
        token = match.group(1).lower()
        punctuation = {",", "(", ")"}
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
                type_token = self.pop()
                if type_token not in TYPE_NAMES:
                    raise InscriptionError(f"unknown cast target type '{type_token}'", self.line)
                expr = Cast(expr, type_token, self.line)  # type: ignore[arg-type]
                continue
            break
        return expr

    def parse_primary(self, stop: set[str]) -> Expr:
        token = self.peek()
        if token is None or token in stop or token == ",":
            raise InscriptionError("expected expression", self.line)
        phrase_call = self.try_parse_phrase_call(stop)
        if phrase_call is not None:
            return phrase_call
        token = self.pop()
        if token == "(":
            inner = self.parse_expression(stop={")"})
            if self.at_end() or self.pop() != ")":
                raise InscriptionError("missing closing ')'", self.line)
            return inner
        if token == ")":
            raise InscriptionError("unexpected token ')' in expression", self.line)
        if re.fullmatch(r"-?\d+", token):
            value = int(token)
            if not -(2**63) <= value <= 2**64 - 1:
                raise InscriptionError("integer literal is outside supported 64-bit range", self.line)
            return Integer(value, self.line)
        if token == "zero":
            return Integer(0, self.line)
        if token == "true":
            return Boolean(True, self.line)
        if token == "false":
            return Boolean(False, self.line)
        if NAME_RE.fullmatch(token) and token not in RESERVED:
            return Variable(token, self.line)
        raise InscriptionError(f"unexpected token '{token}' in expression", self.line)

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
