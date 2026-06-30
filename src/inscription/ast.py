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
RecordLayoutKind = Literal["value", "natural", "packed"]
FunctionImplementation = Literal["normal", "extern", "export"]


@dataclass(frozen=True)
class ImportDecl:
    module: str
    line: int


@dataclass(frozen=True)
class Program:
    records: tuple["RecordDecl", ...]
    constants: tuple["ConstantDecl", ...]
    checks: tuple["CheckStmt", ...]
    functions: tuple["Function", ...]
    module_name: str | None = None
    imports: tuple[ImportDecl, ...] = ()


@dataclass(frozen=True)
class RecordFieldDecl:
    name: str
    type_name: "ValueType"
    line: int


@dataclass(frozen=True)
class RecordDecl:
    name: str
    fields: tuple[RecordFieldDecl, ...]
    line: int
    layout_kind: RecordLayoutKind = "value"
    layout_info: "LayoutInfo | None" = None


@dataclass(frozen=True)
class LayoutInfo:
    size: int
    alignment: int
    field_offsets: dict[str, int]
    padding_offsets: tuple[int, ...]


@dataclass(frozen=True)
class Parameter:
    name: str
    type_name: "ValueType"


@dataclass(frozen=True)
class Function:
    name: str
    params: tuple[Parameter, ...]
    return_type: "ReturnType"
    body: tuple["Stmt", ...]
    line: int
    display_name: str
    extern_symbol: str | None = None
    implementation: FunctionImplementation = "normal"


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
    length: "BufferLength"
    element_type: "ValueType"


@dataclass(frozen=True)
class ViewType:
    element_type: TypeName
    length: int | None = None


@dataclass(frozen=True)
class RecordType:
    name: str


ValueType = TypeName | BufferType | ViewType | RecordType
ReturnType = TypeName | RecordType | ViewType | None


@dataclass(frozen=True)
class ConstantDecl:
    name: str
    type_name: TypeName
    expr: "Expr"
    line: int


@dataclass(frozen=True)
class BufferLoad:
    name: str
    index: "Expr"
    line: int


@dataclass(frozen=True)
class LengthOf:
    name: str
    line: int


@dataclass(frozen=True)
class SizeOfType:
    type_name: str
    line: int


@dataclass(frozen=True)
class AlignmentOfType:
    type_name: str
    line: int


@dataclass(frozen=True)
class OffsetOfField:
    field: str
    type_name: str
    line: int


@dataclass(frozen=True)
class FieldAccess:
    name: str
    field: str
    line: int


@dataclass(frozen=True)
class RecordFieldInit:
    name: str
    expr: "Expr"
    line: int


@dataclass(frozen=True)
class RecordConstructor:
    type_name: str
    fields: tuple[RecordFieldInit, ...]
    line: int


@dataclass(frozen=True)
class LayoutRead:
    type_name: str
    buffer_name: str
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


Expr = (
    Integer
    | Boolean
    | Variable
    | BufferLoad
    | LengthOf
    | SizeOfType
    | AlignmentOfType
    | OffsetOfField
    | FieldAccess
    | RecordConstructor
    | LayoutRead
    | Unary
    | Cast
    | Binary
    | Call
    | Comparison
    | WhenExpr
)

BufferLength = int | Expr


@dataclass(frozen=True)
class SetStmt:
    name: str
    type_name: ValueType | None
    expr: Expr
    line: int


@dataclass(frozen=True)
class BufferBinding:
    name: str
    buffer_type: BufferType
    fill: Expr
    line: int


@dataclass(frozen=True)
class ViewBinding:
    name: str
    source_name: str
    start: Expr
    count: Expr
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
class FieldAssignStmt:
    name: str
    field: str
    expr: Expr
    line: int


@dataclass(frozen=True)
class LayoutWriteStmt:
    record_name: str
    buffer_name: str
    index: Expr
    line: int


@dataclass(frozen=True)
class CheckStmt:
    expr: Expr
    line: int


@dataclass(frozen=True)
class RequireStmt:
    expr: Expr
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
class ForStmt:
    name: str
    start: Expr
    end: Expr
    step: int
    body: tuple["BodyStmt", ...]
    line: int


@dataclass(frozen=True)
class ForEachStmt:
    name: str
    buffer_name: str
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


BodyStmt = (
    CheckStmt
    | RequireStmt
    | SetStmt
    | BufferBinding
    | ViewBinding
    | AssignStmt
    | BufferStoreStmt
    | FieldAssignStmt
    | LayoutWriteStmt
    | CallStmt
    | WhileStmt
    | ForStmt
    | ForEachStmt
    | IfStmt
)
Stmt = BodyStmt | ReturnStmt
