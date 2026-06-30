from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TypeName = Literal["i1", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "f32", "f64"]
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
    enums: tuple["EnumDecl", ...]
    unions: tuple["UnionDecl", ...]
    type_aliases: tuple["TypeAliasDecl", ...]
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
class EnumCaseDecl:
    name: str
    value: "Expr"
    line: int


@dataclass(frozen=True)
class EnumDecl:
    name: str
    underlying_type: "ValueType"
    cases: tuple[EnumCaseDecl, ...]
    line: int


@dataclass(frozen=True)
class TypeAliasDecl:
    name: str
    target: "ValueType"
    line: int


@dataclass(frozen=True)
class UnionPayloadField:
    name: str
    type_name: "ValueType"
    line: int


@dataclass(frozen=True)
class UnionVariantDecl:
    name: str
    payload_fields: tuple[UnionPayloadField, ...]
    line: int


@dataclass(frozen=True)
class UnionDecl:
    name: str
    variants: tuple[UnionVariantDecl, ...]
    line: int


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
    is_word_zero: bool = False


@dataclass(frozen=True)
class Float:
    text: str
    line: int


@dataclass(frozen=True)
class ByteLiteral:
    value: int
    line: int


@dataclass(frozen=True)
class ByteString:
    values: tuple[int, ...]
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
class ArrayType:
    length: "BufferLength"
    element_type: "ValueType"


@dataclass(frozen=True)
class ViewType:
    element_type: "ValueType"
    length: int | None = None


@dataclass(frozen=True)
class OwnedBufferType:
    element_type: "ValueType"
    length: int | None = None


@dataclass(frozen=True)
class RecordType:
    name: str


@dataclass(frozen=True)
class EnumType:
    name: str
    underlying_type: TypeName


@dataclass(frozen=True)
class UnionType:
    name: str


ValueType = TypeName | BufferType | ArrayType | ViewType | OwnedBufferType | RecordType | EnumType | UnionType
ReturnType = TypeName | RecordType | ArrayType | ViewType | OwnedBufferType | EnumType | UnionType | None


@dataclass(frozen=True)
class ConstantDecl:
    name: str
    type_name: ValueType
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
class LengthOfBytes:
    values: tuple[int, ...]
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
class EnumCase:
    type_name: str
    case_name: str
    line: int


@dataclass(frozen=True)
class UnionFieldInit:
    name: str
    expr: "Expr"
    line: int


@dataclass(frozen=True)
class UnionConstructor:
    type_name: str
    variant_name: str
    fields: tuple[UnionFieldInit, ...]
    line: int


@dataclass(frozen=True)
class UnionPatternBinding:
    field_name: str
    alias_name: str | None
    line: int


@dataclass(frozen=True)
class UnionPattern:
    type_name: str
    variant_name: str
    bindings: tuple[UnionPatternBinding, ...]
    line: int


Pattern = "Expr | UnionPattern"


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
    target_type: "ValueType"
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


@dataclass(frozen=True)
class MatchExprArm:
    pattern: "Pattern"
    expr: "Expr"
    line: int


@dataclass(frozen=True)
class MatchExpr:
    scrutinee: "Expr"
    arms: tuple[MatchExprArm, ...]
    otherwise: "Expr"
    line: int


Expr = (
    Integer
    | Float
    | ByteLiteral
    | Boolean
    | Variable
    | BufferLoad
    | LengthOf
    | LengthOfBytes
    | SizeOfType
    | AlignmentOfType
    | OffsetOfField
    | FieldAccess
    | EnumCase
    | UnionConstructor
    | RecordConstructor
    | LayoutRead
    | Unary
    | Cast
    | Binary
    | Call
    | Comparison
    | WhenExpr
    | MatchExpr
)

BufferLength = int | Expr
StorageElement = Expr | ByteString


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
    line: int
    fill: Expr | None = None
    values: tuple[StorageElement, ...] = ()


@dataclass(frozen=True)
class ArrayBinding:
    name: str
    array_type: ArrayType
    line: int
    fill: Expr | None = None
    values: tuple[StorageElement, ...] = ()


@dataclass(frozen=True)
class StorageAliasBinding:
    name: str
    alias_type: ValueType
    line: int
    initializer: Literal["filled with", "containing"]
    fill: Expr | None = None
    values: tuple[StorageElement, ...] = ()


@dataclass(frozen=True)
class OwnedBufferBinding:
    name: str
    length: Expr
    element_type: ValueType
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
class MatchStepArm:
    pattern: Pattern
    body: tuple["BodyStmt", ...]
    line: int


@dataclass(frozen=True)
class MatchStep:
    scrutinee: Expr
    arms: tuple[MatchStepArm, ...]
    otherwise_body: tuple["BodyStmt", ...]
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
    | ArrayBinding
    | StorageAliasBinding
    | OwnedBufferBinding
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
    | MatchStep
)
Stmt = BodyStmt | ReturnStmt
