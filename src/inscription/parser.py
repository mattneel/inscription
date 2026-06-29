from __future__ import annotations

import re
from dataclasses import dataclass

from .ast import (
    AssignStmt,
    Binary,
    BodyStmt,
    Boolean,
    Call,
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
    Variable,
    WhenCase,
    WhenExpr,
    WhileStmt,
)
from .diagnostics import InscriptionError

NAME_RE = re.compile(r"[a-z][a-z0-9_]*")
TOKEN_RE = re.compile(r"\s*(-?\d+|[a-z][a-z0-9_]*|[(),])")
RESERVED = {
    "address", "and", "arguments", "array", "be", "becomes", "by", "call", "divided", "do", "else", "end",
    "equal", "false", "float", "from", "function", "gives", "greater", "i1", "i32", "i64", "if", "input",
    "is", "less", "let", "memref", "minus", "no", "not", "or", "otherwise", "output", "parameters",
    "pointer", "plus", "print", "remainder", "return", "set", "takes", "than", "then", "times", "to",
    "track", "true", "when", "while", "with", "zero",
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
    indent: int


@dataclass(frozen=True)
class PhraseHole:
    name: str
    type_name: TypeName


PhrasePart = str | PhraseHole


@dataclass(frozen=True)
class PhraseTemplate:
    symbol: str
    parts: tuple[PhrasePart, ...]
    params: tuple[Parameter, ...]
    line: int


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
            body, index = self._parse_phrase_body(index + 1, template.symbol, line.number)
            functions.append(Function(template.symbol, template.params, return_type, tuple(body), line.number))
        if not functions:
            raise InscriptionError("program must contain at least one phrase definition")
        return Program(tuple(functions))

    def _looks_like_phrase_header(self, line: Line) -> bool:
        return line.is_header and re.fullmatch(r".+? gives [a-z][a-z0-9_]*", line.text) is not None

    def _parse_phrase_header(self, line: Line) -> tuple[PhraseTemplate, TypeName]:
        match = re.fullmatch(r"(.+?) gives ([a-z][a-z0-9_]*)", line.text)
        if not line.is_header or not match:
            raise InscriptionError("expected phrase definition", line.number)
        phrase_text = match.group(1).strip()
        return_type = self._type_name(match.group(2), line.number)
        template = self._parse_phrase_template(phrase_text, line.number)
        return template, return_type

    def _parse_phrase_template(self, text: str, line: int) -> PhraseTemplate:
        parts: list[PhrasePart] = []
        params: list[Parameter] = []
        param_names: set[str] = set()
        pos = 0
        holes = list(re.finditer(r"\b([a-z][a-z0-9_]*):\s*([a-z][a-z0-9_]*)\b", text))
        for match in holes:
            self._append_literal_parts(parts, text[pos : match.start()], line)
            name = self._name(match.group(1), line)
            type_name = self._type_name(match.group(2), line)
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

    def _parse_phrase_body(self, index: int, name: str, line: int) -> tuple[list[BodyStmt | ReturnStmt], int]:
        body_items: list[BodyStmt] = []
        value_lines: list[Line] = []
        while index < len(self.lines):
            current = self.lines[index]
            if self._looks_like_phrase_header(current):
                break
            if self._is_body_item_start(current):
                if value_lines:
                    if current.text.startswith("let "):
                        raise InscriptionError("let bindings must appear before the value block", current.number)
                    raise InscriptionError("body items must appear before the value block", current.number)
                item, index = self._parse_body_item(index, in_while=False)
                body_items.append(item)
            else:
                if current.is_header:
                    raise InscriptionError("unexpected ':' inside phrase body", current.number)
                value_lines.append(current)
                index += 1
        if not value_lines:
            raise InscriptionError(f"phrase '{name}' must evaluate to a value", line)
        return [*body_items, ReturnStmt(self._parse_value_block(value_lines), value_lines[-1].number)], index

    def _is_body_item_start(self, line: Line) -> bool:
        return (
            line.text.startswith("let ")
            or line.text.startswith("track ")
            or self._assignment_match(line) is not None
            or (line.is_header and line.text.startswith("if "))
            or (line.is_header and line.text.startswith("while "))
        )

    def _parse_body_item(self, index: int, *, in_while: bool) -> tuple[BodyStmt, int]:
        current = self.lines[index]
        if current.text.startswith("let "):
            return self._parse_let(current), index + 1
        if current.text.startswith("track "):
            raise InscriptionError("`track` is not valid Inscription syntax; use `let name be ...`", current.number)
        assignment = self._assignment_match(current)
        if assignment is not None:
            return self._parse_assignment(current, assignment), index + 1
        if current.is_header and current.text.startswith("if "):
            return self._parse_if(index)
        if current.is_header and current.text.startswith("while "):
            return self._parse_while(index)
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
            if not self._is_body_item_start(current):
                raise InscriptionError(f"{name} only supports let bindings, assignments, while loops, and if blocks", current.number)
            item, body_index = self._parse_body_item(body_index, in_while=True)
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

    def _parse_let(self, line: Line) -> SetStmt:
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

    def _parse_assignment(self, line: Line, match: re.Match[str]) -> AssignStmt:
        return AssignStmt(
            self._name(match.group(1), line.number),
            self._parse_expression(match.group(2), line.number),
            line.number,
        )

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

    def _type_name(self, value: str, line: int) -> TypeName:
        if value in {"i1", "i32", "i64"}:
            return value  # type: ignore[return-value]
        raise InscriptionError("v0 phrase definitions only support i1, i32, and i64", line)


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
    PRECEDENCE = {"plus": 10, "minus": 10, "times": 20, "divided by": 20, "remainder": 20}

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
        left = self.parse_arithmetic(comparison_stop)
        if self.at_end() or self.peek() != "is" or "is" in stop:
            return left
        self.pop()
        rest = self.tokens[self.pos :]
        for phrase, predicate in COMPARATORS:
            phrase_len = len(phrase)
            if tuple(rest[:phrase_len]) == phrase:
                self.pos += phrase_len
                right = self.parse_arithmetic(comparison_stop)
                return Comparison(predicate, left, right, self.line)
        raise InscriptionError("unsupported comparison operator", self.line)

    def parse_arithmetic(self, stop: set[str], min_prec: int = 0) -> Expr:
        left = self.parse_unary(stop)
        while not self.at_end():
            token = self.peek()
            if token in stop or token in {",", ")", "is", "and", "or"}:
                break
            operator = self.peek_operator()
            if operator is None:
                if token == "divided":
                    raise InscriptionError("operator 'divided' must be followed by 'by'", self.line)
                break
            op, prec, width = operator
            if prec < min_prec:
                break
            self.pos += width
            right = self.parse_arithmetic(stop, prec + 1)
            left = Binary(op, left, right, self.line)  # type: ignore[arg-type]
        return left

    def parse_unary(self, stop: set[str]) -> Expr:
        if self.peek() == "not" and "not" not in stop:
            self.pop()
            return Unary("not", self.parse_unary(stop), self.line)
        return self.parse_primary(stop)

    def peek_operator(self) -> tuple[str, int, int] | None:
        token = self.peek()
        if token == "divided":
            if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1] == "by":
                return "divided by", self.PRECEDENCE["divided by"], 2
            return None
        if token in {"plus", "minus", "times", "remainder"}:
            return token, self.PRECEDENCE[token], 1
        return None

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
            if not -(2**63) <= value <= 2**63 - 1:
                raise InscriptionError("integer literal is outside signed 64-bit range", self.line)
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
                    elif depth == 0 and (token in stop or token in {",", "and", "or"}):
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
