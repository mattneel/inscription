from __future__ import annotations

import re
from dataclasses import dataclass

from .ast import (
    Binary,
    Call,
    Comparison,
    Expr,
    Function,
    IfStmt,
    Integer,
    Program,
    ReturnStmt,
    SetStmt,
    Stmt,
    Variable,
    WhileStmt,
)
from .diagnostics import InscriptionError

NAME_RE = re.compile(r"[a-z][a-z0-9_]*")
TOKEN_RE = re.compile(r"\s*(-?\d+|[a-z][a-z0-9_]*|,)")
RESERVED = {
    "address", "and", "arguments", "array", "call", "do", "else", "end", "equal", "float",
    "function", "greater", "if", "input", "is", "less", "memref", "minus",
    "no", "not", "or", "otherwise", "output", "parameters", "pointer",
    "plus", "print", "return", "set", "takes", "than", "then", "times",
    "to", "while", "with",
}
COMPARATORS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("equal", "to"), "eq"),
    (("not", "equal", "to"), "ne"),
    (("less", "than", "or", "equal", "to"), "sle"),
    (("less", "than"), "slt"),
    (("greater", "than", "or", "equal", "to"), "sge"),
    (("greater", "than"), "sgt"),
)


def parse_source(source: str) -> Program:
    return Parser(source).parse_program()


@dataclass(frozen=True)
class Line:
    number: int
    text: str


class Parser:
    def __init__(self, source: str):
        self.lines = self._preprocess(source)

    def _preprocess(self, source: str) -> list[Line]:
        lines: list[Line] = []
        for number, raw in enumerate(source.splitlines(), start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            if not stripped.endswith("."):
                raise InscriptionError("expected every nonblank line to end with '.'", number)
            body = stripped[:-1].strip()
            if not body:
                raise InscriptionError("empty sentence is not valid syntax", number)
            lines.append(Line(number, body))
        return lines

    def parse_program(self) -> Program:
        functions: list[Function] = []
        index = 0
        while index < len(self.lines):
            line = self.lines[index]
            match = re.fullmatch(r"Function ([a-z][a-z0-9_]*) takes (.+)", line.text)
            if not match:
                raise InscriptionError("expected function definition", line.number)
            name = self._name(match.group(1), line.number)
            params = self._parse_name_list(match.group(2), line.number, none_phrase="no parameters")
            body, index, term = self._parse_block(index + 1, {"End function"})
            if term != "End function":
                raise InscriptionError(f"function '{name}' is missing 'End function.'", line.number)
            functions.append(Function(name, tuple(params), tuple(body), line.number))
            index += 1
        if not functions:
            raise InscriptionError("program must contain at least one function")
        return Program(tuple(functions))

    def _parse_block(self, index: int, terminators: set[str]) -> tuple[list[Stmt], int, str | None]:
        statements: list[Stmt] = []
        while index < len(self.lines):
            line = self.lines[index]
            text = line.text
            if text in terminators:
                return statements, index, text
            if text.startswith("Set "):
                statements.append(self._parse_set(line))
                index += 1
            elif text.startswith("Return "):
                statements.append(self._parse_return(line))
                index += 1
            elif text.startswith("While "):
                condition_text = self._match_statement(line, r"While (.+) do")
                body, index, term = self._parse_block(index + 1, {"End while"})
                if term != "End while":
                    raise InscriptionError("while block is missing 'End while.'", line.number)
                statements.append(WhileStmt(parse_comparison(condition_text, line.number), tuple(body), line.number))
                index += 1
            elif text.startswith("If "):
                condition_text = self._match_statement(line, r"If (.+) then")
                then_body, index, term = self._parse_block(index + 1, {"Otherwise", "End if"})
                if term == "End if":
                    raise InscriptionError("if block requires 'Otherwise.' before 'End if.'", line.number)
                if term != "Otherwise":
                    raise InscriptionError("if block is missing 'Otherwise.'", line.number)
                else_body, index, term = self._parse_block(index + 1, {"End if"})
                if term != "End if":
                    raise InscriptionError("if block is missing 'End if.'", line.number)
                statements.append(IfStmt(parse_comparison(condition_text, line.number), tuple(then_body), tuple(else_body), line.number))
                index += 1
            elif text in {"End function", "End while", "End if", "Otherwise"}:
                return statements, index, text
            else:
                raise InscriptionError("unsupported or malformed sentence pattern", line.number)
        return statements, index, None

    def _parse_set(self, line: Line) -> SetStmt:
        match = re.fullmatch(r"Set ([a-z][a-z0-9_]*) to (.+)", line.text)
        if not match:
            raise InscriptionError("malformed set statement", line.number)
        return SetStmt(self._name(match.group(1), line.number), parse_expression(match.group(2), line.number), line.number)

    def _parse_return(self, line: Line) -> ReturnStmt:
        expr_text = self._match_statement(line, r"Return (.+)")
        return ReturnStmt(parse_expression(expr_text, line.number), line.number)

    def _match_statement(self, line: Line, pattern: str) -> str:
        match = re.fullmatch(pattern, line.text)
        if not match:
            raise InscriptionError("malformed sentence pattern", line.number)
        return match.group(1)

    def _parse_name_list(self, text: str, line: int, none_phrase: str) -> list[str]:
        text = text.strip()
        if text == none_phrase:
            return []
        if "," not in text:
            if text.count(" and ") > 1:
                raise InscriptionError("malformed name list", line)
            parts = text.split(" and ") if " and " in text else [text]
        elif ", and " in text:
            head, tail = text.rsplit(", and ", 1)
            if "," not in head or "," in tail or " and " in head or " and " in tail:
                raise InscriptionError("malformed name list", line)
            parts = [*head.split(","), tail]
        else:
            if " and " in text:
                raise InscriptionError("malformed name list", line)
            parts = text.split(",")
        parts = [part.strip() for part in parts]
        if not parts or any(not part for part in parts):
            raise InscriptionError("malformed name list", line)
        return [self._name(part, line) for part in parts]

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


def parse_expression(text: str, line: int) -> Expr:
    parser = ExpressionParser(tokenize(text, line), line)
    expr = parser.parse_expression()
    if not parser.at_end():
        raise InscriptionError(f"unexpected token '{parser.peek()}' in expression", line)
    return expr


def parse_expression_tokens(tokens: list[str], line: int) -> Expr:
    parser = ExpressionParser(tokens, line)
    expr = parser.parse_expression()
    if not parser.at_end():
        raise InscriptionError(f"unexpected token '{parser.peek()}' in expression", line)
    return expr


def parse_comparison(text: str, line: int) -> Comparison:
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
                predicate, parse_expression_tokens(left_tokens, line), parse_expression_tokens(right_tokens, line), line
            )
    raise InscriptionError("unsupported comparison operator", line)


class ExpressionParser:
    PRECEDENCE = {"plus": 10, "minus": 10, "times": 20}

    def __init__(self, tokens: list[str], line: int):
        self.tokens = tokens
        self.line = line
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
        token = self.pop()
        if re.fullmatch(r"-?\d+", token):
            value = int(token)
            if not -(2**31) <= value <= 2**31 - 1:
                raise InscriptionError("integer literal is outside signed i32 range", self.line)
            return Integer(value, self.line)
        if token == "call":
            return self.parse_call()
        if NAME_RE.fullmatch(token) and token not in RESERVED:
            return Variable(token, self.line)
        raise InscriptionError(f"unexpected token '{token}' in expression", self.line)

    def parse_call(self) -> Call:
        name = self.pop() if not self.at_end() else ""
        if not NAME_RE.fullmatch(name) or name in RESERVED:
            raise InscriptionError("call target must be an identifier", self.line)
        if self.pop() != "with":
            raise InscriptionError("call expression must use 'with'", self.line)
        if self.peek() == "no":
            self.pop()
            if self.pop() != "arguments":
                raise InscriptionError("expected 'no arguments'", self.line)
            return Call(name, (), self.line)
        args: list[Expr] = []
        saw_comma = False
        final_separator = False
        while not self.at_end():
            args.append(self.parse_expression(0, stop={"and"}))
            if final_separator:
                if not self.at_end():
                    raise InscriptionError("malformed call argument list", self.line)
                break
            if self.peek() == ",":
                saw_comma = True
                self.pop()
                if self.at_end():
                    raise InscriptionError("malformed call argument list", self.line)
                if self.peek() == "and":
                    if len(args) < 2:
                        raise InscriptionError("malformed call argument list", self.line)
                    self.pop()
                    if self.at_end():
                        raise InscriptionError("malformed call argument list", self.line)
                    final_separator = True
                continue
            if self.peek() == "and":
                if saw_comma or len(args) != 1:
                    raise InscriptionError("malformed call argument list", self.line)
                self.pop()
                if self.at_end():
                    raise InscriptionError("malformed call argument list", self.line)
                final_separator = True
                continue
            break
        if not args:
            raise InscriptionError("call expression requires arguments or 'no arguments'", self.line)
        return Call(name, tuple(args), self.line)
