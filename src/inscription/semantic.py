from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Literal

from .ast import (
    ArrayBinding,
    ArrayType,
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
    CheckStmt,
    Comparison,
    ConstantDecl,
    EnumCase,
    EnumDecl,
    EnumType,
    Expr,
    FieldAccess,
    FieldAssignStmt,
    Float,
    ForEachStmt,
    ForStmt,
    Function,
    IfStmt,
    Integer,
    AlignmentOfType,
    LengthOf,
    LayoutInfo,
    LayoutRead,
    LayoutWriteStmt,
    MatchExpr,
    MatchStep,
    OffsetOfField,
    Parameter,
    Program,
    RecordConstructor,
    RecordDecl,
    RecordType,
    RequireStmt,
    ReturnStmt,
    SetStmt,
    SizeOfType,
    TypeName,
    Unary,
    ValueType,
    Variable,
    ViewBinding,
    ViewType,
    WhenExpr,
    WhileStmt,
)
from .diagnostics import InscriptionError

BOOLEAN_TYPE: TypeName = "i1"
SIGNED_INTEGER_TYPES: set[TypeName] = {"i8", "i16", "i32", "i64"}
UNSIGNED_INTEGER_TYPES: set[TypeName] = {"u8", "u16", "u32", "u64"}
INTEGER_TYPES: set[TypeName] = SIGNED_INTEGER_TYPES | UNSIGNED_INTEGER_TYPES
FLOAT_TYPES: set[TypeName] = {"f32", "f64"}
NUMERIC_TYPES: set[TypeName] = INTEGER_TYPES | FLOAT_TYPES
SCALAR_TYPES: set[TypeName] = {BOOLEAN_TYPE} | NUMERIC_TYPES
TYPE_WIDTHS: dict[TypeName, int] = {
    "i1": 1,
    "i8": 8,
    "i16": 16,
    "i32": 32,
    "i64": 64,
    "u8": 8,
    "u16": 16,
    "u32": 32,
    "u64": 64,
    "f32": 32,
    "f64": 64,
}
INTEGER_RANGES: dict[TypeName, tuple[int, int]] = {
    "i8": (-(2**7), 2**7 - 1),
    "i16": (-(2**15), 2**15 - 1),
    "i32": (-(2**31), 2**31 - 1),
    "i64": (-(2**63), 2**63 - 1),
    "u8": (0, 2**8 - 1),
    "u16": (0, 2**16 - 1),
    "u32": (0, 2**32 - 1),
    "u64": (0, 2**64 - 1),
}
BindingKind = Literal["param", "let", "buffer", "array", "view", "index", "constant"]


@dataclass(frozen=True)
class Binding:
    type_name: ValueType
    kind: BindingKind
    line: int
    writable: bool = True
    root: str | None = None


@dataclass(frozen=True)
class ConstValue:
    type_name: ValueType
    value: int | bool | float



@dataclass(frozen=True)
class EnumInfo:
    name: str
    underlying_type: TypeName
    cases: dict[str, int]
    case_order: tuple[str, ...]
    line: int


ACTIVE_ENUMS: dict[str, EnumInfo] = {}


def enum_type_for_name(name: str) -> EnumType | None:
    info = ACTIVE_ENUMS.get(name)
    if info is None:
        return None
    return EnumType(info.name, info.underlying_type)


def is_enum_type(type_name: ValueType | None) -> bool:
    return isinstance(type_name, EnumType)


def storage_type(type_name: ValueType) -> ValueType:
    return type_name.underlying_type if isinstance(type_name, EnumType) else type_name



def resolve_named_value_type(type_name: ValueType) -> ValueType:
    if isinstance(type_name, BufferType):
        return BufferType(type_name.length, resolve_named_value_type(type_name.element_type))
    if isinstance(type_name, ArrayType):
        return ArrayType(type_name.length, resolve_named_value_type(type_name.element_type))
    if isinstance(type_name, ViewType):
        return ViewType(resolve_named_value_type(type_name.element_type), type_name.length)
    if isinstance(type_name, RecordType):
        enum_type = enum_type_for_name(type_name.name)
        if enum_type is not None:
            return enum_type
    return type_name

class CompileTimeEvaluationError(Exception):
    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.line = line


def analyze(program: Program) -> None:
    enum_table(program)
    records = record_table(program)
    functions = function_table(program)
    constants = constant_table(program, records, functions)
    functions = resolve_function_table(functions, records, constants)
    validate_external_symbols(functions)
    for check in program.checks:
        _check_compile_time_check(check, {}, functions, records, constants)
    main = functions.get("main")
    if main is not None and main.params:
        raise InscriptionError("main must take no parameters", main.line)
    for fn in program.functions:
        _check_function(fn, functions, records, constants)


def enum_table(program: Program) -> dict[str, EnumInfo]:
    global ACTIVE_ENUMS
    ACTIVE_ENUMS = {}
    record_names = {record.name for record in program.records}
    constant_names = {constant.name for constant in program.constants}
    enums: dict[str, EnumInfo] = {}
    for enum in program.enums:
        if enum.name in SCALAR_TYPES:
            raise InscriptionError(f"enum {enum.name} conflicts with scalar type {enum.name}", enum.line)
        if enum.name in enums:
            raise InscriptionError(f"enum {enum.name} is already defined", enum.line)
        if enum.name in record_names:
            raise InscriptionError(f"enum {enum.name} conflicts with record {enum.name}", enum.line)
        if enum.name in constant_names:
            raise InscriptionError(f"enum {enum.name} conflicts with constant {enum.name}", enum.line)
        if enum.underlying_type not in INTEGER_TYPES:
            raise InscriptionError(
                f"enum underlying type must be an integer type, got {format_type(enum.underlying_type)}", enum.line
            )
        if not enum.cases:
            raise InscriptionError(f"enum {enum.name} must declare at least one case", enum.line)
        case_constants = _primitive_constants_before_enum(program, enum.line)
        cases: dict[str, int] = {}
        values: dict[int, str] = {}
        for case in enum.cases:
            if case.name in cases:
                raise InscriptionError(f"enum {enum.name} has duplicate case {case.name}", case.line)
            try:
                value = evaluate_const_expr(
                    case.value,
                    _constant_env_types(case_constants),
                    {},
                    {},
                    case_constants,
                    expected=enum.underlying_type,
                )
            except CompileTimeEvaluationError as exc:
                raise InscriptionError(f"enum case {case.name} must be compile-time evaluable", exc.line or case.line) from exc
            if value.type_name != enum.underlying_type:
                raise InscriptionError(
                    f"enum case {case.name} must have type {enum.underlying_type}, got {format_type(value.type_name)}", case.line
                )
            int_value = int(value.value)
            if int_value in values:
                raise InscriptionError(f"enum {enum.name} has duplicate case value {int_value}", case.line)
            cases[case.name] = int_value
            values[int_value] = case.name
        enums[enum.name] = EnumInfo(enum.name, enum.underlying_type, cases, tuple(cases), enum.line)
    ACTIVE_ENUMS = enums
    return enums


def _primitive_constants_before_enum(program: Program, enum_line: int) -> dict[str, ConstValue]:
    """Evaluate earlier primitive scalar constants for enum case expressions.

    The main constant table needs enum metadata, but enum case values are
    themselves compile-time expressions. This narrow prepass preserves the
    existing declaration-order rule for constants while allowing simple integer
    constants declared before an enum to be used as case values.
    """

    constants: dict[str, ConstValue] = {}
    for const in sorted(program.constants, key=lambda item: item.line):
        if const.line >= enum_line:
            continue
        if not isinstance(const.type_name, str) or const.type_name not in SCALAR_TYPES:
            continue
        env = _constant_env_types(constants)
        try:
            value = evaluate_const_expr(const.expr, env, {}, {}, constants, expected=const.type_name)
        except (CompileTimeEvaluationError, InscriptionError):
            continue
        if value.type_name == const.type_name:
            constants[const.name] = value
    return constants


def record_table(program: Program) -> dict[str, RecordDecl]:
    records: dict[str, RecordDecl] = {}
    for record in program.records:
        if record.name in SCALAR_TYPES:
            raise InscriptionError(f"record name {record.name} collides with scalar type", record.line)
        if record.name in ACTIVE_ENUMS:
            raise InscriptionError(f"record {record.name} conflicts with enum {record.name}", record.line)
        if record.name in records:
            raise InscriptionError(f"record {record.name} is already defined", record.line)
        if not record.fields:
            prefix = "record" if record.layout_kind == "value" else "layout record"
            raise InscriptionError(f"{prefix} {record.name} must declare at least one field", record.line)
        seen_fields: set[str] = set()
        resolved_fields = []
        for field in record.fields:
            if field.name in seen_fields:
                prefix = "record" if record.layout_kind == "value" else "layout record"
                raise InscriptionError(f"{prefix} {record.name} has duplicate field {field.name}", field.line)
            seen_fields.add(field.name)
            field_type = resolve_named_value_type(field.type_name)
            if record.layout_kind == "value":
                if not (isinstance(field_type, str) and field_type in SCALAR_TYPES) and not isinstance(field_type, EnumType):
                    raise InscriptionError(
                        f"record fields must be scalar types, got {format_type(field_type)}", field.line
                    )
            elif not ((isinstance(field_type, str) and field_type in INTEGER_TYPES) or isinstance(field_type, EnumType)):
                raise InscriptionError(
                    f"layout record fields must be integer types, got {format_type(field_type)}", field.line
                )
            resolved_fields.append(type(field)(field.name, field_type, field.line))
        resolved_record = RecordDecl(record.name, tuple(resolved_fields), record.line, record.layout_kind)
        layout_info = compute_layout_info(resolved_record) if record.layout_kind != "value" else None
        records[record.name] = RecordDecl(record.name, tuple(resolved_fields), record.line, record.layout_kind, layout_info)
    return records


def function_table(program: Program) -> dict[str, Function]:
    functions: dict[str, Function] = {}
    for fn in program.functions:
        if fn.name in functions:
            if fn.extern_symbol is not None or functions[fn.name].extern_symbol is not None:
                raise InscriptionError(f"phrase `{fn.display_name}` is already defined", fn.line)
            raise InscriptionError(f"duplicate phrase '{fn.name}'", fn.line)
        functions[fn.name] = fn
        seen_params: set[str] = set()
        for param in fn.params:
            if param.name in seen_params:
                raise InscriptionError(f"duplicate parameter '{param.name}'", fn.line)
            seen_params.add(param.name)
    return functions


def validate_external_symbols(functions: dict[str, Function]) -> None:
    externs: dict[str, tuple[tuple[ValueType, ...], ValueType | None]] = {}
    exports: dict[str, Function] = {}
    normal_symbols = {fn.name for fn in functions.values() if fn.implementation == "normal"}
    for fn in functions.values():
        if fn.extern_symbol is None:
            continue
        if fn.implementation == "export":
            if fn.extern_symbol == "main" or fn.extern_symbol in normal_symbols:
                raise InscriptionError(
                    f"exported symbol {fn.extern_symbol} conflicts with generated function {fn.extern_symbol}",
                    fn.line,
                )
            if fn.extern_symbol in exports:
                raise InscriptionError(f"exported symbol {fn.extern_symbol} is already defined", fn.line)
            if fn.extern_symbol in externs:
                raise InscriptionError(
                    f"exported symbol {fn.extern_symbol} conflicts with external symbol {fn.extern_symbol}",
                    fn.line,
                )
            exports[fn.extern_symbol] = fn
            continue
        if fn.implementation == "extern":
            if fn.extern_symbol == "main" or fn.extern_symbol in normal_symbols:
                raise InscriptionError(
                    f"external symbol {fn.extern_symbol} conflicts with generated function {fn.extern_symbol}",
                    fn.line,
                )
            if fn.extern_symbol in exports:
                raise InscriptionError(
                    f"exported symbol {fn.extern_symbol} conflicts with external symbol {fn.extern_symbol}",
                    fn.line,
                )
            signature = (tuple(param.type_name for param in fn.params), fn.return_type)
            existing = externs.get(fn.extern_symbol)
            if existing is not None and existing != signature:
                raise InscriptionError(f"external symbol {fn.extern_symbol} declared with incompatible types", fn.line)
            externs[fn.extern_symbol] = signature


def constant_table(
    program: Program,
    records: dict[str, RecordDecl],
    functions: dict[str, Function],
) -> dict[str, ConstValue]:
    constants: dict[str, ConstValue] = {}
    for const in program.constants:
        if const.name in constants:
            raise InscriptionError(f"constant {const.name} is already defined", const.line)
        if const.name in SCALAR_TYPES:
            raise InscriptionError(f"constant {const.name} conflicts with scalar type {const.name}", const.line)
        if const.name in records:
            raise InscriptionError(f"constant {const.name} conflicts with record {const.name}", const.line)
        if const.name in ACTIVE_ENUMS:
            raise InscriptionError(f"constant {const.name} conflicts with enum {const.name}", const.line)
        resolved_type = resolve_value_type(const.type_name, const.line, records, constants, functions, {})
        if not (isinstance(resolved_type, str) and resolved_type in SCALAR_TYPES) and not isinstance(resolved_type, EnumType):
            raise InscriptionError(f"constant {const.name} must have a scalar type", const.line)
        env = _constant_env_types(constants)
        try:
            value = evaluate_const_expr(const.expr, env, functions, records, constants, expected=resolved_type)
        except CompileTimeEvaluationError as exc:
            raise InscriptionError(f"constant {const.name} must be compile-time evaluable", exc.line or const.line) from exc
        except InscriptionError as exc:
            message = getattr(exc, "message", str(exc))
            if (
                _should_preserve_expected_error(exc)
                or message.startswith("unknown binding")
                or message.startswith("constant expression")
                or message.startswith("constant shift")
            ):
                raise
            try:
                actual = infer_expr_type(const.expr, env, functions, records)
            except InscriptionError:
                raise exc
            raise InscriptionError(
                f"constant {const.name} must have type {format_type(resolved_type)}, got {format_type(actual)}", const.line
            ) from exc
        if value.type_name != resolved_type:
            raise InscriptionError(
                f"constant {const.name} must have type {format_type(resolved_type)}, got {format_type(value.type_name)}", const.line
            )
        constants[const.name] = value
    return constants


def resolve_function_table(
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> dict[str, Function]:
    resolved: dict[str, Function] = {}
    for name, fn in functions.items():
        params = tuple(
            Parameter(param.name, resolve_value_type(param.type_name, fn.line, records, constants, functions, {}))
            for param in fn.params
        )
        return_type = (
            None
            if fn.return_type is None
            else resolve_value_type(fn.return_type, fn.line, records, constants, functions, {})
        )
        resolved[name] = Function(fn.name, params, return_type, fn.body, fn.line, fn.display_name, fn.extern_symbol, fn.implementation)
    return resolved


def mlir_type(type_name: ValueType) -> str:
    type_name = storage_type(type_name)
    assert isinstance(type_name, str)
    if type_name.startswith("u"):
        return f"i{TYPE_WIDTHS[type_name]}"
    return type_name


def memref_type(buffer_type: BufferType | ArrayType) -> str:
    return f"memref<{buffer_type.length}x{mlir_type(buffer_type.element_type)}>"


def format_type(type_name: ValueType) -> str:
    if isinstance(type_name, BufferType):
        return f"buffer of {type_name.length} {format_type(type_name.element_type)}"
    if isinstance(type_name, ArrayType):
        return f"array of {type_name.length} {format_type(type_name.element_type)}"
    if isinstance(type_name, ViewType):
        return f"view of {format_type(type_name.element_type)}"
    if isinstance(type_name, RecordType):
        return type_name.name
    if isinstance(type_name, EnumType):
        return type_name.name
    return type_name


def is_integer_type(type_name: ValueType | None) -> bool:
    return type_name in INTEGER_TYPES


def is_float_type(type_name: ValueType | None) -> bool:
    return type_name in FLOAT_TYPES


def is_numeric_type(type_name: ValueType | None) -> bool:
    return type_name in NUMERIC_TYPES


def is_signed_type(type_name: ValueType) -> bool:
    type_name = storage_type(type_name)
    return type_name in SIGNED_INTEGER_TYPES


def type_width(type_name: ValueType) -> int:
    type_name = storage_type(type_name)
    assert isinstance(type_name, str)
    return TYPE_WIDTHS[type_name]


def byte_width(type_name: ValueType) -> int:
    type_name = storage_type(type_name)
    assert isinstance(type_name, str)
    return TYPE_WIDTHS[type_name] // 8


def _align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def compute_layout_info(record: RecordDecl) -> LayoutInfo:
    offset = 0
    alignment = 1
    field_offsets: dict[str, int] = {}
    occupied: set[int] = set()
    for field in record.fields:
        field_size = byte_width(field.type_name)
        field_alignment = 1 if record.layout_kind == "packed" else field_size
        alignment = max(alignment, field_alignment)
        offset = _align_up(offset, field_alignment)
        field_offsets[field.name] = offset
        occupied.update(range(offset, offset + field_size))
        offset += field_size
    size = offset if record.layout_kind == "packed" else _align_up(offset, alignment)
    padding_offsets = tuple(byte for byte in range(size) if byte not in occupied)
    return LayoutInfo(size, alignment, field_offsets, padding_offsets)


def layout_info(record: RecordDecl) -> LayoutInfo:
    if record.layout_info is None:
        raise AssertionError("layout info requested for non-layout record")  # pragma: no cover
    return record.layout_info


def all_ones_constant_value(_type_name: TypeName) -> int:
    return -1


def _check_function(
    fn: Function,
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    fn = functions[fn.name]
    if fn.implementation == "extern":
        _check_extern_function(fn, records)
        return
    if fn.implementation == "export":
        _check_exported_function(fn, records)
    resolved_params: list[tuple[str, ValueType]] = []
    for param in fn.params:
        if param.name in constants:
            raise InscriptionError(f"binding {param.name} conflicts with constant {param.name}", fn.line)
        resolved_type = resolve_value_type(param.type_name, fn.line, records, constants, functions, {})
        _check_parameter_type(resolved_type, fn.line, records, constants, functions)
        resolved_params.append((param.name, resolved_type))
    if fn.return_type is None:
        _check_does_function(fn, functions, records, constants, resolved_params)
        return
    if isinstance(fn.return_type, RecordType):
        if fn.return_type.name not in records:
            raise InscriptionError(f"unknown type {fn.return_type.name}", fn.line)
    if isinstance(fn.return_type, ViewType):
        raise InscriptionError("view return types are not supported", fn.line)
    if isinstance(fn.return_type, ArrayType):
        raise InscriptionError("array return types are not supported", fn.line)
    if not fn.body:
        raise InscriptionError(f"phrase '{fn.name}' must evaluate to a value", fn.line)
    bindings = _constant_bindings(constants)
    for name, type_name in resolved_params:
        bindings[name] = Binding(
            type_name,
            "param",
            fn.line,
            writable=not isinstance(type_name, BufferType | ArrayType | ViewType),
            root=name if isinstance(type_name, BufferType | ArrayType | ViewType) else None,
        )
    returned = False
    for index, stmt in enumerate(fn.body):
        if returned:
            raise InscriptionError("unreachable statement after value expression", getattr(stmt, "line", None))
        is_last = index == len(fn.body) - 1
        if isinstance(stmt, ReturnStmt):
            if not is_last:
                raise InscriptionError("value expression must be the final phrase body form", stmt.line)
            actual = _infer_declared_type(stmt.expr, fn.return_type, _env_types(bindings), functions, records, constants)
            if actual != fn.return_type:
                if isinstance(actual, RecordType) or isinstance(fn.return_type, RecordType):
                    raise InscriptionError(
                        f"phrase {fn.display_name} must return {format_type(fn.return_type)}, got {format_type(actual)}",
                        stmt.line,
                    )
                require_type(actual, fn.return_type, stmt.line)
            returned = True
        else:
            _check_body_stmt(stmt, bindings, functions, records, constants)
    if not returned:
        raise InscriptionError(f"phrase '{fn.name}' must evaluate to a value", fn.line)


def _primitive_abi_type_message(prefix: str, type_name: ValueType) -> str:
    wording = "primitive scalar types" if isinstance(resolve_named_value_type(type_name), EnumType) else "scalar types"
    return f"{prefix} must be {wording}, got {format_type(type_name)}"


def _check_extern_function(fn: Function, records: dict[str, RecordDecl]) -> None:
    if fn.body:
        raise InscriptionError("extern phrase declarations cannot have bodies", fn.line)
    for param in fn.params:
        if not isinstance(param.type_name, str) or param.type_name not in SCALAR_TYPES:
            raise InscriptionError(
                _primitive_abi_type_message("extern phrase parameters", param.type_name),
                fn.line,
            )
    if fn.return_type is not None and (not isinstance(fn.return_type, str) or fn.return_type not in SCALAR_TYPES):
        if isinstance(fn.return_type, RecordType) and fn.return_type.name not in records and enum_type_for_name(fn.return_type.name) is None:
            raise InscriptionError(f"unknown type {fn.return_type.name}", fn.line)
        raise InscriptionError(
            _primitive_abi_type_message("extern phrase return types", fn.return_type),
            fn.line,
        )


def _check_exported_function(fn: Function, records: dict[str, RecordDecl]) -> None:
    for param in fn.params:
        if not isinstance(param.type_name, str) or param.type_name not in SCALAR_TYPES:
            raise InscriptionError(
                _primitive_abi_type_message("exported phrase parameters", param.type_name),
                fn.line,
            )
    if fn.return_type is not None and (not isinstance(fn.return_type, str) or fn.return_type not in SCALAR_TYPES):
        if isinstance(fn.return_type, RecordType) and fn.return_type.name not in records and enum_type_for_name(fn.return_type.name) is None:
            raise InscriptionError(f"unknown type {fn.return_type.name}", fn.line)
        raise InscriptionError(
            _primitive_abi_type_message("exported phrase return types", fn.return_type),
            fn.line,
        )


def _check_does_function(
    fn: Function,
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
    resolved_params: list[tuple[str, ValueType]],
) -> None:
    if not fn.body:
        raise InscriptionError("does phrase body must contain at least one step", fn.line)
    bindings = _constant_bindings(constants)
    for name, type_name in resolved_params:
        bindings[name] = Binding(
            type_name,
            "param",
            fn.line,
            writable=True,
            root=name if isinstance(type_name, BufferType | ArrayType | ViewType) else None,
        )
    for stmt in fn.body:
        if isinstance(stmt, ReturnStmt):
            raise InscriptionError("does phrase body cannot end with a value expression", stmt.line)
        _check_body_stmt(stmt, bindings, functions, records, constants)


def _check_parameter_type(
    type_name: ValueType,
    line: int,
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
    functions: dict[str, Function],
) -> None:
    if isinstance(type_name, BufferType):
        _check_buffer_type(type_name, line, records, constants, functions, {})
        return
    if isinstance(type_name, ArrayType):
        resolved = resolve_array_type(type_name, line, records, constants, functions, {})
        element = resolved.element_type
        suffix = f"view of {element}" if isinstance(element, str) else "view"
        raise InscriptionError(f"array parameters are not supported in v0.22; use {suffix}", line)
    if isinstance(type_name, ViewType):
        _check_view_type(type_name, line)
        return
    if isinstance(type_name, RecordType):
        if type_name.name not in records:
            raise InscriptionError(f"unknown type {type_name.name}", line)
        return
    if isinstance(type_name, EnumType):
        return
    if type_name not in SCALAR_TYPES:
        raise InscriptionError("supported scalar types are i1, i8, i16, i32, i64, u8, u16, u32, u64, f32, and f64", line)


def _check_buffer_type(
    buffer_type: BufferType | ViewType,
    line: int,
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
    functions: dict[str, Function],
    env: dict[str, ValueType],
) -> None:
    resolved = resolve_buffer_type(buffer_type, line, records, constants, functions, env)
    if resolved.length < 1:
        raise InscriptionError("buffer length must be at least 1", line)
    if not is_numeric_type(resolved.element_type) and not isinstance(resolved.element_type, EnumType):
        raise InscriptionError(f"buffer element type must be an integer type, got {format_type(resolved.element_type)}", line)


def _check_array_type(array_type: ArrayType, line: int) -> None:
    if array_type.length < 1:
        raise InscriptionError("buffer length must be at least 1", line)
    if not is_numeric_type(array_type.element_type) and not isinstance(array_type.element_type, EnumType):
        raise InscriptionError(f"array element type must be numeric, got {format_type(array_type.element_type)}", line)


def _check_view_type(view_type: ViewType, line: int) -> None:
    if not is_numeric_type(view_type.element_type) and not isinstance(view_type.element_type, EnumType):
        raise InscriptionError(f"view element type must be an integer type, got {format_type(view_type.element_type)}", line)


def _check_body_stmt(
    stmt: BodyStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    if isinstance(stmt, CheckStmt):
        _check_compile_time_check(stmt, _env_types(bindings), functions, records, constants)
        return
    if isinstance(stmt, RequireStmt):
        _check_require(stmt, _env_types(bindings), functions, records, constants)
        return
    if isinstance(stmt, SetStmt):
        _declare_let(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, BufferBinding):
        _declare_buffer(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, ArrayBinding):
        _declare_array(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, ViewBinding):
        _declare_view(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, AssignStmt):
        _check_assignment(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, BufferStoreStmt):
        _check_buffer_store(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, FieldAssignStmt):
        _check_field_assignment(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, LayoutWriteStmt):
        _check_layout_write(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, CallStmt):
        _check_call_stmt(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, WhileStmt):
        _check_while(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, ForStmt):
        _check_for(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, ForEachStmt):
        _check_for_each(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, IfStmt):
        _check_if(stmt, bindings, functions, records, constants)
        return
    if isinstance(stmt, MatchStep):
        _check_match_step(stmt, bindings, functions, records, constants)
        return
    raise AssertionError(stmt)  # pragma: no cover


def _check_no_shadow(name: str, line: int, bindings: dict[str, Binding], *, kind: str) -> None:
    existing = bindings.get(name)
    if existing is None:
        return
    if existing.kind == "param":
        raise InscriptionError(f"{kind} binding '{name}' cannot shadow phrase hole", line)
    if existing.kind == "buffer":
        raise InscriptionError(f"{kind} binding '{name}' cannot shadow buffer binding", line)
    if existing.kind == "array":
        raise InscriptionError(f"{kind} binding '{name}' cannot shadow array binding", line)
    if existing.kind == "view":
        raise InscriptionError(f"{kind} binding '{name}' cannot shadow view binding", line)
    if existing.kind == "constant":
        raise InscriptionError(f"binding {name} conflicts with constant {name}", line)
    raise InscriptionError(f"duplicate {kind} binding '{name}'", line)


def _declare_let(
    stmt: SetStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    _check_no_shadow(stmt.name, stmt.line, bindings, kind="let")
    if stmt.type_name is not None:
        resolved_declared_type = resolve_value_type(stmt.type_name, stmt.line, records, constants, functions, _env_types(bindings))
        if isinstance(resolved_declared_type, ArrayType):
            raise InscriptionError("array type annotations are not supported in v0.22", stmt.line)
        if isinstance(resolved_declared_type, RecordType) and resolved_declared_type.name not in records:
            raise InscriptionError(f"unknown type {resolved_declared_type.name}", stmt.line)
        actual = _infer_declared_type(stmt.expr, resolved_declared_type, _env_types(bindings), functions, records, constants)
        if actual != resolved_declared_type:
            raise InscriptionError(
                f"let {stmt.name} must have type {format_type(resolved_declared_type)}, got {format_type(actual)}", stmt.line
            )
        bindings[stmt.name] = Binding(resolved_declared_type, "let", stmt.line)
        return
    type_name = infer_expr_type(stmt.expr, _env_types(bindings), functions, records, constants=constants)
    bindings[stmt.name] = Binding(type_name, "let", stmt.line)


def _declare_buffer(
    stmt: BufferBinding,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    _check_no_shadow(stmt.name, stmt.line, bindings, kind="buffer")
    buffer_type = resolve_buffer_type(stmt.buffer_type, stmt.line, records, constants, functions, _env_types(bindings))
    _check_buffer_type(buffer_type, stmt.line, records, constants, functions, _env_types(bindings))
    if stmt.values:
        if len(stmt.values) != buffer_type.length:
            raise InscriptionError(f"buffer {stmt.name} expects {buffer_type.length} elements, got {len(stmt.values)}", stmt.line)
        for index, value in enumerate(stmt.values):
            actual = _infer_declared_type(value, buffer_type.element_type, _env_types(bindings), functions, records, constants)
            if actual != buffer_type.element_type:
                raise InscriptionError(
                    f"buffer {stmt.name} element {index} must have type {format_type(buffer_type.element_type)}, got {format_type(actual)}",
                    getattr(value, "line", stmt.line),
                )
    else:
        assert stmt.fill is not None
        actual = _infer_declared_type(stmt.fill, buffer_type.element_type, _env_types(bindings), functions, records, constants)
        if actual != buffer_type.element_type:
            raise InscriptionError(
                f"buffer {stmt.name} fill must have type {format_type(buffer_type.element_type)}, got {format_type(actual)}", stmt.line
            )
    bindings[stmt.name] = Binding(buffer_type, "buffer", stmt.line, root=stmt.name)


def _declare_array(
    stmt: ArrayBinding,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    _check_no_shadow(stmt.name, stmt.line, bindings, kind="array")
    array_type = resolve_array_type(stmt.array_type, stmt.line, records, constants, functions, _env_types(bindings))
    _check_array_type(array_type, stmt.line)
    if stmt.values:
        if len(stmt.values) != array_type.length:
            raise InscriptionError(f"array {stmt.name} expects {array_type.length} elements, got {len(stmt.values)}", stmt.line)
        for index, value in enumerate(stmt.values):
            actual = _infer_declared_type(value, array_type.element_type, _env_types(bindings), functions, records, constants)
            if actual != array_type.element_type:
                raise InscriptionError(
                    f"array {stmt.name} element {index} must have type {format_type(array_type.element_type)}, got {format_type(actual)}",
                    getattr(value, "line", stmt.line),
                )
    else:
        assert stmt.fill is not None
        actual = _infer_declared_type(stmt.fill, array_type.element_type, _env_types(bindings), functions, records, constants)
        if actual != array_type.element_type:
            raise InscriptionError(
                f"array {stmt.name} fill must have type {format_type(array_type.element_type)}, got {format_type(actual)}", stmt.line
            )
    bindings[stmt.name] = Binding(array_type, "array", stmt.line, writable=False, root=stmt.name)


def _declare_view(
    stmt: ViewBinding,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    _check_no_shadow(stmt.name, stmt.line, bindings, kind="view")
    source = bindings.get(stmt.source_name)
    if source is None:
        raise InscriptionError(f"unknown binding {stmt.source_name}", stmt.line)
    if not isinstance(source.type_name, BufferType | ArrayType | ViewType):
        raise InscriptionError(
            f"view source {stmt.source_name} must be a buffer or view, got {format_type(source.type_name)}",
            stmt.line,
        )
    start_type = infer_expr_type(stmt.start, _env_types(bindings), functions, records, constants=constants)
    if start_type != "i32":
        raise InscriptionError(f"view start must have type i32, got {format_type(start_type)}", stmt.line)
    count_type = infer_expr_type(stmt.count, _env_types(bindings), functions, records, constants=constants)
    if count_type != "i32":
        raise InscriptionError(f"view count must have type i32, got {format_type(count_type)}", stmt.line)

    env = _env_types(bindings)
    static_start = _static_integer_value(stmt.start, env, functions, records, constants)
    static_count = _static_integer_value(stmt.count, env, functions, records, constants)
    if static_start is not None and static_start < 0:
        raise InscriptionError("view start must be nonnegative", getattr(stmt.start, "line", stmt.line))
    if static_count is not None and static_count < 0:
        raise InscriptionError("view count must be nonnegative", getattr(stmt.count, "line", stmt.line))
    source_length = _static_storage_length(source.type_name)
    if static_start is not None and static_count is not None and source_length is not None:
        if static_start + static_count > source_length:
            raise InscriptionError(
                f"view range {static_start} for {static_count} exceeds source {stmt.source_name} of length {source_length}",
                stmt.line,
            )
    element_type = source.type_name.element_type
    bindings[stmt.name] = Binding(
        ViewType(element_type, static_count),
        "view",
        stmt.line,
        writable=source.writable,
        root=source.root or stmt.source_name,
    )


def _check_assignment(
    stmt: AssignStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    binding = bindings.get(stmt.name)
    if binding is None:
        raise InscriptionError(f"unknown binding {stmt.name}", stmt.line)
    if isinstance(binding.type_name, BufferType):
        raise InscriptionError(
            f"cannot rebind buffer {stmt.name}; use `{stmt.name} at index becomes value`", stmt.line
        )
    if isinstance(binding.type_name, ArrayType):
        raise InscriptionError(f"cannot rebind array {stmt.name}", stmt.line)
    if isinstance(binding.type_name, ViewType):
        raise InscriptionError(f"cannot rebind view {stmt.name}", stmt.line)
    if not binding.writable:
        if binding.kind == "constant":
            raise InscriptionError(f"cannot rebind constant {stmt.name}", stmt.line)
        if binding.kind == "index":
            raise InscriptionError(f"cannot rebind for-loop index {stmt.name}", stmt.line)
        raise InscriptionError(f"cannot rebind {stmt.name}", stmt.line)
    actual = _infer_declared_type(stmt.expr, binding.type_name, _env_types(bindings), functions, records, constants)
    if actual != binding.type_name:
        raise InscriptionError(
            f"assignment to {stmt.name} must have type {format_type(binding.type_name)}, got {format_type(actual)}", stmt.line
        )


def _check_buffer_store(
    stmt: BufferStoreStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    binding = _require_indexable_binding(stmt.name, stmt.line, bindings)
    storage_type = binding.type_name
    if isinstance(storage_type, ArrayType):
        raise InscriptionError(f"cannot store into array {stmt.name}; arrays are immutable", stmt.line)
    if not binding.writable:
        if isinstance(storage_type, ViewType):
            raise InscriptionError(f"cannot store through read-only view {stmt.name}", stmt.line)
        raise InscriptionError(f"cannot store to read-only buffer parameter {stmt.name}", stmt.line)
    _check_storage_index(stmt.name, storage_type, stmt.index, _env_types(bindings), functions, records, constants)
    actual = _infer_declared_type(stmt.value, storage_type.element_type, _env_types(bindings), functions, records, constants)
    if actual != storage_type.element_type:
        raise InscriptionError(
            f"store to {stmt.name} must have type {format_type(storage_type.element_type)}, got {format_type(actual)}", stmt.line
        )


def _check_field_assignment(
    stmt: FieldAssignStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    record_type = _require_record_type(stmt.name, stmt.line, _env_types(bindings))
    field_type = _require_record_field(record_type, stmt.field, stmt.line, records)
    actual = _infer_declared_type(stmt.expr, field_type, _env_types(bindings), functions, records, constants)
    if actual != field_type:
        raise InscriptionError(
            f"field {stmt.field} of {record_type.name} must have type {format_type(field_type)}, got {format_type(actual)}", stmt.line
        )


def _check_layout_write(
    stmt: LayoutWriteStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    record_type = _require_record_type(stmt.record_name, stmt.line, _env_types(bindings))
    record = _record_decl(record_type, stmt.line, records)
    if record.layout_kind == "value":
        raise InscriptionError(f"write {stmt.record_name} requires a layout record value, got {record_type.name}", stmt.line)
    buffer_binding = _require_indexable_binding(stmt.buffer_name, stmt.line, bindings)
    buffer_type = buffer_binding.type_name
    if buffer_type.element_type != "u8":
        noun = "u8 buffer or view" if isinstance(buffer_type, ViewType) else "u8 buffer"
        raise InscriptionError(
            f"write {record_type.name} requires a {noun}, got {format_type(buffer_type)}", stmt.line
        )
    if isinstance(buffer_type, ArrayType):
        raise InscriptionError(f"cannot write into array {stmt.buffer_name}; arrays are immutable", stmt.line)
    if not buffer_binding.writable:
        if isinstance(buffer_type, ViewType):
            raise InscriptionError(f"cannot write to read-only view {stmt.buffer_name}", stmt.line)
        raise InscriptionError(f"cannot write to read-only buffer parameter {stmt.buffer_name}", stmt.line)
    _check_layout_index(
        "layout write",
        "write",
        record_type.name,
        stmt.buffer_name,
        layout_info(record).size,
        buffer_type,
        stmt.index,
        _env_types(bindings),
        functions,
        records,
        constants,
    )


def _check_call_stmt(
    stmt: CallStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    target = _lookup_phrase(stmt.call.name, stmt.line, functions)
    if target.return_type is not None:
        raise InscriptionError(
            f"phrase `{target.display_name}` returns {format_type(target.return_type)} and cannot be used as a step", stmt.line
        )
    _check_call_arguments(stmt.call, target, bindings, functions, records, constants, effectful=True)


def _check_while(
    stmt: WhileStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    condition_type = infer_expr_type(stmt.condition, _env_types(bindings), functions, records)
    if condition_type != "i1":
        raise InscriptionError(f"while condition must be i1, got {format_type(condition_type)}", stmt.line)
    if not stmt.body:
        raise InscriptionError("while loop requires at least one body step", stmt.line)
    scoped = dict(bindings)
    for body_stmt in stmt.body:
        _check_body_stmt(body_stmt, scoped, functions, records, constants)


def _check_for(
    stmt: ForStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    start_type = infer_expr_type(stmt.start, _env_types(bindings), functions, records)
    end_type = infer_expr_type(stmt.end, _env_types(bindings), functions, records)
    if not is_integer_type(start_type) or not is_integer_type(end_type):
        raise InscriptionError(
            f"for loop bounds must be integer types, got {format_type(start_type)} and {format_type(end_type)}", stmt.line
        )
    if start_type != end_type:
        raise InscriptionError(
            f"for loop bounds must have matching integer types, got {format_type(start_type)} and {format_type(end_type)}",
            stmt.line,
        )
    if stmt.step < 1:
        raise InscriptionError("for loop step must be at least 1", stmt.line)
    if not stmt.body:
        raise InscriptionError("for loop body must contain at least one step", stmt.line)
    _check_index_shadow(stmt.name, stmt.line, bindings)
    scoped = dict(bindings)
    scoped[stmt.name] = Binding(start_type, "index", stmt.line, writable=False)
    for body_stmt in stmt.body:
        _check_body_stmt(body_stmt, scoped, functions, records, constants)


def _check_for_each(
    stmt: ForEachStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    binding = bindings.get(stmt.buffer_name)
    if binding is None:
        raise InscriptionError(f"unknown binding {stmt.buffer_name}", stmt.line)
    if not isinstance(binding.type_name, BufferType | ArrayType | ViewType):
        raise InscriptionError(f"for each index requires a buffer, got {format_type(binding.type_name)}", stmt.line)
    if not stmt.body:
        raise InscriptionError("for loop body must contain at least one step", stmt.line)
    _check_index_shadow(stmt.name, stmt.line, bindings)
    scoped = dict(bindings)
    scoped[stmt.name] = Binding("i32", "index", stmt.line, writable=False)
    for body_stmt in stmt.body:
        _check_body_stmt(body_stmt, scoped, functions, records, constants)


def _check_index_shadow(name: str, line: int, bindings: dict[str, Binding]) -> None:
    if name in bindings:
        raise InscriptionError(f"binding {name} already exists", line)


def _check_if(
    stmt: IfStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    condition_type = infer_expr_type(stmt.condition, _env_types(bindings), functions, records)
    if condition_type != "i1":
        raise InscriptionError(f"if condition must be i1, got {format_type(condition_type)}", stmt.line)
    if not stmt.then_body:
        raise InscriptionError("if branch must contain at least one step", stmt.line)
    if not stmt.else_body:
        raise InscriptionError("otherwise branch must contain at least one step", stmt.line)

    then_scope = dict(bindings)
    for body_stmt in stmt.then_body:
        _check_body_stmt(body_stmt, then_scope, functions, records, constants)

    else_scope = dict(bindings)
    for body_stmt in stmt.else_body:
        _check_body_stmt(body_stmt, else_scope, functions, records, constants)


def _check_match_step(
    stmt: MatchStep,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    env = {**_constant_env_types(constants), **_env_types(bindings)}
    scrutinee_type = infer_match_scrutinee_type(stmt.scrutinee, env, functions, records, constants=constants)
    _require_match_scrutinee_type(scrutinee_type, stmt.line)
    if not stmt.arms:
        raise InscriptionError("match block requires at least one pattern arm", stmt.line)
    _check_match_patterns(tuple(arm.pattern for arm in stmt.arms), scrutinee_type, env, functions, records, constants)

    for arm in stmt.arms:
        if not arm.body:
            raise InscriptionError("match arm must contain at least one step", arm.line)
        arm_scope = dict(bindings)
        for body_stmt in arm.body:
            _check_body_stmt(body_stmt, arm_scope, functions, records, constants)

    if not stmt.otherwise_body:
        raise InscriptionError("match arm must contain at least one step", stmt.line)
    otherwise_scope = dict(bindings)
    for body_stmt in stmt.otherwise_body:
        _check_body_stmt(body_stmt, otherwise_scope, functions, records, constants)


def _lookup_phrase(name: str, line: int, functions: dict[str, Function]) -> Function:
    target = functions.get(name)
    if target is None:
        raise InscriptionError(f"unknown phrase '{name}'", line)
    return target


def _check_call_arguments(
    call: Call,
    target: Function,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
    *,
    effectful: bool,
) -> None:
    _check_call_arity(call, target)
    seen_roots: dict[str, str] = {}
    env = _env_types(bindings)
    for arg, param in zip(call.args, target.params, strict=True):
        expected = resolve_value_type(param.type_name, call.line, records, constants, functions, {})
        if isinstance(expected, BufferType):
            name, binding = _require_buffer_argument(arg, expected, env, getattr(arg, "line", call.line), records)
            root = bindings[name].root or name
            if root in seen_roots:
                raise InscriptionError(f"buffer {name} cannot be passed to multiple buffer parameters in one call", call.line)
            seen_roots[root] = name
            full_binding = bindings[name]
            if effectful and not full_binding.writable:
                raise InscriptionError(f"cannot pass read-only buffer {name} to effectful phrase `{target.display_name}`", call.line)
            continue
        if isinstance(expected, ViewType):
            name, actual_type = _require_view_argument(arg, expected, env, getattr(arg, "line", call.line), records)
            root = bindings[name].root or name
            previous = seen_roots.get(root)
            if previous is not None:
                if previous != name:
                    raise InscriptionError(
                        f"views {previous} and {name} share root buffer {root} and cannot be passed to multiple view parameters in one call",
                        call.line,
                    )
                if isinstance(actual_type, ViewType):
                    raise InscriptionError(f"view {name} cannot be passed to multiple view parameters in one call", call.line)
                if isinstance(actual_type, ArrayType):
                    raise InscriptionError(f"array {name} cannot be passed to multiple view parameters in one call", call.line)
                raise InscriptionError(f"buffer {name} cannot be passed to multiple buffer parameters in one call", call.line)
            seen_roots[root] = name
            full_binding = bindings[name]
            if effectful and not full_binding.writable:
                noun = "view" if isinstance(actual_type, ViewType) else "array" if isinstance(actual_type, ArrayType) else "buffer"
                raise InscriptionError(f"cannot pass read-only {noun} {name} to effectful phrase `{target.display_name}`", call.line)
            continue
        if isinstance(expected, RecordType):
            _require_record_argument(arg, expected, env, getattr(arg, "line", call.line), records)
            continue
        actual = _infer_call_scalar_argument_type(arg, expected, env, functions, records)
        if actual != expected:
            argument_name = _argument_name(arg)
            if argument_name == "argument":
                argument_name = param.name
            raise InscriptionError(
                f"argument {argument_name} must have type {format_type(expected)}, got {format_type(actual)}",
                getattr(arg, "line", call.line),
            )


def _check_call_argument_types(
    call: Call,
    target: Function,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue] | None = None,
) -> None:
    _check_call_arity(call, target)
    constants = constants or {}
    seen_storage_names: set[str] = set()
    for arg, param in zip(call.args, target.params, strict=True):
        expected = resolve_value_type(param.type_name, call.line, records, constants, functions, {})
        if isinstance(expected, BufferType):
            name, _binding_type = _require_buffer_argument(arg, expected, env, getattr(arg, "line", call.line), records)
            if name in seen_storage_names:
                raise InscriptionError(f"buffer {name} cannot be passed to multiple buffer parameters in one call", call.line)
            seen_storage_names.add(name)
            continue
        if isinstance(expected, ViewType):
            name, _binding_type = _require_view_argument(arg, expected, env, getattr(arg, "line", call.line), records)
            if name in seen_storage_names:
                raise InscriptionError(f"view {name} cannot be passed to multiple view parameters in one call", call.line)
            seen_storage_names.add(name)
            continue
        if isinstance(expected, RecordType):
            _require_record_argument(arg, expected, env, getattr(arg, "line", call.line), records)
            continue
        actual = _infer_call_scalar_argument_type(arg, expected, env, functions, records)
        if actual != expected:
            argument_name = _argument_name(arg)
            if argument_name == "argument":
                argument_name = param.name
            raise InscriptionError(
                f"argument {argument_name} must have type {format_type(expected)}, got {format_type(actual)}",
                getattr(arg, "line", call.line),
            )


def _check_call_arity(call: Call, target: Function) -> None:
    if len(call.args) != len(target.params):
        raise InscriptionError(
            f"phrase '{target.name}' expects {len(target.params)} argument(s), got {len(call.args)}", call.line
        )


def _require_buffer_argument(
    arg: Expr,
    expected: BufferType,
    env: dict[str, ValueType],
    line: int,
    records: dict[str, RecordDecl],
) -> tuple[str, BufferType]:
    name = _argument_name(arg)
    actual = env.get(name) if isinstance(arg, Variable) else None
    if actual is None:
        try:
            actual_type = infer_expr_type(arg, env, {}, records)
        except Exception:
            actual_type = None
        got = format_type(actual_type) if actual_type is not None else "non-buffer expression"
        raise InscriptionError(f"argument {name} must be {format_type(expected)}, got {got}", line)
    if not isinstance(actual, BufferType):
        if isinstance(actual, ArrayType):
            raise InscriptionError(f"argument {name} must have type {format_type(expected)}, got {format_type(actual)}", line)
        raise InscriptionError(f"argument {name} must be {format_type(expected)}, got {format_type(actual)}", line)
    if actual != expected:
        raise InscriptionError(
            f"buffer argument {name} must have type {format_type(expected)}, got {format_type(actual)}", line
        )
    return name, actual


def _require_view_argument(
    arg: Expr,
    expected: ViewType,
    env: dict[str, ValueType],
    line: int,
    records: dict[str, RecordDecl],
) -> tuple[str, BufferType | ArrayType | ViewType]:
    name = _argument_name(arg)
    actual = env.get(name) if isinstance(arg, Variable) else None
    if actual is None:
        try:
            actual_type = infer_expr_type(arg, env, {}, records)
        except Exception:
            actual_type = None
        got = format_type(actual_type) if actual_type is not None else "non-view expression"
        raise InscriptionError(f"argument {name} must have type {format_type(expected)}, got {got}", line)
    if isinstance(actual, BufferType):
        if actual.element_type != expected.element_type:
            raise InscriptionError(
                f"argument {name} must have type {format_type(expected)}, got {format_type(actual)}", line
            )
        return name, actual
    if isinstance(actual, ArrayType):
        if actual.element_type != expected.element_type:
            raise InscriptionError(
                f"argument {name} must have type {format_type(expected)}, got {format_type(actual)}", line
            )
        return name, actual
    if isinstance(actual, ViewType):
        if actual.element_type != expected.element_type:
            raise InscriptionError(
                f"argument {name} must have type {format_type(expected)}, got {format_type(actual)}", line
            )
        return name, actual
    raise InscriptionError(f"argument {name} must have type {format_type(expected)}, got {format_type(actual)}", line)


def _require_record_argument(
    arg: Expr,
    expected: RecordType,
    env: dict[str, ValueType],
    line: int,
    records: dict[str, RecordDecl],
) -> tuple[str, RecordType]:
    if expected.name not in records:
        raise InscriptionError(f"unknown type {expected.name}", line)
    name = _argument_name(arg)
    actual = env.get(name) if isinstance(arg, Variable) else None
    if actual is None:
        try:
            actual_type = infer_expr_type(arg, env, {}, records)
        except Exception:
            actual_type = None
        got = format_type(actual_type) if actual_type is not None else "non-record expression"
        raise InscriptionError(f"argument {name} must have type {expected.name}, got {got}", line)
    if not isinstance(actual, RecordType):
        raise InscriptionError(f"argument {name} must have type {expected.name}, got {format_type(actual)}", line)
    if actual != expected:
        raise InscriptionError(f"argument {name} must have type {expected.name}, got {actual.name}", line)
    return name, actual


def _infer_call_scalar_argument_type(
    arg: Expr,
    expected: ValueType,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> ValueType:
    if isinstance(arg, Variable):
        actual = env.get(arg.name)
        if isinstance(actual, BufferType | ArrayType | ViewType | RecordType):
            return actual
    return _infer_declared_type(arg, expected, env, functions, records)


def _argument_name(arg: Expr) -> str:
    if isinstance(arg, Variable):
        return arg.name
    return "argument"


def _infer_declared_type(
    expr: Expr,
    expected: ValueType,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue] | None = None,
) -> ValueType:
    try:
        return infer_expr_type(expr, env, functions, records, expected=expected, constants=constants)
    except InscriptionError as expected_error:
        if isinstance(expr, Variable) and "record " in str(expected_error) and "cannot be used as a scalar value" in str(expected_error):
            raise
        if _should_preserve_expected_error(expected_error):
            raise
        try:
            return infer_expr_type(expr, env, functions, records, constants=constants)
        except InscriptionError:
            raise expected_error


def _should_preserve_expected_error(error: InscriptionError) -> bool:
    message = str(error)
    return (
        ("integer literal" in message and "out of range" in message)
        or message.startswith("floating literal")
        or message.startswith("constant floating expression")
        or message.startswith("cannot cast")
    )


def _env_types(bindings: dict[str, Binding]) -> dict[str, ValueType]:
    return {name: binding.type_name for name, binding in bindings.items()}


def _constant_env_types(constants: dict[str, ConstValue]) -> dict[str, ValueType]:
    return {name: value.type_name for name, value in constants.items()}


def _constant_bindings(constants: dict[str, ConstValue]) -> dict[str, Binding]:
    return {
        name: Binding(value.type_name, "constant", 0, writable=False)
        for name, value in constants.items()
    }


def resolve_value_type(
    type_name: ValueType,
    line: int,
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
    functions: dict[str, Function],
    env: dict[str, ValueType],
) -> ValueType:
    type_name = resolve_named_value_type(type_name)
    if isinstance(type_name, BufferType):
        return resolve_buffer_type(type_name, line, records, constants, functions, env)
    if isinstance(type_name, ArrayType):
        return resolve_array_type(type_name, line, records, constants, functions, env)
    if isinstance(type_name, ViewType):
        type_name = ViewType(resolve_value_type(type_name.element_type, line, records, constants, functions, env), type_name.length)
        _check_view_type(type_name, line)
        return type_name
    return type_name


def resolve_buffer_type(
    buffer_type: BufferType,
    line: int,
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
    functions: dict[str, Function],
    env: dict[str, ValueType],
) -> BufferType:
    length = evaluate_buffer_length(buffer_type.length, line, records, constants, functions, env)
    return BufferType(length, resolve_value_type(buffer_type.element_type, line, records, constants, functions, env))


def resolve_array_type(
    array_type: ArrayType,
    line: int,
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
    functions: dict[str, Function],
    env: dict[str, ValueType],
) -> ArrayType:
    length = evaluate_buffer_length(array_type.length, line, records, constants, functions, env)
    return ArrayType(length, resolve_value_type(array_type.element_type, line, records, constants, functions, env))


def evaluate_buffer_length(
    length: int | Expr,
    line: int,
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
    functions: dict[str, Function],
    env: dict[str, ValueType],
) -> int:
    if isinstance(length, int):
        value = length
        value_type: ValueType = "i32"
    else:
        merged_env = {**_constant_env_types(constants), **env}
        try:
            const_value = evaluate_const_expr(length, merged_env, functions, records, constants)
        except CompileTimeEvaluationError as exc:
            raise InscriptionError("buffer length must be compile-time evaluable", exc.line or line) from exc
        value = int(const_value.value)
        value_type = const_value.type_name
    if not is_integer_type(value_type):
        raise InscriptionError(f"buffer length must be an integer type, got {format_type(value_type)}", line)
    if value < 1:
        raise InscriptionError("buffer length must be at least 1", line)
    return value


def _check_compile_time_check(
    stmt: CheckStmt,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    merged_env = {**_constant_env_types(constants), **env}
    actual = infer_expr_type(stmt.expr, merged_env, functions, records, constants=constants)
    if actual != "i1":
        raise InscriptionError(f"check expression must have type i1, got {format_type(actual)}", stmt.line)
    try:
        value = evaluate_const_expr(stmt.expr, merged_env, functions, records, constants, expected="i1")
    except CompileTimeEvaluationError as exc:
        detail = str(exc)
        suffix = f"; {detail}" if detail.endswith("runtime binding") else ""
        raise InscriptionError(f"check expression must be compile-time evaluable{suffix}", exc.line or stmt.line) from exc
    if value.value is not True:
        raise InscriptionError("compile-time check failed", stmt.line)


def _check_require(
    stmt: RequireStmt,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    merged_env = {**_constant_env_types(constants), **env}
    actual = infer_expr_type(stmt.expr, merged_env, functions, records, constants=constants)
    if actual != "i1":
        raise InscriptionError(f"require condition must have type i1, got {format_type(actual)}", stmt.line)
    try:
        value = evaluate_const_expr(stmt.expr, merged_env, functions, records, constants, expected="i1")
    except CompileTimeEvaluationError:
        return
    if value.value is not True:
        raise InscriptionError("require condition is known to be false", stmt.line)


def evaluate_const_expr(
    expr: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
    *,
    expected: ValueType | None = None,
) -> ConstValue:
    type_name = infer_expr_type(expr, env, functions, records, expected=expected, constants=constants)
    if isinstance(type_name, RecordType | BufferType | ArrayType | ViewType):
        raise CompileTimeEvaluationError("record value is not compile-time evaluable", getattr(expr, "line", None))

    if isinstance(expr, Integer):
        if is_float_type(type_name) and expr.is_word_zero:
            assert isinstance(type_name, str)
            return ConstValue(type_name, normalize_float(0.0, type_name))
        assert isinstance(type_name, str) and is_integer_type(type_name)
        return ConstValue(type_name, normalize_integer(expr.value, type_name))
    if isinstance(expr, Float):
        assert isinstance(type_name, str) and is_float_type(type_name)
        return ConstValue(type_name, normalize_float(parse_float_literal(expr.text, expr.line), type_name))
    if isinstance(expr, Boolean):
        return ConstValue("i1", expr.value)
    if isinstance(expr, EnumCase):
        info = ACTIVE_ENUMS.get(expr.type_name)
        if info is None:
            raise InscriptionError(f"unknown type {expr.type_name}", expr.line)
        if expr.case_name not in info.cases:
            raise InscriptionError(f"enum {expr.type_name} has no case {expr.case_name}", expr.line)
        enum_type = EnumType(info.name, info.underlying_type)
        if expected is not None and enum_type != expected:
            require_type(enum_type, expected, expr.line)
        return ConstValue(enum_type, info.cases[expr.case_name])
    if isinstance(expr, Variable):
        if expr.name in constants:
            value = constants[expr.name]
            if expected is not None and value.type_name != expected:
                require_type(value.type_name, expected, expr.line)
            return value
        if expr.name in env:
            raise CompileTimeEvaluationError(f"{expr.name} is a runtime binding", expr.line)
        raise InscriptionError(f"unknown binding {expr.name}", expr.line)
    if isinstance(expr, LengthOf):
        binding_type = env.get(expr.name)
        if binding_type is None:
            raise InscriptionError(f"unknown binding {expr.name}", expr.line)
        if not isinstance(binding_type, BufferType | ArrayType | ViewType):
            raise InscriptionError(f"length of {expr.name} requires a buffer, got {format_type(binding_type)}", expr.line)
        if not isinstance(binding_type.length, int):
            raise CompileTimeEvaluationError(f"length of {expr.name} is not compile-time evaluable", expr.line)
        return ConstValue("i32", binding_type.length)
    if isinstance(expr, SizeOfType):
        return ConstValue("i32", layout_info(records[expr.type_name]).size)
    if isinstance(expr, AlignmentOfType):
        return ConstValue("i32", layout_info(records[expr.type_name]).alignment)
    if isinstance(expr, OffsetOfField):
        return ConstValue("i32", layout_info(records[expr.type_name]).field_offsets[expr.field])
    if isinstance(expr, FieldAccess):
        qualified_constant = f"{expr.name}.{expr.field}"
        if qualified_constant in constants and expr.name not in env:
            value = constants[qualified_constant]
            if expected is not None and value.type_name != expected:
                require_type(value.type_name, expected, expr.line)
            return value
        raise CompileTimeEvaluationError("expression is not compile-time evaluable", expr.line)
    if isinstance(expr, Cast):
        target_type = infer_cast_type(expr, env, functions, records)
        if isinstance(target_type, EnumType):
            source = evaluate_const_expr(expr.expr, env, functions, records, constants, expected=target_type.underlying_type if isinstance(expr.expr, Integer) else None)
            if isinstance(source.type_name, EnumType):
                if source.type_name != target_type:
                    raise InscriptionError(
                        f"cannot cast {format_type(source.type_name)} to {format_type(target_type)}; cast through {source.type_name.underlying_type} first",
                        expr.line,
                    )
                return ConstValue(target_type, int(source.value))
            if source.type_name != target_type.underlying_type:
                raise InscriptionError(
                    f"cannot cast {format_type(source.type_name)} to {format_type(target_type)}; cast to {target_type.underlying_type} first",
                    expr.line,
                )
            return ConstValue(target_type, int(source.value))
        source = evaluate_const_expr(expr.expr, env, functions, records, constants)
        source_type = source.type_name.underlying_type if isinstance(source.type_name, EnumType) else source.type_name
        assert isinstance(source_type, str) and isinstance(target_type, str)
        return ConstValue(target_type, cast_const_value(source.value, source_type, target_type))
    if isinstance(expr, Unary):
        operand_expected = "i1" if expr.op == "not" else type_name
        operand = evaluate_const_expr(expr.expr, env, functions, records, constants, expected=operand_expected)
        if expr.op == "not":
            return ConstValue("i1", not bool(operand.value))
        if expr.op == "bitwise not":
            assert isinstance(type_name, str)
            return ConstValue(type_name, normalize_integer(~to_bits(int(operand.value), type_name), type_name))
    if isinstance(expr, Binary):
        if expr.op in {"and", "or"}:
            left = evaluate_const_expr(expr.left, env, functions, records, constants, expected="i1")
            right = evaluate_const_expr(expr.right, env, functions, records, constants, expected="i1")
            return ConstValue("i1", bool(left.value) and bool(right.value) if expr.op == "and" else bool(left.value) or bool(right.value))
        left = evaluate_const_expr(expr.left, env, functions, records, constants, expected=type_name)
        right = evaluate_const_expr(expr.right, env, functions, records, constants, expected=type_name)
        assert isinstance(type_name, str)
        return ConstValue(type_name, evaluate_numeric_binary(expr.op, left.value, right.value, type_name, expr.line))
    if isinstance(expr, Comparison):
        operand_type = infer_comparison_operand_type(expr, env, functions, records)
        left = evaluate_const_expr(expr.left, env, functions, records, constants, expected=operand_type)
        right = evaluate_const_expr(expr.right, env, functions, records, constants, expected=operand_type)
        return ConstValue("i1", evaluate_comparison(expr.pred, left.value, right.value, operand_type))
    if isinstance(expr, MatchExpr):
        infer_match_expression_type(expr, env, functions, records, expected=type_name, constants=constants)
        scrutinee_type = infer_expr_type(expr.scrutinee, env, functions, records, constants=constants)
        scrutinee = evaluate_const_expr(expr.scrutinee, env, functions, records, constants, expected=scrutinee_type)
        result_type = type_name
        for arm in expr.arms:
            pattern = evaluate_const_expr(arm.pattern, env, functions, records, constants, expected=scrutinee_type)
            if _const_values_equal(scrutinee, pattern):
                return evaluate_const_expr(arm.expr, env, functions, records, constants, expected=result_type)
        return evaluate_const_expr(expr.otherwise, env, functions, records, constants, expected=result_type)
    raise CompileTimeEvaluationError("expression is not compile-time evaluable", getattr(expr, "line", None))


def _const_values_equal(left: ConstValue, right: ConstValue) -> bool:
    if left.type_name != right.type_name:
        return False
    if left.type_name == "i1":
        return bool(left.value) == bool(right.value)
    if is_float_type(left.type_name):
        return float(left.value) == float(right.value)
    return int(left.value) == int(right.value)


def normalize_integer(value: int, type_name: TypeName) -> int:
    bits = TYPE_WIDTHS[type_name]
    mask = (1 << bits) - 1
    raw = value & mask
    if is_signed_type(type_name) and raw >= (1 << (bits - 1)):
        return raw - (1 << bits)
    return raw


def to_bits(value: int, type_name: TypeName) -> int:
    return value & ((1 << TYPE_WIDTHS[type_name]) - 1)


def parse_float_literal(text: str, line: int) -> float:
    try:
        value = float(text)
    except ValueError as exc:  # pragma: no cover - tokenizer should prevent this
        raise InscriptionError(f"invalid floating literal {text}", line) from exc
    if not math.isfinite(value):
        raise InscriptionError(f"floating literal {text} is outside supported finite range", line)
    return value


def normalize_float(value: float, type_name: TypeName) -> float:
    if not math.isfinite(value):
        raise InscriptionError("constant floating expression is not finite")
    if type_name == "f32":
        try:
            return struct.unpack("!f", struct.pack("!f", float(value)))[0]
        except OverflowError as exc:
            raise InscriptionError("constant floating expression is not finite") from exc
    if type_name == "f64":
        return float(value)
    raise AssertionError(type_name)  # pragma: no cover


def cast_const_value(value: int | bool | float, source_type: TypeName, target_type: TypeName) -> int | float:
    if is_float_type(source_type) or is_float_type(target_type):
        if source_type == "i1" or target_type == "i1":
            raise InscriptionError(f"cannot cast {source_type} to {target_type}")
        if is_float_type(source_type) and is_float_type(target_type):
            return normalize_float(float(value), target_type)
        if is_float_type(source_type) and is_integer_type(target_type):
            return normalize_integer(int(float(value)), target_type)
        if is_integer_type(source_type) and is_float_type(target_type):
            int_value = int(value)
            if source_type in UNSIGNED_INTEGER_TYPES:
                int_value = to_bits(int_value, source_type)
            return normalize_float(float(int_value), target_type)
        raise InscriptionError(f"cannot cast {source_type} to {target_type}")
    source_bits = to_bits(int(value), source_type)
    if type_width(source_type) == type_width(target_type):
        return normalize_integer(source_bits, target_type)
    if type_width(source_type) > type_width(target_type):
        return normalize_integer(source_bits, target_type)
    if is_signed_type(source_type):
        return normalize_integer(normalize_integer(source_bits, source_type), target_type)
    return normalize_integer(source_bits, target_type)


def trunc_div(left: int, right: int) -> int:
    quotient = abs(left) // abs(right)
    return -quotient if (left < 0) ^ (right < 0) else quotient


def evaluate_integer_binary(op: str, left: int, right: int, type_name: TypeName, line: int) -> int:
    if op == "plus":
        return normalize_integer(left + right, type_name)
    if op == "minus":
        return normalize_integer(left - right, type_name)
    if op == "times":
        return normalize_integer(left * right, type_name)
    if op == "divided by":
        if right == 0:
            raise InscriptionError("constant expression divides by zero", line)
        result = trunc_div(left, right) if is_signed_type(type_name) else to_bits(left, type_name) // to_bits(right, type_name)
        return normalize_integer(result, type_name)
    if op == "remainder":
        if right == 0:
            raise InscriptionError("constant expression divides by zero", line)
        result = left - trunc_div(left, right) * right if is_signed_type(type_name) else to_bits(left, type_name) % to_bits(right, type_name)
        return normalize_integer(result, type_name)
    if op == "bitwise and":
        return normalize_integer(to_bits(left, type_name) & to_bits(right, type_name), type_name)
    if op == "bitwise xor":
        return normalize_integer(to_bits(left, type_name) ^ to_bits(right, type_name), type_name)
    if op == "bitwise or":
        return normalize_integer(to_bits(left, type_name) | to_bits(right, type_name), type_name)
    if op in {"shifted left by", "shifted right by"}:
        amount = int(right)
        if amount < 0 or amount >= type_width(type_name):
            raise InscriptionError(f"constant shift amount {amount} is out of range for {type_name}", line)
        if op == "shifted left by":
            return normalize_integer(to_bits(left, type_name) << amount, type_name)
        if is_signed_type(type_name):
            return normalize_integer(left >> amount, type_name)
        return normalize_integer(to_bits(left, type_name) >> amount, type_name)
    raise AssertionError(op)  # pragma: no cover


def evaluate_float_binary(op: str, left: float, right: float, type_name: TypeName, line: int) -> float:
    if op == "plus":
        return normalize_float(left + right, type_name)
    if op == "minus":
        return normalize_float(left - right, type_name)
    if op == "times":
        return normalize_float(left * right, type_name)
    if op == "divided by":
        if right == 0.0:
            raise InscriptionError("constant expression divides by zero", line)
        return normalize_float(left / right, type_name)
    raise InscriptionError(f"{op} requires integer operands, got {type_name} and {type_name}", line)


def evaluate_numeric_binary(op: str, left: int | bool | float, right: int | bool | float, type_name: TypeName, line: int) -> int | float:
    if is_float_type(type_name):
        return evaluate_float_binary(op, float(left), float(right), type_name, line)
    return evaluate_integer_binary(op, int(left), int(right), type_name, line)


def evaluate_comparison(pred: str, left: int | bool | float, right: int | bool | float, type_name: ValueType) -> bool:
    type_name = storage_type(type_name)
    assert isinstance(type_name, str)
    if is_float_type(type_name):
        lhs = float(left)
        rhs = float(right)
        if not math.isfinite(lhs) or not math.isfinite(rhs):
            return False
        if pred == "eq":
            return lhs == rhs
        if pred == "ne":
            return lhs != rhs
        if pred == "slt":
            return lhs < rhs
        if pred == "sle":
            return lhs <= rhs
        if pred == "sgt":
            return lhs > rhs
        if pred == "sge":
            return lhs >= rhs
        raise AssertionError(pred)  # pragma: no cover
    lhs = int(left) if is_signed_type(type_name) else to_bits(int(left), type_name)
    rhs = int(right) if is_signed_type(type_name) else to_bits(int(right), type_name)
    if pred == "eq":
        return lhs == rhs
    if pred == "ne":
        return lhs != rhs
    if pred == "slt":
        return lhs < rhs
    if pred == "sle":
        return lhs <= rhs
    if pred == "sgt":
        return lhs > rhs
    if pred == "sge":
        return lhs >= rhs
    raise AssertionError(pred)  # pragma: no cover


def infer_expr_type(
    expr: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    *,
    expected: ValueType | None = None,
    constants: dict[str, ConstValue] | None = None,
) -> ValueType:
    constants = constants or {}
    if isinstance(expr, Integer):
        if expected is not None:
            if is_float_type(expected) and expr.is_word_zero:
                return expected
            if not is_integer_type(expected):
                raise InscriptionError(f"integer literal cannot have type {format_type(expected)}", expr.line)
            _check_integer_literal_range(expr.value, expected, expr.line)
            return expected
        _check_integer_literal_range(expr.value, "i32", expr.line)
        return "i32"
    if isinstance(expr, Float):
        if expected is not None:
            if not is_float_type(expected):
                raise InscriptionError(f"floating literal cannot have type {format_type(expected)}", expr.line)
            normalize_float(parse_float_literal(expr.text, expr.line), expected)
            return expected
        normalize_float(parse_float_literal(expr.text, expr.line), "f64")
        return "f64"
    if isinstance(expr, Boolean):
        if expected is not None:
            require_type("i1", expected, expr.line)
        return "i1"
    if isinstance(expr, EnumCase):
        info = ACTIVE_ENUMS.get(expr.type_name)
        if info is None:
            raise InscriptionError(f"unknown type {expr.type_name}", expr.line)
        if expr.case_name not in info.cases:
            raise InscriptionError(f"enum {expr.type_name} has no case {expr.case_name}", expr.line)
        actual = EnumType(info.name, info.underlying_type)
        if expected is not None:
            require_type(actual, expected, expr.line)
        return actual
    if isinstance(expr, Variable):
        actual = constants[expr.name].type_name if expr.name in constants and expr.name not in env else _lookup_binding_type(expr.name, expr.line, env)
        if isinstance(actual, BufferType):
            raise InscriptionError(f"buffer {expr.name} cannot be used as a scalar value; use `{expr.name} at index`", expr.line)
        if isinstance(actual, ArrayType):
            raise InscriptionError(f"array {expr.name} cannot be used as a scalar value; use `{expr.name} at index`", expr.line)
        if isinstance(actual, ViewType):
            raise InscriptionError(f"view {expr.name} cannot be used as a scalar value; use `{expr.name} at index`", expr.line)
        if isinstance(actual, RecordType):
            if expected is None or expected == actual:
                return actual
            raise InscriptionError(
                f"record {expr.name} cannot be used as a scalar value; use a field such as {expr.name}.{_first_record_field(actual, records)}",
                expr.line,
            )
        if expected is not None:
            require_type(actual, expected, expr.line)
        return actual
    if isinstance(expr, BufferLoad):
        buffer_type = _require_indexable_type(expr.name, expr.line, env)
        _check_storage_index(expr.name, buffer_type, expr.index, env, functions, records, constants)
        if expected is not None:
            require_type(buffer_type.element_type, expected, expr.line)
        return buffer_type.element_type
    if isinstance(expr, LengthOf):
        binding_type = env.get(expr.name)
        if binding_type is None:
            raise InscriptionError(f"unknown binding {expr.name}", expr.line)
        if not isinstance(binding_type, BufferType | ArrayType | ViewType):
            raise InscriptionError(f"length of {expr.name} requires a buffer, got {format_type(binding_type)}", expr.line)
        if isinstance(binding_type, BufferType | ArrayType) and not isinstance(binding_type.length, int):
            raise InscriptionError("buffer length must be compile-time evaluable", expr.line)
        if binding_type.length is not None and binding_type.length > INTEGER_RANGES["i32"][1]:
            raise InscriptionError(f"buffer length {binding_type.length} does not fit in i32", expr.line)
        if expected is not None:
            require_type("i32", expected, expr.line)
        return "i32"
    if isinstance(expr, SizeOfType):
        _require_layout_record_decl(expr.type_name, expr.line, records, f"size of {expr.type_name}")
        if expected is not None:
            require_type("i32", expected, expr.line)
        return "i32"
    if isinstance(expr, AlignmentOfType):
        _require_layout_record_decl(expr.type_name, expr.line, records, f"alignment of {expr.type_name}")
        if expected is not None:
            require_type("i32", expected, expr.line)
        return "i32"
    if isinstance(expr, OffsetOfField):
        record = _require_layout_record_decl(expr.type_name, expr.line, records, f"offset of {expr.field} in {expr.type_name}")
        if expr.field not in layout_info(record).field_offsets:
            raise InscriptionError(f"layout record {expr.type_name} has no field {expr.field}", expr.line)
        if expected is not None:
            require_type("i32", expected, expr.line)
        return "i32"
    if isinstance(expr, FieldAccess):
        qualified_constant = f"{expr.name}.{expr.field}"
        if expr.name not in env and qualified_constant in constants:
            actual = constants[qualified_constant].type_name
            if expected is not None:
                require_type(actual, expected, expr.line)
            return actual
        record_type = _require_record_type(expr.name, expr.line, env)
        field_type = _require_record_field(record_type, expr.field, expr.line, records)
        if expected is not None:
            require_type(field_type, expected, expr.line)
        return field_type
    if isinstance(expr, RecordConstructor):
        actual = infer_record_constructor_type(expr, env, functions, records)
        if expected is not None and actual != expected:
            raise InscriptionError(f"expected {format_type(expected)}, got {format_type(actual)}", expr.line)
        return actual
    if isinstance(expr, LayoutRead):
        actual = infer_layout_read_type(expr, env, functions, records, constants)
        if expected is not None and actual != expected:
            raise InscriptionError(f"expected {format_type(expected)}, got {format_type(actual)}", expr.line)
        return actual
    if isinstance(expr, Unary):
        return infer_unary_type(expr, env, functions, records, expected=expected)
    if isinstance(expr, Cast):
        return infer_cast_type(expr, env, functions, records, expected=expected)
    if isinstance(expr, Binary):
        return infer_binary_type(expr, env, functions, records, expected=expected)
    if isinstance(expr, Call):
        target = _lookup_phrase(expr.name, expr.line, functions)
        if target.return_type is None:
            raise InscriptionError(f"phrase `{target.display_name}` does not return a value", expr.line)
        _check_call_argument_types(expr, target, env, functions, records, constants)
        if expected is not None:
            require_type(target.return_type, expected, expr.line)
        return target.return_type
    if isinstance(expr, Comparison):
        infer_comparison_operand_type(expr, env, functions, records)
        if expected is not None:
            require_type("i1", expected, expr.line)
        return "i1"
    if isinstance(expr, WhenExpr):
        if expected is None:
            expected = infer_expr_type(expr.otherwise, env, functions, records)
        for case in expr.cases:
            actual = _infer_declared_type(case.expr, expected, env, functions, records)
            if actual != expected:
                raise InscriptionError(
                    f"guarded value branches must have matching types, got {format_type(expected)} and {format_type(actual)}",
                    case.line,
                )
            condition_type = infer_i1_operand_type(case.condition, env, functions, records)
            if condition_type != "i1":
                raise InscriptionError(f"value block condition must be i1, got {condition_type}", case.line)
        otherwise_type = _infer_declared_type(expr.otherwise, expected, env, functions, records)
        if otherwise_type != expected:
            raise InscriptionError(
                f"guarded value branches must have matching types, got {format_type(expected)} and {format_type(otherwise_type)}",
                expr.line,
            )
        return expected
    if isinstance(expr, MatchExpr):
        return infer_match_expression_type(expr, env, functions, records, expected=expected, constants=constants)
    raise AssertionError(expr)  # pragma: no cover


def infer_match_expression_type(
    expr: MatchExpr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    *,
    expected: ValueType | None = None,
    constants: dict[str, ConstValue] | None = None,
) -> ValueType:
    constants = constants or {}
    scrutinee_type = infer_match_scrutinee_type(expr.scrutinee, env, functions, records, constants=constants)
    _require_match_scrutinee_type(scrutinee_type, expr.line)
    if not expr.arms:
        raise InscriptionError("match expression requires at least one pattern arm", expr.line)
    _check_match_patterns(tuple(arm.pattern for arm in expr.arms), scrutinee_type, env, functions, records, constants)

    result_type = expected if expected is not None else (
        infer_expr_type(expr.arms[0].expr, env, functions, records, constants=constants)
        if expr.arms
        else infer_expr_type(expr.otherwise, env, functions, records, constants=constants)
    )
    if isinstance(result_type, BufferType | ArrayType | ViewType):
        raise InscriptionError(f"match expression cannot return {format_type(result_type)}", expr.line)
    for arm in expr.arms:
        actual = _infer_declared_type(arm.expr, result_type, env, functions, records, constants)
        if actual != result_type:
            raise InscriptionError(
                f"match expression arms must have matching types, got {format_type(result_type)} and {format_type(actual)}",
                arm.line,
            )
    otherwise_type = _infer_declared_type(expr.otherwise, result_type, env, functions, records, constants)
    if otherwise_type != result_type:
        raise InscriptionError(
            f"match expression arms must have matching types, got {format_type(result_type)} and {format_type(otherwise_type)}",
            expr.line,
        )
    return result_type


def infer_match_scrutinee_type(
    expr: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    *,
    constants: dict[str, ConstValue] | None = None,
) -> ValueType:
    if isinstance(expr, Variable) and expr.name in env:
        return env[expr.name]
    return infer_expr_type(expr, env, functions, records, constants=constants)


def _require_match_scrutinee_type(type_name: ValueType, line: int) -> None:
    if type_name == "i1" or is_integer_type(type_name) or isinstance(type_name, EnumType):
        return
    raise InscriptionError(f"match scrutinee must be i1, integer, or enum, got {format_type(type_name)}", line)


def _check_match_patterns(
    patterns: tuple[Expr, ...],
    scrutinee_type: ValueType,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> None:
    seen: dict[tuple[str, int | bool], str] = {}
    for pattern in patterns:
        pattern_type = _infer_match_pattern_type(pattern, scrutinee_type, env, functions, records, constants)
        if pattern_type != scrutinee_type:
            raise InscriptionError(
                f"match pattern must have type {format_type(scrutinee_type)}, got {format_type(pattern_type)}",
                getattr(pattern, "line", None),
            )
        try:
            value = evaluate_const_expr(pattern, env, functions, records, constants, expected=scrutinee_type)
        except CompileTimeEvaluationError as exc:
            raise InscriptionError("match pattern must be compile-time evaluable", exc.line or getattr(pattern, "line", None)) from exc
        key = _match_pattern_key(value)
        label = _match_pattern_label(pattern, value)
        if key in seen:
            raise InscriptionError(f"match has duplicate pattern {label}", getattr(pattern, "line", None))
        seen[key] = label


def _infer_match_pattern_type(
    pattern: Expr,
    scrutinee_type: ValueType,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> ValueType:
    if isinstance(pattern, Integer):
        expected: ValueType | None
        if isinstance(scrutinee_type, EnumType):
            expected = scrutinee_type.underlying_type
        elif is_integer_type(scrutinee_type):
            expected = scrutinee_type
        else:
            expected = None
        return infer_expr_type(pattern, env, functions, records, expected=expected, constants=constants)
    if isinstance(pattern, Variable):
        if pattern.name not in constants:
            raise InscriptionError("match pattern must be compile-time evaluable", pattern.line)
        return constants[pattern.name].type_name
    if isinstance(pattern, FieldAccess):
        qualified_constant = f"{pattern.name}.{pattern.field}"
        if qualified_constant in constants and pattern.name not in env:
            return constants[qualified_constant].type_name
    return infer_expr_type(pattern, env, functions, records, constants=constants)


def _match_pattern_key(value: ConstValue) -> tuple[str, int | bool]:
    if value.type_name == "i1":
        return ("i1", bool(value.value))
    if isinstance(value.type_name, EnumType):
        return (value.type_name.name, int(value.value))
    return (format_type(value.type_name), int(value.value))


def _match_pattern_label(pattern: Expr, value: ConstValue) -> str:
    if isinstance(pattern, EnumCase):
        return f"{pattern.type_name}.{pattern.case_name}"
    if value.type_name == "i1":
        return "true" if bool(value.value) else "false"
    if isinstance(value.type_name, EnumType):
        info = ACTIVE_ENUMS.get(value.type_name.name)
        if info is not None:
            for case_name in info.case_order:
                if info.cases[case_name] == int(value.value):
                    return f"{value.type_name.name}.{case_name}"
    return str(int(value.value))


def infer_unary_type(
    expr: Unary,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    *,
    expected: ValueType | None = None,
) -> TypeName:
    if expr.op == "not":
        actual = infer_i1_operand_type(expr.expr, env, functions, records)
        if actual != "i1":
            raise InscriptionError(f"not requires i1 operand, got {format_type(actual)}", expr.line)
        if expected is not None:
            require_type("i1", expected, expr.line)
        return "i1"
    if expr.op == "bitwise not":
        target = expected if is_integer_type(expected) else None
        actual = infer_integer_operand_type(expr.expr, env, functions, records, expected=target)
        if not is_integer_type(actual):
            raise InscriptionError(f"bitwise not requires integer operand, got {format_type(actual)}", expr.line)
        if expected is not None:
            require_type(actual, expected, expr.line)
        return actual
    raise AssertionError(expr)  # pragma: no cover


def infer_cast_type(
    expr: Cast,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    *,
    expected: ValueType | None = None,
) -> ValueType:
    target_type = resolve_named_value_type(expr.target_type)
    if isinstance(target_type, RecordType):
        raise InscriptionError(f"cannot cast to {format_type(target_type)}", expr.line)

    if isinstance(target_type, EnumType):
        if isinstance(expr.expr, Integer):
            source_type = infer_expr_type(expr.expr, env, functions, records, expected=target_type.underlying_type)
        else:
            source_type = infer_expr_type(expr.expr, env, functions, records)
        if isinstance(source_type, EnumType):
            if source_type == target_type:
                if expected is not None:
                    require_type(target_type, expected, expr.line)
                return target_type
            raise InscriptionError(
                f"cannot cast {format_type(source_type)} to {format_type(target_type)}; cast through {source_type.underlying_type} first",
                expr.line,
            )
        if source_type == target_type.underlying_type:
            if expected is not None:
                require_type(target_type, expected, expr.line)
            return target_type
        raise InscriptionError(
            f"cannot cast {format_type(source_type)} to {format_type(target_type)}; cast to {target_type.underlying_type} first",
            expr.line,
        )

    source_type = infer_expr_type(expr.expr, env, functions, records)
    if isinstance(source_type, EnumType):
        if not isinstance(target_type, str) or target_type == "i1" or is_float_type(target_type):
            raise InscriptionError(f"cannot cast {format_type(source_type)} to {format_type(target_type)}", expr.line)
        if not is_integer_type(target_type):
            raise InscriptionError(f"cannot cast {format_type(source_type)} to {format_type(target_type)}", expr.line)
        if expected is not None:
            require_type(target_type, expected, expr.line)
        return target_type
    if (
        (source_type == "i1" and is_float_type(target_type))
        or (is_float_type(source_type) and target_type == "i1")
        or (not isinstance(source_type, str))
        or (not isinstance(target_type, str))
        or (not is_integer_type(source_type) and not is_float_type(source_type))
        or (not is_integer_type(target_type) and not is_float_type(target_type))
    ):
        raise InscriptionError(f"cannot cast {format_type(source_type)} to {format_type(target_type)}", expr.line)
    if expected is not None:
        require_type(target_type, expected, expr.line)
    return target_type


def infer_binary_type(
    expr: Binary,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    *,
    expected: ValueType | None = None,
) -> TypeName:
    if expr.op in {"and", "or"}:
        left_type = infer_i1_operand_type(expr.left, env, functions, records)
        right_type = infer_i1_operand_type(expr.right, env, functions, records)
        if left_type != "i1" or right_type != "i1":
            raise InscriptionError(
                f"{expr.op} requires i1 operands, got {format_type(left_type)} and {format_type(right_type)}", expr.line
            )
        if expected is not None:
            require_type("i1", expected, expr.line)
        return "i1"

    if expr.op in {"plus", "minus", "times", "divided by"}:
        return infer_numeric_pair_type(expr.op, expr.left, expr.right, env, functions, records, expr.line, expected=expected)

    if expr.op == "remainder":
        return infer_integer_pair_type(expr.op, expr.left, expr.right, env, functions, records, expr.line, expected=expected)

    if expr.op in {"bitwise and", "bitwise xor", "bitwise or"}:
        return infer_integer_pair_type(expr.op, expr.left, expr.right, env, functions, records, expr.line, expected=expected)

    if expr.op in {"shifted left by", "shifted right by"}:
        return infer_integer_pair_type(expr.op, expr.left, expr.right, env, functions, records, expr.line, expected=expected)

    raise AssertionError(expr)  # pragma: no cover


def infer_i1_operand_type(
    expr: Expr, env: dict[str, ValueType], functions: dict[str, Function], records: dict[str, RecordDecl]
) -> TypeName:
    try:
        return infer_expr_type(expr, env, functions, records, expected="i1")  # type: ignore[return-value]
    except InscriptionError:
        return infer_expr_type(expr, env, functions, records)  # type: ignore[return-value]


def infer_integer_operand_type(
    expr: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    *,
    expected: TypeName | None = None,
) -> TypeName:
    if expected is not None:
        try:
            return infer_expr_type(expr, env, functions, records, expected=expected)  # type: ignore[return-value]
        except InscriptionError as expected_error:
            if _should_preserve_expected_error(expected_error):
                raise
            return infer_expr_type(expr, env, functions, records)  # type: ignore[return-value]
    return infer_expr_type(expr, env, functions, records)  # type: ignore[return-value]


def infer_numeric_operand_type(
    expr: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    *,
    expected: TypeName | None = None,
) -> TypeName:
    if expected is not None:
        try:
            return infer_expr_type(expr, env, functions, records, expected=expected)  # type: ignore[return-value]
        except InscriptionError as expected_error:
            if _should_preserve_expected_error(expected_error):
                raise
            return infer_expr_type(expr, env, functions, records)  # type: ignore[return-value]
    return infer_expr_type(expr, env, functions, records)  # type: ignore[return-value]


def _is_numeric_literal(expr: Expr) -> bool:
    return isinstance(expr, Integer | Float)


def infer_numeric_pair_type(
    op: str,
    left: Expr,
    right: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    line: int,
    *,
    expected: ValueType | None = None,
) -> TypeName:
    target = expected if is_numeric_type(expected) else None
    if target is not None:
        left_type = infer_numeric_operand_type(left, env, functions, records, expected=target)
        right_type = infer_numeric_operand_type(right, env, functions, records, expected=target)
    elif _is_numeric_literal(left) and not _is_numeric_literal(right):
        right_type = infer_expr_type(right, env, functions, records)
        left_type = infer_numeric_operand_type(left, env, functions, records, expected=right_type if is_numeric_type(right_type) else None)  # type: ignore[arg-type]
    elif _is_numeric_literal(right) and not _is_numeric_literal(left):
        left_type = infer_expr_type(left, env, functions, records)
        right_type = infer_numeric_operand_type(right, env, functions, records, expected=left_type if is_numeric_type(left_type) else None)  # type: ignore[arg-type]
    else:
        left_type = infer_expr_type(left, env, functions, records)
        right_type = infer_numeric_operand_type(right, env, functions, records, expected=left_type if is_numeric_type(left_type) else None)  # type: ignore[arg-type]

    if not is_numeric_type(left_type) or not is_numeric_type(right_type):
        if isinstance(left_type, EnumType) or isinstance(right_type, EnumType):
            raise InscriptionError(f"{op} requires numeric primitive operands, got {format_type(left_type)} and {format_type(right_type)}", line)
        if not is_float_type(left_type) and not is_float_type(right_type):
            raise InscriptionError(f"{op} requires integer operands, got {format_type(left_type)} and {format_type(right_type)}", line)
        raise InscriptionError(f"{op} requires numeric operands, got {format_type(left_type)} and {format_type(right_type)}", line)
    if left_type != right_type:
        if is_integer_type(left_type) and is_integer_type(right_type):
            raise InscriptionError(
                f"{op} requires matching integer types, got {format_type(left_type)} and {format_type(right_type)}", line
            )
        raise InscriptionError(
            f"{op} requires matching numeric types, got {format_type(left_type)} and {format_type(right_type)}", line
        )
    if target is not None and left_type != target:
        if is_integer_type(left_type) and is_integer_type(target):
            raise InscriptionError(f"{op} requires matching integer types, got {format_type(left_type)} and {target}", line)
        raise InscriptionError(f"{op} requires matching numeric types, got {format_type(left_type)} and {format_type(target)}", line)
    assert isinstance(left_type, str)
    return left_type


def infer_integer_pair_type(
    op: str,
    left: Expr,
    right: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    line: int,
    *,
    expected: ValueType | None = None,
) -> TypeName:
    target = expected if is_integer_type(expected) else None
    if target is not None:
        left_type = infer_integer_operand_type(left, env, functions, records, expected=target)
        right_type = infer_integer_operand_type(right, env, functions, records, expected=target)
    elif isinstance(left, Integer) and not isinstance(right, Integer):
        right_type = infer_expr_type(right, env, functions, records)
        left_type = infer_integer_operand_type(left, env, functions, records, expected=right_type if is_integer_type(right_type) else None)  # type: ignore[arg-type]
    elif isinstance(right, Integer) and not isinstance(left, Integer):
        left_type = infer_expr_type(left, env, functions, records)
        right_type = infer_integer_operand_type(right, env, functions, records, expected=left_type if is_integer_type(left_type) else None)  # type: ignore[arg-type]
    else:
        left_type = infer_expr_type(left, env, functions, records)
        right_type = infer_integer_operand_type(right, env, functions, records, expected=left_type if is_integer_type(left_type) else None)  # type: ignore[arg-type]

    if not is_integer_type(left_type) or not is_integer_type(right_type):
        raise InscriptionError(f"{op} requires integer operands, got {format_type(left_type)} and {format_type(right_type)}", line)
    if left_type != right_type:
        raise InscriptionError(
            f"{op} requires matching integer types, got {format_type(left_type)} and {format_type(right_type)}", line
        )
    if target is not None and left_type != target:
        raise InscriptionError(f"{op} requires matching integer types, got {format_type(left_type)} and {target}", line)
    return left_type


def infer_comparison_operand_type(
    condition: Comparison, env: dict[str, ValueType], functions: dict[str, Function], records: dict[str, RecordDecl]
) -> ValueType:
    return infer_comparison_pair_type(condition.left, condition.right, env, functions, records, condition.line, condition.pred)


def infer_comparison_pair_type(
    left: Expr,
    right: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    line: int,
    pred: str,
) -> ValueType:
    left_type = infer_expr_type(left, env, functions, records)
    if _is_numeric_literal(right) and is_numeric_type(left_type):
        right_type = infer_numeric_operand_type(right, env, functions, records, expected=left_type)  # type: ignore[arg-type]
    else:
        right_type = infer_expr_type(right, env, functions, records)
    if _is_numeric_literal(left) and is_numeric_type(right_type):
        left_type = infer_numeric_operand_type(left, env, functions, records, expected=right_type)  # type: ignore[arg-type]

    if isinstance(left_type, EnumType) or isinstance(right_type, EnumType):
        if not isinstance(left_type, EnumType) or not isinstance(right_type, EnumType) or left_type != right_type:
            raise InscriptionError(
                f"comparison requires matching enum types, got {format_type(left_type)} and {format_type(right_type)}", line
            )
        if pred not in {"eq", "ne"}:
            raise InscriptionError(
                f"ordered comparisons are not supported for enum {format_type(left_type)}; cast to {left_type.underlying_type} first",
                line,
            )
        return left_type

    if not is_numeric_type(left_type) or not is_numeric_type(right_type):
        if not is_float_type(left_type) and not is_float_type(right_type):
            raise InscriptionError(
                f"comparison requires integer operands, got {format_type(left_type)} and {format_type(right_type)}", line
            )
        raise InscriptionError(
            f"comparison requires numeric operands, got {format_type(left_type)} and {format_type(right_type)}", line
        )
    if left_type != right_type:
        if is_integer_type(left_type) and is_integer_type(right_type):
            raise InscriptionError(
                f"comparison requires matching integer types, got {format_type(left_type)} and {format_type(right_type)}", line
            )
        raise InscriptionError(
            f"comparison requires matching numeric types, got {format_type(left_type)} and {format_type(right_type)}", line
        )
    return left_type


def _lookup_binding_type(name: str, line: int, env: dict[str, ValueType]) -> ValueType:
    try:
        return env[name]
    except KeyError as exc:
        raise InscriptionError(f"unknown binding {name}; variable '{name}' used before initialization", line) from exc


def _require_buffer_binding(name: str, line: int, bindings: dict[str, Binding]) -> Binding:
    binding = bindings.get(name)
    if binding is None:
        raise InscriptionError(f"unknown binding {name}", line)
    if not isinstance(binding.type_name, BufferType):
        raise InscriptionError(f"{name} is not a buffer", line)
    return binding


def _require_indexable_binding(name: str, line: int, bindings: dict[str, Binding]) -> Binding:
    binding = bindings.get(name)
    if binding is None:
        raise InscriptionError(f"unknown binding {name}", line)
    if not isinstance(binding.type_name, BufferType | ArrayType | ViewType):
        raise InscriptionError(f"{name} is not a buffer", line)
    return binding


def _require_buffer_type(name: str, line: int, env: dict[str, ValueType]) -> BufferType:
    binding_type = env.get(name)
    if binding_type is None:
        raise InscriptionError(f"unknown binding {name}", line)
    if not isinstance(binding_type, BufferType):
        raise InscriptionError(f"{name} is not a buffer", line)
    return binding_type


def _require_indexable_type(name: str, line: int, env: dict[str, ValueType]) -> BufferType | ArrayType | ViewType:
    binding_type = env.get(name)
    if binding_type is None:
        raise InscriptionError(f"unknown binding {name}", line)
    if not isinstance(binding_type, BufferType | ArrayType | ViewType):
        raise InscriptionError(f"{name} is not a buffer", line)
    return binding_type


def _require_record_type(name: str, line: int, env: dict[str, ValueType]) -> RecordType:
    binding_type = env.get(name)
    if binding_type is None:
        raise InscriptionError(f"unknown binding {name}", line)
    if not isinstance(binding_type, RecordType):
        raise InscriptionError(f"{name} is not a record", line)
    return binding_type


def _record_decl(record_type: RecordType, line: int, records: dict[str, RecordDecl]) -> RecordDecl:
    record = records.get(record_type.name)
    if record is None:
        raise InscriptionError(f"unknown record type {record_type.name}", line)
    return record


def _require_layout_record_decl(
    type_name: str,
    line: int,
    records: dict[str, RecordDecl],
    context: str,
) -> RecordDecl:
    record = records.get(type_name)
    if record is None:
        raise InscriptionError(f"unknown record type {type_name}", line)
    if record.layout_kind == "value":
        raise InscriptionError(f"{context} requires a layout record", line)
    return record


def _require_record_field(record_type: RecordType, field: str, line: int, records: dict[str, RecordDecl]) -> ValueType:
    record = _record_decl(record_type, line, records)
    for field_decl in record.fields:
        if field_decl.name == field:
                return field_decl.type_name
    raise InscriptionError(f"record {record_type.name} has no field {field}", line)


def _first_record_field(record_type: RecordType, records: dict[str, RecordDecl]) -> str:
    record = records.get(record_type.name)
    if record is None or not record.fields:
        return "field"
    return record.fields[0].name


def infer_record_constructor_type(
    expr: RecordConstructor,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> RecordType:
    record_type = RecordType(expr.type_name)
    record = _record_decl(record_type, expr.line, records)
    expected_names = [field.name for field in record.fields]
    actual_names = [field.name for field in expr.fields]
    for initializer in expr.fields:
        if initializer.name not in expected_names:
            raise InscriptionError(f"record {record.name} has no field {initializer.name}", initializer.line)
    if actual_names != expected_names:
        if len(actual_names) == len(expected_names) and set(actual_names) == set(expected_names):
            raise InscriptionError(
                f"record {record.name} initializer fields must appear in declaration order: {', '.join(expected_names)}",
                expr.line,
            )
        raise InscriptionError(f"record {record.name} initializer requires fields {', '.join(expected_names)}", expr.line)
    for initializer, field_decl in zip(expr.fields, record.fields, strict=True):
        actual = _infer_declared_type(initializer.expr, field_decl.type_name, env, functions, records)
        if actual != field_decl.type_name:
            raise InscriptionError(
                f"field {initializer.name} of {record.name} must have type {format_type(field_decl.type_name)}, got {format_type(actual)}",
                initializer.line,
            )
    return record_type


def infer_layout_read_type(
    expr: LayoutRead,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue] | None = None,
) -> RecordType:
    record = _require_layout_record_decl(expr.type_name, expr.line, records, f"read {expr.type_name}")
    buffer_type = _require_indexable_type(expr.buffer_name, expr.line, env)
    if buffer_type.element_type != "u8":
        if isinstance(buffer_type, ViewType):
            noun = "u8 buffer or view"
        elif isinstance(buffer_type, ArrayType):
            noun = "u8 buffer, view, or array"
        else:
            noun = "u8 buffer"
        raise InscriptionError(f"read {expr.type_name} requires a {noun}, got {format_type(buffer_type)}", expr.line)
    _check_layout_index(
        "layout read",
        "read",
        expr.type_name,
        expr.buffer_name,
        layout_info(record).size,
        buffer_type,
        expr.index,
        env,
        functions,
        records,
        constants,
    )
    return RecordType(expr.type_name)


def _check_buffer_index(
    name: str,
    buffer_type: BufferType,
    index: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue] | None = None,
) -> None:
    constants = constants or {}
    static_index = _static_integer_value(index, env, functions, records, constants)
    assert isinstance(buffer_type.length, int)
    if static_index is not None and not 0 <= static_index < buffer_type.length:
        raise InscriptionError(
            f"buffer index {static_index} is out of bounds for buffer {name} of length {buffer_type.length}", getattr(index, "line", None)
        )
    index_type = infer_expr_type(index, env, functions, records)
    if not is_integer_type(index_type):
        raise InscriptionError(
            f"buffer index must be an integer type, got {format_type(index_type)}", getattr(index, "line", None)
        )


def _check_array_index(
    name: str,
    array_type: ArrayType,
    index: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue] | None = None,
) -> None:
    constants = constants or {}
    static_index = _static_integer_value(index, env, functions, records, constants)
    assert isinstance(array_type.length, int)
    if static_index is not None and not 0 <= static_index < array_type.length:
        raise InscriptionError(
            f"array index {static_index} is out of bounds for array {name} of length {array_type.length}", getattr(index, "line", None)
        )
    index_type = infer_expr_type(index, env, functions, records)
    if not is_integer_type(index_type):
        raise InscriptionError(
            f"array index must be an integer type, got {format_type(index_type)}", getattr(index, "line", None)
        )


def _check_storage_index(
    name: str,
    storage_type: BufferType | ArrayType | ViewType,
    index: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue] | None = None,
) -> None:
    if isinstance(storage_type, BufferType):
        _check_buffer_index(name, storage_type, index, env, functions, records, constants)
        return
    if isinstance(storage_type, ArrayType):
        _check_array_index(name, storage_type, index, env, functions, records, constants)
        return
    constants = constants or {}
    static_index = _static_integer_value(index, env, functions, records, constants)
    if static_index is not None and storage_type.length is not None and not 0 <= static_index < storage_type.length:
        raise InscriptionError(
            f"view index {static_index} is out of bounds for view {name} of length {storage_type.length}",
            getattr(index, "line", None),
        )
    index_type = infer_expr_type(index, env, functions, records)
    if not is_integer_type(index_type):
        raise InscriptionError(
            f"buffer index must be an integer type, got {format_type(index_type)}", getattr(index, "line", None)
        )


def _static_storage_length(type_name: BufferType | ArrayType | ViewType) -> int | None:
    return type_name.length if isinstance(type_name.length, int) else None


def _check_layout_index(
    index_label: str,
    action: str,
    type_name: str,
    buffer_name: str,
    record_size: int,
    buffer_type: BufferType | ArrayType | ViewType,
    index: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue] | None = None,
) -> None:
    constants = constants or {}
    static_index = _static_integer_value(index, env, functions, records, constants)
    storage_length = _static_storage_length(buffer_type)
    if static_index is not None and storage_length is not None and not 0 <= static_index <= storage_length - record_size:
        raise InscriptionError(
            f"{action} {type_name} at index {static_index} exceeds buffer {buffer_name} of length {storage_length}",
            getattr(index, "line", None),
        )
    index_type = infer_expr_type(index, env, functions, records)
    if not is_integer_type(index_type):
        raise InscriptionError(
            f"{index_label} index must be an integer type, got {format_type(index_type)}", getattr(index, "line", None)
        )


def _static_integer_value(
    expr: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue],
) -> int | None:
    try:
        value = evaluate_const_expr(expr, {**_constant_env_types(constants), **env}, functions, records, constants)
    except (CompileTimeEvaluationError, InscriptionError):
        return None
    if not is_integer_type(value.type_name):
        return None
    return int(value.value)


def _check_integer_literal_range(value: int, type_name: TypeName, line: int) -> None:
    if type_name not in INTEGER_RANGES:
        raise InscriptionError(f"integer literal cannot have type {type_name}", line)
    low, high = INTEGER_RANGES[type_name]
    if not low <= value <= high:
        raise InscriptionError(f"integer literal {value} is out of range for {type_name}", line)


def require_type(actual: ValueType, expected: ValueType, line: int) -> None:
    if actual != expected:
        raise InscriptionError(f"expected {format_type(expected)}, got {format_type(actual)}", line)
