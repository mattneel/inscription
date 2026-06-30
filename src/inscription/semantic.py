from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Literal

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
    CheckStmt,
    Comparison,
    ConstantDecl,
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
BindingKind = Literal["param", "let", "buffer", "view", "index", "constant"]


@dataclass(frozen=True)
class Binding:
    type_name: ValueType
    kind: BindingKind
    line: int
    writable: bool = True
    root: str | None = None


@dataclass(frozen=True)
class ConstValue:
    type_name: TypeName
    value: int | bool | float


class CompileTimeEvaluationError(Exception):
    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.line = line


def analyze(program: Program) -> None:
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


def record_table(program: Program) -> dict[str, RecordDecl]:
    records: dict[str, RecordDecl] = {}
    for record in program.records:
        if record.name in SCALAR_TYPES:
            raise InscriptionError(f"record name {record.name} collides with scalar type", record.line)
        if record.name in records:
            raise InscriptionError(f"record {record.name} is already defined", record.line)
        if not record.fields:
            prefix = "record" if record.layout_kind == "value" else "layout record"
            raise InscriptionError(f"{prefix} {record.name} must declare at least one field", record.line)
        seen_fields: set[str] = set()
        for field in record.fields:
            if field.name in seen_fields:
                prefix = "record" if record.layout_kind == "value" else "layout record"
                raise InscriptionError(f"{prefix} {record.name} has duplicate field {field.name}", field.line)
            seen_fields.add(field.name)
            if record.layout_kind == "value":
                if not isinstance(field.type_name, str) or field.type_name not in SCALAR_TYPES:
                    raise InscriptionError(
                        f"record fields must be scalar types, got {format_type(field.type_name)}", field.line
                    )
            elif not isinstance(field.type_name, str) or field.type_name not in INTEGER_TYPES:
                raise InscriptionError(
                    f"layout record fields must be integer types, got {format_type(field.type_name)}", field.line
                )
        layout_info = compute_layout_info(record) if record.layout_kind != "value" else None
        records[record.name] = RecordDecl(record.name, record.fields, record.line, record.layout_kind, layout_info)
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
        if const.type_name not in SCALAR_TYPES:
            raise InscriptionError(f"constant {const.name} must have a scalar type", const.line)
        env = _constant_env_types(constants)
        try:
            value = evaluate_const_expr(const.expr, env, functions, records, constants, expected=const.type_name)
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
                f"constant {const.name} must have type {const.type_name}, got {format_type(actual)}", const.line
            ) from exc
        if value.type_name != const.type_name:
            raise InscriptionError(
                f"constant {const.name} must have type {const.type_name}, got {format_type(value.type_name)}", const.line
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


def mlir_type(type_name: TypeName) -> str:
    if type_name.startswith("u"):
        return f"i{TYPE_WIDTHS[type_name]}"
    return type_name


def memref_type(buffer_type: BufferType) -> str:
    return f"memref<{buffer_type.length}x{mlir_type(buffer_type.element_type)}>"


def format_type(type_name: ValueType) -> str:
    if isinstance(type_name, BufferType):
        return f"buffer of {type_name.length} {format_type(type_name.element_type)}"
    if isinstance(type_name, ViewType):
        return f"view of {type_name.element_type}"
    if isinstance(type_name, RecordType):
        return type_name.name
    return type_name


def is_integer_type(type_name: ValueType | None) -> bool:
    return type_name in INTEGER_TYPES


def is_float_type(type_name: ValueType | None) -> bool:
    return type_name in FLOAT_TYPES


def is_numeric_type(type_name: ValueType | None) -> bool:
    return type_name in NUMERIC_TYPES


def is_signed_type(type_name: TypeName) -> bool:
    return type_name in SIGNED_INTEGER_TYPES


def type_width(type_name: TypeName) -> int:
    return TYPE_WIDTHS[type_name]


def byte_width(type_name: TypeName) -> int:
    return TYPE_WIDTHS[type_name] // 8


def _align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def compute_layout_info(record: RecordDecl) -> LayoutInfo:
    offset = 0
    alignment = 1
    field_offsets: dict[str, int] = {}
    occupied: set[int] = set()
    for field in record.fields:
        assert isinstance(field.type_name, str)
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
    if not fn.body:
        raise InscriptionError(f"phrase '{fn.name}' must evaluate to a value", fn.line)
    bindings = _constant_bindings(constants)
    for name, type_name in resolved_params:
        bindings[name] = Binding(
            type_name,
            "param",
            fn.line,
            writable=not isinstance(type_name, BufferType | ViewType),
            root=name if isinstance(type_name, BufferType | ViewType) else None,
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


def _check_extern_function(fn: Function, records: dict[str, RecordDecl]) -> None:
    if fn.body:
        raise InscriptionError("extern phrase declarations cannot have bodies", fn.line)
    for param in fn.params:
        if not isinstance(param.type_name, str) or param.type_name not in SCALAR_TYPES:
            raise InscriptionError(
                f"extern phrase parameters must be scalar types, got {format_type(param.type_name)}",
                fn.line,
            )
    if fn.return_type is not None and (not isinstance(fn.return_type, str) or fn.return_type not in SCALAR_TYPES):
        if isinstance(fn.return_type, RecordType) and fn.return_type.name not in records:
            raise InscriptionError(f"unknown type {fn.return_type.name}", fn.line)
        raise InscriptionError(
            f"extern phrase return types must be scalar types, got {format_type(fn.return_type)}",
            fn.line,
        )



def _check_exported_function(fn: Function, records: dict[str, RecordDecl]) -> None:
    for param in fn.params:
        if not isinstance(param.type_name, str) or param.type_name not in SCALAR_TYPES:
            raise InscriptionError(
                f"exported phrase parameters must be scalar types, got {format_type(param.type_name)}",
                fn.line,
            )
    if fn.return_type is not None and (not isinstance(fn.return_type, str) or fn.return_type not in SCALAR_TYPES):
        if isinstance(fn.return_type, RecordType) and fn.return_type.name not in records:
            raise InscriptionError(f"unknown type {fn.return_type.name}", fn.line)
        raise InscriptionError(
            f"exported phrase return types must be scalar types, got {format_type(fn.return_type)}",
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
            root=name if isinstance(type_name, BufferType | ViewType) else None,
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
    if isinstance(type_name, ViewType):
        _check_view_type(type_name, line)
        return
    if isinstance(type_name, RecordType):
        if type_name.name not in records:
            raise InscriptionError(f"unknown type {type_name.name}", line)
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
    if not is_numeric_type(resolved.element_type):
        raise InscriptionError(f"buffer element type must be an integer type, got {format_type(resolved.element_type)}", line)


def _check_view_type(view_type: ViewType, line: int) -> None:
    if view_type.element_type not in NUMERIC_TYPES:
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
    raise AssertionError(stmt)  # pragma: no cover


def _check_no_shadow(name: str, line: int, bindings: dict[str, Binding], *, kind: str) -> None:
    existing = bindings.get(name)
    if existing is None:
        return
    if existing.kind == "param":
        raise InscriptionError(f"{kind} binding '{name}' cannot shadow phrase hole", line)
    if existing.kind == "buffer":
        raise InscriptionError(f"{kind} binding '{name}' cannot shadow buffer binding", line)
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
        if isinstance(stmt.type_name, RecordType) and stmt.type_name.name not in records:
            raise InscriptionError(f"unknown type {stmt.type_name.name}", stmt.line)
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
    assert isinstance(buffer_type.element_type, str)
    actual = _infer_declared_type(stmt.fill, buffer_type.element_type, _env_types(bindings), functions, records, constants)
    if actual != buffer_type.element_type:
        raise InscriptionError(
            f"buffer {stmt.name} fill must have type {buffer_type.element_type}, got {format_type(actual)}", stmt.line
        )
    bindings[stmt.name] = Binding(buffer_type, "buffer", stmt.line, root=stmt.name)


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
    if not isinstance(source.type_name, BufferType | ViewType):
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
    assert isinstance(element_type, str)
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
    if not binding.writable:
        if isinstance(storage_type, ViewType):
            raise InscriptionError(f"cannot store through read-only view {stmt.name}", stmt.line)
        raise InscriptionError(f"cannot store to read-only buffer parameter {stmt.name}", stmt.line)
    _check_storage_index(stmt.name, storage_type, stmt.index, _env_types(bindings), functions, records, constants)
    assert isinstance(storage_type.element_type, str)
    actual = _infer_declared_type(stmt.value, storage_type.element_type, _env_types(bindings), functions, records, constants)
    if actual != storage_type.element_type:
        raise InscriptionError(
            f"store to {stmt.name} must have type {storage_type.element_type}, got {format_type(actual)}", stmt.line
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
            f"field {stmt.field} of {record_type.name} must have type {field_type}, got {format_type(actual)}", stmt.line
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
    if not isinstance(binding.type_name, BufferType | ViewType):
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
                raise InscriptionError(f"buffer {name} cannot be passed to multiple buffer parameters in one call", call.line)
            seen_roots[root] = name
            full_binding = bindings[name]
            if effectful and not full_binding.writable:
                noun = "view" if isinstance(actual_type, ViewType) else "buffer"
                raise InscriptionError(f"cannot pass read-only {noun} {name} to effectful phrase `{target.display_name}`", call.line)
            continue
        if isinstance(expected, RecordType):
            _require_record_argument(arg, expected, env, getattr(arg, "line", call.line), records)
            continue
        actual = _infer_call_scalar_argument_type(arg, expected, env, functions, records)
        if actual != expected:
            raise InscriptionError(
                f"argument {_argument_name(arg)} must have type {format_type(expected)}, got {format_type(actual)}",
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
            raise InscriptionError(
                f"argument {_argument_name(arg)} must have type {format_type(expected)}, got {format_type(actual)}",
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
) -> tuple[str, BufferType | ViewType]:
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
    expected: TypeName,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> ValueType:
    if isinstance(arg, Variable):
        actual = env.get(arg.name)
        if isinstance(actual, BufferType | ViewType | RecordType):
            return actual
    return infer_expr_type(arg, env, functions, records, expected=expected)


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
    if isinstance(type_name, BufferType):
        return resolve_buffer_type(type_name, line, records, constants, functions, env)
    if isinstance(type_name, ViewType):
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
    return BufferType(length, buffer_type.element_type)


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
    if not isinstance(type_name, str):
        raise CompileTimeEvaluationError("record value is not compile-time evaluable", getattr(expr, "line", None))

    if isinstance(expr, Integer):
        if is_float_type(type_name) and expr.is_word_zero:
            return ConstValue(type_name, normalize_float(0.0, type_name))
        assert is_integer_type(type_name)
        return ConstValue(type_name, normalize_integer(expr.value, type_name))
    if isinstance(expr, Float):
        assert is_float_type(type_name)
        return ConstValue(type_name, normalize_float(parse_float_literal(expr.text, expr.line), type_name))
    if isinstance(expr, Boolean):
        return ConstValue("i1", expr.value)
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
        if not isinstance(binding_type, BufferType | ViewType):
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
        source = evaluate_const_expr(expr.expr, env, functions, records, constants)
        return ConstValue(expr.target_type, cast_const_value(source.value, source.type_name, expr.target_type))
    if isinstance(expr, Unary):
        operand_expected = "i1" if expr.op == "not" else type_name
        operand = evaluate_const_expr(expr.expr, env, functions, records, constants, expected=operand_expected)
        if expr.op == "not":
            return ConstValue("i1", not bool(operand.value))
        if expr.op == "bitwise not":
            return ConstValue(type_name, normalize_integer(~to_bits(int(operand.value), type_name), type_name))
    if isinstance(expr, Binary):
        if expr.op in {"and", "or"}:
            left = evaluate_const_expr(expr.left, env, functions, records, constants, expected="i1")
            right = evaluate_const_expr(expr.right, env, functions, records, constants, expected="i1")
            return ConstValue("i1", bool(left.value) and bool(right.value) if expr.op == "and" else bool(left.value) or bool(right.value))
        left = evaluate_const_expr(expr.left, env, functions, records, constants, expected=type_name)
        right = evaluate_const_expr(expr.right, env, functions, records, constants, expected=type_name)
        return ConstValue(type_name, evaluate_numeric_binary(expr.op, left.value, right.value, type_name, expr.line))
    if isinstance(expr, Comparison):
        operand_type = infer_comparison_operand_type(expr, env, functions, records)
        left = evaluate_const_expr(expr.left, env, functions, records, constants, expected=operand_type)
        right = evaluate_const_expr(expr.right, env, functions, records, constants, expected=operand_type)
        return ConstValue("i1", evaluate_comparison(expr.pred, left.value, right.value, operand_type))
    raise CompileTimeEvaluationError("expression is not compile-time evaluable", getattr(expr, "line", None))


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


def evaluate_comparison(pred: str, left: int | bool | float, right: int | bool | float, type_name: TypeName) -> bool:
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
                assert isinstance(expected, str)
                return expected
            if not is_integer_type(expected):
                raise InscriptionError(f"integer literal cannot have type {format_type(expected)}", expr.line)
            assert isinstance(expected, str)
            _check_integer_literal_range(expr.value, expected, expr.line)
            return expected
        _check_integer_literal_range(expr.value, "i32", expr.line)
        return "i32"
    if isinstance(expr, Float):
        if expected is not None:
            if not is_float_type(expected):
                raise InscriptionError(f"floating literal cannot have type {format_type(expected)}", expr.line)
            assert isinstance(expected, str)
            normalize_float(parse_float_literal(expr.text, expr.line), expected)
            return expected
        normalize_float(parse_float_literal(expr.text, expr.line), "f64")
        return "f64"
    if isinstance(expr, Boolean):
        if expected is not None:
            require_type("i1", expected, expr.line)
        return "i1"
    if isinstance(expr, Variable):
        actual = constants[expr.name].type_name if expr.name in constants and expr.name not in env else _lookup_binding_type(expr.name, expr.line, env)
        if isinstance(actual, BufferType):
            raise InscriptionError(f"buffer {expr.name} cannot be used as a scalar value; use `{expr.name} at index`", expr.line)
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
            assert isinstance(expected, str)
            require_type(actual, expected, expr.line)
        return actual
    if isinstance(expr, BufferLoad):
        buffer_type = _require_indexable_type(expr.name, expr.line, env)
        _check_storage_index(expr.name, buffer_type, expr.index, env, functions, records, constants)
        if expected is not None:
            assert isinstance(expected, str)
            require_type(buffer_type.element_type, expected, expr.line)
        return buffer_type.element_type
    if isinstance(expr, LengthOf):
        binding_type = env.get(expr.name)
        if binding_type is None:
            raise InscriptionError(f"unknown binding {expr.name}", expr.line)
        if not isinstance(binding_type, BufferType | ViewType):
            raise InscriptionError(f"length of {expr.name} requires a buffer, got {format_type(binding_type)}", expr.line)
        if isinstance(binding_type, BufferType) and not isinstance(binding_type.length, int):
            raise InscriptionError("buffer length must be compile-time evaluable", expr.line)
        if binding_type.length is not None and binding_type.length > INTEGER_RANGES["i32"][1]:
            raise InscriptionError(f"buffer length {binding_type.length} does not fit in i32", expr.line)
        if expected is not None:
            assert isinstance(expected, str)
            require_type("i32", expected, expr.line)
        return "i32"
    if isinstance(expr, SizeOfType):
        _require_layout_record_decl(expr.type_name, expr.line, records, f"size of {expr.type_name}")
        if expected is not None:
            assert isinstance(expected, str)
            require_type("i32", expected, expr.line)
        return "i32"
    if isinstance(expr, AlignmentOfType):
        _require_layout_record_decl(expr.type_name, expr.line, records, f"alignment of {expr.type_name}")
        if expected is not None:
            assert isinstance(expected, str)
            require_type("i32", expected, expr.line)
        return "i32"
    if isinstance(expr, OffsetOfField):
        record = _require_layout_record_decl(expr.type_name, expr.line, records, f"offset of {expr.field} in {expr.type_name}")
        if expr.field not in layout_info(record).field_offsets:
            raise InscriptionError(f"layout record {expr.type_name} has no field {expr.field}", expr.line)
        if expected is not None:
            assert isinstance(expected, str)
            require_type("i32", expected, expr.line)
        return "i32"
    if isinstance(expr, FieldAccess):
        qualified_constant = f"{expr.name}.{expr.field}"
        if expr.name not in env and qualified_constant in constants:
            actual = constants[qualified_constant].type_name
            if expected is not None:
                assert isinstance(expected, str)
                require_type(actual, expected, expr.line)
            return actual
        record_type = _require_record_type(expr.name, expr.line, env)
        field_type = _require_record_field(record_type, expr.field, expr.line, records)
        if expected is not None:
            assert isinstance(expected, str)
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
            assert isinstance(expected, str)
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
    raise AssertionError(expr)  # pragma: no cover


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
            assert isinstance(expected, str)
            require_type("i1", expected, expr.line)
        return "i1"
    if expr.op == "bitwise not":
        target = expected if is_integer_type(expected) else None
        actual = infer_integer_operand_type(expr.expr, env, functions, records, expected=target)
        if not is_integer_type(actual):
            raise InscriptionError(f"bitwise not requires integer operand, got {format_type(actual)}", expr.line)
        if expected is not None:
            assert isinstance(expected, str)
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
) -> TypeName:
    source_type = infer_expr_type(expr.expr, env, functions, records)
    target_type = expr.target_type
    if (
        (source_type == "i1" and is_float_type(target_type))
        or (is_float_type(source_type) and target_type == "i1")
        or (not isinstance(source_type, str))
        or (not is_integer_type(source_type) and not is_float_type(source_type))
        or (not is_integer_type(target_type) and not is_float_type(target_type))
    ):
        raise InscriptionError(f"cannot cast {source_type} to {target_type}", expr.line)
    if expected is not None:
        assert isinstance(expected, str)
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
            assert isinstance(expected, str)
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
) -> TypeName:
    return infer_comparison_pair_type(condition.left, condition.right, env, functions, records, condition.line)


def infer_comparison_pair_type(
    left: Expr,
    right: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    line: int,
) -> TypeName:
    if _is_numeric_literal(left) and not _is_numeric_literal(right):
        right_type = infer_expr_type(right, env, functions, records)
        left_type = infer_numeric_operand_type(left, env, functions, records, expected=right_type if is_numeric_type(right_type) else None)  # type: ignore[arg-type]
    elif _is_numeric_literal(right) and not _is_numeric_literal(left):
        left_type = infer_expr_type(left, env, functions, records)
        right_type = infer_numeric_operand_type(right, env, functions, records, expected=left_type if is_numeric_type(left_type) else None)  # type: ignore[arg-type]
    else:
        left_type = infer_expr_type(left, env, functions, records)
        right_type = infer_numeric_operand_type(right, env, functions, records, expected=left_type if is_numeric_type(left_type) else None)  # type: ignore[arg-type]

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
    assert isinstance(left_type, str)
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
    if not isinstance(binding.type_name, BufferType | ViewType):
        raise InscriptionError(f"{name} is not a buffer", line)
    return binding


def _require_buffer_type(name: str, line: int, env: dict[str, ValueType]) -> BufferType:
    binding_type = env.get(name)
    if binding_type is None:
        raise InscriptionError(f"unknown binding {name}", line)
    if not isinstance(binding_type, BufferType):
        raise InscriptionError(f"{name} is not a buffer", line)
    return binding_type


def _require_indexable_type(name: str, line: int, env: dict[str, ValueType]) -> BufferType | ViewType:
    binding_type = env.get(name)
    if binding_type is None:
        raise InscriptionError(f"unknown binding {name}", line)
    if not isinstance(binding_type, BufferType | ViewType):
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


def _require_record_field(record_type: RecordType, field: str, line: int, records: dict[str, RecordDecl]) -> TypeName:
    record = _record_decl(record_type, line, records)
    for field_decl in record.fields:
        if field_decl.name == field:
            assert isinstance(field_decl.type_name, str)
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
        assert isinstance(field_decl.type_name, str)
        actual = _infer_declared_type(initializer.expr, field_decl.type_name, env, functions, records)
        if actual != field_decl.type_name:
            raise InscriptionError(
                f"field {initializer.name} of {record.name} must have type {field_decl.type_name}, got {format_type(actual)}",
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
        noun = "u8 buffer or view" if isinstance(buffer_type, ViewType) else "u8 buffer"
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


def _check_storage_index(
    name: str,
    storage_type: BufferType | ViewType,
    index: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    constants: dict[str, ConstValue] | None = None,
) -> None:
    if isinstance(storage_type, BufferType):
        _check_buffer_index(name, storage_type, index, env, functions, records, constants)
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


def _static_storage_length(type_name: BufferType | ViewType) -> int | None:
    return type_name.length if isinstance(type_name.length, int) else None


def _check_layout_index(
    index_label: str,
    action: str,
    type_name: str,
    buffer_name: str,
    record_size: int,
    buffer_type: BufferType,
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
