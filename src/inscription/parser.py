from __future__ import annotations

import re
from dataclasses import dataclass

from .ast import Binary, Call, Comparison, Expr, Function, Integer, Program, ReturnStmt, SetStmt, Variable, WhenCase, WhenExpr
from .diagnostics import InscriptionError

NAME_RE = re.compile(r"[a-z][a-z0-9_]*")
TOKEN_RE = re.compile(r"\s*(-?\d+|[a-z][a-z0-9_]*|,)")
RESERVED = {
    "address", "and", "arguments", "array", "be", "call", "do", "else", "end", "equal", "float",
    "function", "gives", "greater", "i32", "if", "input", "is", "less", "let", "memref", "minus",
    "no", "not", "or", "otherwise", "output", "parameters", "pointer", "plus", "print", "return",
    "set", "takes", "than", "then", "times", "to", "when", "while", "with", "zero",
}
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


@dataclass(frozen=True)
class PhraseHole:
    name: str
    type_name: str


PhrasePart = str | PhraseHole


@dataclass(frozen=True)
class PhraseTemplate:
    symbol: str
    parts: tuple[PhrasePart, ...]
    params: tuple[str, ...]
    line: int


class Parser:
    def __init__(self, source: str):
        self.lines = self._preprocess(source)
        self.phrases = self._collect_phrase_templates()

    def _preprocess(self, source: str) -> list[Line]:
        lines: list[Line] = []
        for number, raw in enumerate(source.splitlines(), start=1):
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
            lines.append(Line(number, body, is_header))
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
            template, _return_type = self._parse_phrase_header(line)
            body, index = self._parse_phrase_body(index + 1, template.symbol, line.number)
            functions.append(Function(template.symbol, template.params, tuple(body), line.number))
        if not functions:
            raise InscriptionError("program must contain at least one phrase definition")
        return Program(tuple(functions))

    def _looks_like_phrase_header(self, line: Line) -> bool:
        return line.is_header and re.fullmatch(r".+? gives [a-z][a-z0-9_]*", line.text) is not None

    def _parse_phrase_header(self, line: Line) -> tuple[PhraseTemplate, str]:
        match = re.fullmatch(r"(.+?) gives ([a-z][a-z0-9_]*)", line.text)
        if not line.is_header or not match:
            raise InscriptionError("expected phrase definition", line.number)
        phrase_text = match.group(1).strip()
        return_type = match.group(2)
        if return_type != "i32":
            raise InscriptionError("v0 phrase definitions only support i32 return values", line.number)
        template = self._parse_phrase_template(phrase_text, line.number)
        return template, return_type

    def _parse_phrase_template(self, text: str, line: int) -> PhraseTemplate:
        parts: list[PhrasePart] = []
        params: list[str] = []
        pos = 0
        holes = list(re.finditer(r"\b([a-z][a-z0-9_]*):\s*([a-z][a-z0-9_]*)\b", text))
        for match in holes:
            self._append_literal_parts(parts, text[pos : match.start()], line)
            name = self._name(match.group(1), line)
            type_name = match.group(2)
            if type_name != "i32":
                raise InscriptionError("v0 phrase holes only support i32", line)
            if name in params:
                raise InscriptionError(f"duplicate parameter '{name}'", line)
            params.append(name)
            parts.append(PhraseHole(name, type_name))
            pos = match.end()
        self._append_literal_parts(parts, text[pos:], line)
        if not parts or all(isinstance(part, PhraseHole) for part in parts):
            raise InscriptionError("phrase definition must include literal words", line)
        symbol = self._phrase_symbol(parts, line)
        return PhraseTemplate(symbol, tuple(parts), tuple(params), line)

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

    def _parse_phrase_body(self, index: int, name: str, line: int) -> tuple[list[SetStmt | ReturnStmt], int]:
        lets: list[SetStmt] = []
        value_lines: list[Line] = []
        while index < len(self.lines):
            current = self.lines[index]
            if self._looks_like_phrase_header(current):
                break
            if current.is_header:
                raise InscriptionError("unexpected ':' inside phrase body", current.number)
            if current.text.startswith("let "):
                if value_lines:
                    raise InscriptionError("let bindings must appear before the value block", current.number)
                lets.append(self._parse_let(current))
            else:
                value_lines.append(current)
            index += 1
        if not value_lines:
            raise InscriptionError(f"phrase '{name}' must evaluate to a value", line)
        return [*lets, ReturnStmt(self._parse_value_block(value_lines), value_lines[-1].number)], index

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
                        self._parse_comparison(condition_text, line.number),
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

    def _parse_let(self, line: Line) -> SetStmt:
        match = re.fullmatch(r"let ([a-z][a-z0-9_]*) be (.+)", line.text)
        if not match:
            raise InscriptionError("malformed let binding", line.number)
        return SetStmt(self._name(match.group(1), line.number), self._parse_expression(match.group(2), line.number), line.number)

    def _parse_expression(self, text: str, line: int) -> Expr:
        return parse_expression(text, line, self.phrases)

    def _parse_comparison(self, text: str, line: int) -> Comparison:
        return parse_comparison(text, line, self.phrases)

    def _name(self, value: str, line: int) -> str:
        if not NAME_RE.fullmatch(value):
            raise InscriptionError(f"invalid identifier '{value}'", line)
        if value in RESERVED:
            raise InscriptionError(f"reserved word '{value}' cannot be an identifier", line)
        return value


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
        if tokens and token_start == pos and tokens[-1] != "," and token != ",":
            raise InscriptionError("missing whitespace between expression tokens", line)
        tokens.append(token)
        pos = match.end()
    if not tokens:
        raise InscriptionError("expected expression", line)
    return tokens


def parse_expression(text: str, line: int, phrases: tuple[PhraseTemplate, ...] = ()) -> Expr:
    parser = ExpressionParser(tokenize(text, line), line, phrases)
    expr = parser.parse_expression()
    if not parser.at_end():
        raise InscriptionError(f"unexpected token '{parser.peek()}' in expression", line)
    return expr


def parse_expression_tokens(tokens: list[str], line: int, phrases: tuple[PhraseTemplate, ...] = ()) -> Expr:
    parser = ExpressionParser(tokens, line, phrases)
    expr = parser.parse_expression()
    if not parser.at_end():
        raise InscriptionError(f"unexpected token '{parser.peek()}' in expression", line)
    return expr


def parse_comparison(text: str, line: int, phrases: tuple[PhraseTemplate, ...] = ()) -> Comparison:
    tokens = tokenize(text, line)
    try:
        is_index = tokens.index("is")
    except ValueError as exc:
        raise InscriptionError("comparison must contain 'is'", line) from exc
    left_tokens = tokens[:is_index]
    rest = tokens[is_index + 1 :]
    if not left_tokens or not rest:
        raise InscriptionError("malformed comparison", line)
    for phrase, predicate in COMPARATORS:
        phrase_len = len(phrase)
        if tuple(rest[:phrase_len]) == phrase:
            right_tokens = rest[phrase_len:]
            if not right_tokens:
                raise InscriptionError("comparison is missing right-hand expression", line)
            return Comparison(
                predicate,
                parse_expression_tokens(left_tokens, line, phrases),
                parse_expression_tokens(right_tokens, line, phrases),
                line,
            )
    raise InscriptionError("unsupported comparison operator", line)


class ExpressionParser:
    PRECEDENCE = {"plus": 10, "minus": 10, "times": 20}

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

    def parse_expression(self, min_prec: int = 0, stop: set[str] | None = None) -> Expr:
        stop = stop or set()
        left = self.parse_primary(stop)
        while not self.at_end():
            token = self.peek()
            if token in stop or token == ",":
                break
            prec = self.PRECEDENCE.get(token or "")
            if prec is None or prec < min_prec:
                break
            op = self.pop()
            right = self.parse_expression(prec + 1, stop)
            left = Binary(op, left, right, self.line)  # type: ignore[arg-type]
        return left

    def parse_primary(self, stop: set[str]) -> Expr:
        token = self.peek()
        if token is None or token in stop or token == ",":
            raise InscriptionError("expected expression", self.line)
        phrase_call = self.try_parse_phrase_call(stop)
        if phrase_call is not None:
            return phrase_call
        token = self.pop()
        if re.fullmatch(r"-?\d+", token):
            value = int(token)
            if not -(2**31) <= value <= 2**31 - 1:
                raise InscriptionError("integer literal is outside signed i32 range", self.line)
            return Integer(value, self.line)
        if token == "zero":
            return Integer(0, self.line)
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
                while end < len(self.tokens) and self.tokens[end] not in stop and self.tokens[end] != ",":
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
        for index in range(start, len(self.tokens) - len(literals) + 1):
            if tuple(self.tokens[index : index + len(literals)]) == literals:
                return index
        return None
