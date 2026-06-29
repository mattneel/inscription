from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CmpPredicate = Literal["eq", "ne", "slt", "sle", "sgt", "sge"]
BinOp = Literal["plus", "minus", "times"]


@dataclass(frozen=True)
class Program:
    functions: tuple["Function", ...]


@dataclass(frozen=True)
class Function:
    name: str
    params: tuple[str, ...]
    body: tuple["Stmt", ...]
    line: int


@dataclass(frozen=True)
class Integer:
    value: int
    line: int


@dataclass(frozen=True)
class Variable:
    name: str
    line: int


@dataclass(frozen=True)
class Binary:
    op: BinOp
    left: "Expr"
    right: "Expr"
    line: int


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple["Expr", ...]
    line: int


@dataclass(frozen=True)
class Comparison:
    pred: CmpPredicate
    left: "Expr"
    right: "Expr"
    line: int


@dataclass(frozen=True)
class WhenCase:
    expr: "Expr"
    condition: Comparison
    line: int


@dataclass(frozen=True)
class WhenExpr:
    cases: tuple[WhenCase, ...]
    otherwise: "Expr"
    line: int


Expr = Integer | Variable | Binary | Call | WhenExpr


@dataclass(frozen=True)
class SetStmt:
    name: str
    expr: Expr
    line: int


@dataclass(frozen=True)
class ReturnStmt:
    expr: Expr
    line: int


Stmt = SetStmt | ReturnStmt
