from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TypeName = Literal["i1", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"]
CmpPredicate = Literal["eq", "ne", "slt", "sle", "sgt", "sge"]
BinOp = Literal[
    "plus",
    "minus",
    "times",
    "divided by",
    "remainder",
    "shifted left by",
    "shifted right by",
    "bitwise and",
    "bitwise xor",
    "bitwise or",
    "and",
    "or",
]
UnaryOp = Literal["not", "bitwise not"]


@dataclass(frozen=True)
class Program:
    functions: tuple["Function", ...]


@dataclass(frozen=True)
class Parameter:
    name: str
    type_name: "ValueType"


@dataclass(frozen=True)
class Function:
    name: str
    params: tuple[Parameter, ...]
    return_type: TypeName | None
    body: tuple["Stmt", ...]
    line: int
    display_name: str


@dataclass(frozen=True)
class Integer:
    value: int
    line: int


@dataclass(frozen=True)
class Boolean:
    value: bool
    line: int


@dataclass(frozen=True)
class Variable:
    name: str
    line: int


@dataclass(frozen=True)
class BufferType:
    length: int
    element_type: TypeName


ValueType = TypeName | BufferType


@dataclass(frozen=True)
class BufferLoad:
    name: str
    index: "Expr"
    line: int


@dataclass(frozen=True)
class Binary:
    op: BinOp
    left: "Expr"
    right: "Expr"
    line: int


@dataclass(frozen=True)
class Unary:
    op: UnaryOp
    expr: "Expr"
    line: int


@dataclass(frozen=True)
class Cast:
    expr: "Expr"
    target_type: TypeName
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
    condition: "Expr"
    line: int


@dataclass(frozen=True)
class WhenExpr:
    cases: tuple[WhenCase, ...]
    otherwise: "Expr"
    line: int


Expr = Integer | Boolean | Variable | BufferLoad | Unary | Cast | Binary | Call | Comparison | WhenExpr


@dataclass(frozen=True)
class SetStmt:
    name: str
    type_name: TypeName | None
    expr: Expr
    line: int


@dataclass(frozen=True)
class BufferBinding:
    name: str
    buffer_type: BufferType
    fill: Expr
    line: int


@dataclass(frozen=True)
class AssignStmt:
    name: str
    expr: Expr
    line: int


@dataclass(frozen=True)
class BufferStoreStmt:
    name: str
    index: Expr
    value: Expr
    line: int


@dataclass(frozen=True)
class CallStmt:
    call: Call
    line: int


@dataclass(frozen=True)
class WhileStmt:
    condition: Expr
    body: tuple["BodyStmt", ...]
    line: int


@dataclass(frozen=True)
class IfStmt:
    condition: Expr
    then_body: tuple["BodyStmt", ...]
    else_body: tuple["BodyStmt", ...]
    line: int


@dataclass(frozen=True)
class ReturnStmt:
    expr: Expr
    line: int


BodyStmt = SetStmt | BufferBinding | AssignStmt | BufferStoreStmt | CallStmt | WhileStmt | IfStmt
Stmt = BodyStmt | ReturnStmt
