from __future__ import annotations

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
    Comparison,
    Expr,
    FieldAccess,
    FieldAssignStmt,
    ForEachStmt,
    ForStmt,
    Function,
    IfStmt,
    Integer,
    LengthOf,
    Program,
    RecordConstructor,
    RecordDecl,
    RecordType,
    ReturnStmt,
    SetStmt,
    TypeName,
    Unary,
    ValueType,
    Variable,
    WhenExpr,
    WhileStmt,
)
from .diagnostics import InscriptionError

BOOLEAN_TYPE: TypeName = "i1"
SIGNED_INTEGER_TYPES: set[TypeName] = {"i8", "i16", "i32", "i64"}
UNSIGNED_INTEGER_TYPES: set[TypeName] = {"u8", "u16", "u32", "u64"}
INTEGER_TYPES: set[TypeName] = SIGNED_INTEGER_TYPES | UNSIGNED_INTEGER_TYPES
SCALAR_TYPES: set[TypeName] = {BOOLEAN_TYPE} | INTEGER_TYPES
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
BindingKind = Literal["param", "let", "buffer", "index"]


@dataclass(frozen=True)
class Binding:
    type_name: ValueType
    kind: BindingKind
    line: int
    writable: bool = True


def analyze(program: Program) -> None:
    records = record_table(program)
    functions = function_table(program)
    main = functions.get("main")
    if main is not None and main.params:
        raise InscriptionError("main must take no parameters", main.line)
    for fn in program.functions:
        _check_function(fn, functions, records)


def record_table(program: Program) -> dict[str, RecordDecl]:
    records: dict[str, RecordDecl] = {}
    for record in program.records:
        if record.name in SCALAR_TYPES:
            raise InscriptionError(f"record name {record.name} collides with scalar type", record.line)
        if record.name in records:
            raise InscriptionError(f"record {record.name} is already defined", record.line)
        if not record.fields:
            raise InscriptionError(f"record {record.name} must declare at least one field", record.line)
        seen_fields: set[str] = set()
        for field in record.fields:
            if field.name in seen_fields:
                raise InscriptionError(f"record {record.name} has duplicate field {field.name}", field.line)
            seen_fields.add(field.name)
            if not isinstance(field.type_name, str) or field.type_name not in SCALAR_TYPES:
                raise InscriptionError(
                    f"record fields must be scalar types, got {format_type(field.type_name)}", field.line
                )
        records[record.name] = record
    return records


def function_table(program: Program) -> dict[str, Function]:
    functions: dict[str, Function] = {}
    for fn in program.functions:
        if fn.name in functions:
            raise InscriptionError(f"duplicate phrase '{fn.name}'", fn.line)
        functions[fn.name] = fn
        seen_params: set[str] = set()
        for param in fn.params:
            if param.name in seen_params:
                raise InscriptionError(f"duplicate parameter '{param.name}'", fn.line)
            seen_params.add(param.name)
    return functions


def mlir_type(type_name: TypeName) -> str:
    if type_name.startswith("u"):
        return f"i{TYPE_WIDTHS[type_name]}"
    return type_name


def memref_type(buffer_type: BufferType) -> str:
    return f"memref<{buffer_type.length}x{mlir_type(buffer_type.element_type)}>"


def format_type(type_name: ValueType) -> str:
    if isinstance(type_name, BufferType):
        return f"buffer of {type_name.length} {format_type(type_name.element_type)}"
    if isinstance(type_name, RecordType):
        return type_name.name
    return type_name


def is_integer_type(type_name: ValueType | None) -> bool:
    return type_name in INTEGER_TYPES


def is_signed_type(type_name: TypeName) -> bool:
    return type_name in SIGNED_INTEGER_TYPES


def type_width(type_name: TypeName) -> int:
    return TYPE_WIDTHS[type_name]


def all_ones_constant_value(_type_name: TypeName) -> int:
    return -1


def _check_function(fn: Function, functions: dict[str, Function], records: dict[str, RecordDecl]) -> None:
    for param in fn.params:
        _check_parameter_type(param.type_name, fn.line, records)
    if fn.return_type is None:
        _check_does_function(fn, functions, records)
        return
    if isinstance(fn.return_type, RecordType):
        raise InscriptionError("record return types are not supported in v0.7", fn.line)
    if not fn.body:
        raise InscriptionError(f"phrase '{fn.name}' must evaluate to a value", fn.line)
    bindings: dict[str, Binding] = {
        param.name: Binding(param.type_name, "param", fn.line, writable=not isinstance(param.type_name, BufferType))
        for param in fn.params
    }
    returned = False
    for index, stmt in enumerate(fn.body):
        if returned:
            raise InscriptionError("unreachable statement after value expression", getattr(stmt, "line", None))
        is_last = index == len(fn.body) - 1
        if isinstance(stmt, ReturnStmt):
            if not is_last:
                raise InscriptionError("value expression must be the final phrase body form", stmt.line)
            actual = infer_expr_type(stmt.expr, _env_types(bindings), functions, records, expected=fn.return_type)
            require_type(actual, fn.return_type, stmt.line)
            returned = True
        else:
            _check_body_stmt(stmt, bindings, functions, records)
    if not returned:
        raise InscriptionError(f"phrase '{fn.name}' must evaluate to a value", fn.line)


def _check_does_function(fn: Function, functions: dict[str, Function], records: dict[str, RecordDecl]) -> None:
    if not fn.body:
        raise InscriptionError("does phrase body must contain at least one step", fn.line)
    bindings: dict[str, Binding] = {
        param.name: Binding(param.type_name, "param", fn.line, writable=True) for param in fn.params
    }
    for stmt in fn.body:
        if isinstance(stmt, ReturnStmt):
            raise InscriptionError("does phrase body cannot end with a value expression", stmt.line)
        _check_body_stmt(stmt, bindings, functions, records)


def _check_parameter_type(type_name: ValueType, line: int, records: dict[str, RecordDecl]) -> None:
    if isinstance(type_name, BufferType):
        _check_buffer_type(type_name, line)
        return
    if isinstance(type_name, RecordType):
        if type_name.name not in records:
            raise InscriptionError(f"unknown type {type_name.name}", line)
        return
    if type_name not in SCALAR_TYPES:
        raise InscriptionError("supported scalar types are i1, i8, i16, i32, i64, u8, u16, u32, and u64", line)


def _check_buffer_type(buffer_type: BufferType, line: int) -> None:
    if buffer_type.length < 1:
        raise InscriptionError("buffer length must be at least 1", line)
    if not is_integer_type(buffer_type.element_type):
        raise InscriptionError(f"buffer element type must be an integer type, got {format_type(buffer_type.element_type)}", line)


def _check_body_stmt(
    stmt: BodyStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> None:
    if isinstance(stmt, SetStmt):
        _declare_let(stmt, bindings, functions, records)
        return
    if isinstance(stmt, BufferBinding):
        _declare_buffer(stmt, bindings, functions, records)
        return
    if isinstance(stmt, AssignStmt):
        _check_assignment(stmt, bindings, functions, records)
        return
    if isinstance(stmt, BufferStoreStmt):
        _check_buffer_store(stmt, bindings, functions, records)
        return
    if isinstance(stmt, FieldAssignStmt):
        _check_field_assignment(stmt, bindings, functions, records)
        return
    if isinstance(stmt, CallStmt):
        _check_call_stmt(stmt, bindings, functions, records)
        return
    if isinstance(stmt, WhileStmt):
        _check_while(stmt, bindings, functions, records)
        return
    if isinstance(stmt, ForStmt):
        _check_for(stmt, bindings, functions, records)
        return
    if isinstance(stmt, ForEachStmt):
        _check_for_each(stmt, bindings, functions, records)
        return
    if isinstance(stmt, IfStmt):
        _check_if(stmt, bindings, functions, records)
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
    raise InscriptionError(f"duplicate {kind} binding '{name}'", line)


def _declare_let(
    stmt: SetStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> None:
    _check_no_shadow(stmt.name, stmt.line, bindings, kind="let")
    if stmt.type_name is not None:
        if isinstance(stmt.type_name, RecordType) and stmt.type_name.name not in records:
            raise InscriptionError(f"unknown type {stmt.type_name.name}", stmt.line)
        actual = _infer_declared_type(stmt.expr, stmt.type_name, _env_types(bindings), functions, records)
        if actual != stmt.type_name:
            raise InscriptionError(
                f"let {stmt.name} must have type {format_type(stmt.type_name)}, got {format_type(actual)}", stmt.line
            )
        bindings[stmt.name] = Binding(stmt.type_name, "let", stmt.line)
        return
    type_name = infer_expr_type(stmt.expr, _env_types(bindings), functions, records)
    bindings[stmt.name] = Binding(type_name, "let", stmt.line)


def _declare_buffer(
    stmt: BufferBinding,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> None:
    _check_no_shadow(stmt.name, stmt.line, bindings, kind="buffer")
    buffer_type = stmt.buffer_type
    _check_buffer_type(buffer_type, stmt.line)
    assert isinstance(buffer_type.element_type, str)
    actual = _infer_declared_type(stmt.fill, buffer_type.element_type, _env_types(bindings), functions, records)
    if actual != buffer_type.element_type:
        raise InscriptionError(
            f"buffer {stmt.name} fill must have type {buffer_type.element_type}, got {format_type(actual)}", stmt.line
        )
    bindings[stmt.name] = Binding(buffer_type, "buffer", stmt.line)


def _check_assignment(
    stmt: AssignStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> None:
    binding = bindings.get(stmt.name)
    if binding is None:
        raise InscriptionError(f"unknown binding {stmt.name}", stmt.line)
    if isinstance(binding.type_name, BufferType):
        raise InscriptionError(
            f"cannot rebind buffer {stmt.name}; use `{stmt.name} at index becomes value`", stmt.line
        )
    if not binding.writable:
        if binding.kind == "index":
            raise InscriptionError(f"cannot rebind for-loop index {stmt.name}", stmt.line)
        raise InscriptionError(f"cannot rebind {stmt.name}", stmt.line)
    actual = _infer_declared_type(stmt.expr, binding.type_name, _env_types(bindings), functions, records)
    if actual != binding.type_name:
        raise InscriptionError(
            f"assignment to {stmt.name} must have type {format_type(binding.type_name)}, got {format_type(actual)}", stmt.line
        )


def _check_buffer_store(
    stmt: BufferStoreStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> None:
    binding = _require_buffer_binding(stmt.name, stmt.line, bindings)
    buffer_type = binding.type_name
    if not binding.writable:
        raise InscriptionError(f"cannot store to read-only buffer parameter {stmt.name}", stmt.line)
    _check_buffer_index(stmt.name, buffer_type, stmt.index, _env_types(bindings), functions, records)
    assert isinstance(buffer_type.element_type, str)
    actual = _infer_declared_type(stmt.value, buffer_type.element_type, _env_types(bindings), functions, records)
    if actual != buffer_type.element_type:
        raise InscriptionError(
            f"store to {stmt.name} must have type {buffer_type.element_type}, got {format_type(actual)}", stmt.line
        )


def _check_field_assignment(
    stmt: FieldAssignStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> None:
    record_type = _require_record_type(stmt.name, stmt.line, _env_types(bindings))
    field_type = _require_record_field(record_type, stmt.field, stmt.line, records)
    actual = _infer_declared_type(stmt.expr, field_type, _env_types(bindings), functions, records)
    if actual != field_type:
        raise InscriptionError(
            f"field {stmt.field} of {record_type.name} must have type {field_type}, got {format_type(actual)}", stmt.line
        )


def _check_call_stmt(
    stmt: CallStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> None:
    target = _lookup_phrase(stmt.call.name, stmt.line, functions)
    if target.return_type is not None:
        raise InscriptionError(
            f"phrase `{target.display_name}` returns {target.return_type} and cannot be used as a step", stmt.line
        )
    _check_call_arguments(stmt.call, target, bindings, functions, records, effectful=True)


def _check_while(
    stmt: WhileStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> None:
    condition_type = infer_expr_type(stmt.condition, _env_types(bindings), functions, records)
    if condition_type != "i1":
        raise InscriptionError(f"while condition must be i1, got {format_type(condition_type)}", stmt.line)
    if not stmt.body:
        raise InscriptionError("while loop requires at least one body step", stmt.line)
    scoped = dict(bindings)
    for body_stmt in stmt.body:
        _check_body_stmt(body_stmt, scoped, functions, records)


def _check_for(
    stmt: ForStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
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
        _check_body_stmt(body_stmt, scoped, functions, records)


def _check_for_each(
    stmt: ForEachStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> None:
    binding = bindings.get(stmt.buffer_name)
    if binding is None:
        raise InscriptionError(f"unknown binding {stmt.buffer_name}", stmt.line)
    if not isinstance(binding.type_name, BufferType):
        raise InscriptionError(f"for each index requires a buffer, got {format_type(binding.type_name)}", stmt.line)
    if not stmt.body:
        raise InscriptionError("for loop body must contain at least one step", stmt.line)
    _check_index_shadow(stmt.name, stmt.line, bindings)
    scoped = dict(bindings)
    scoped[stmt.name] = Binding("i32", "index", stmt.line, writable=False)
    for body_stmt in stmt.body:
        _check_body_stmt(body_stmt, scoped, functions, records)


def _check_index_shadow(name: str, line: int, bindings: dict[str, Binding]) -> None:
    if name in bindings:
        raise InscriptionError(f"binding {name} already exists", line)


def _check_if(
    stmt: IfStmt,
    bindings: dict[str, Binding],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
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
        _check_body_stmt(body_stmt, then_scope, functions, records)

    else_scope = dict(bindings)
    for body_stmt in stmt.else_body:
        _check_body_stmt(body_stmt, else_scope, functions, records)


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
    *,
    effectful: bool,
) -> None:
    _check_call_arity(call, target)
    seen_buffers: set[str] = set()
    env = _env_types(bindings)
    for arg, param in zip(call.args, target.params, strict=True):
        expected = param.type_name
        if isinstance(expected, BufferType):
            name, binding = _require_buffer_argument(arg, expected, env, getattr(arg, "line", call.line), records)
            if name in seen_buffers:
                raise InscriptionError(f"buffer {name} cannot be passed to multiple buffer parameters in one call", call.line)
            seen_buffers.add(name)
            full_binding = bindings[name]
            if effectful and not full_binding.writable:
                raise InscriptionError(f"cannot pass read-only buffer {name} to effectful phrase `{target.display_name}`", call.line)
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
) -> None:
    _check_call_arity(call, target)
    seen_buffers: set[str] = set()
    for arg, param in zip(call.args, target.params, strict=True):
        expected = param.type_name
        if isinstance(expected, BufferType):
            name, _binding_type = _require_buffer_argument(arg, expected, env, getattr(arg, "line", call.line), records)
            if name in seen_buffers:
                raise InscriptionError(f"buffer {name} cannot be passed to multiple buffer parameters in one call", call.line)
            seen_buffers.add(name)
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
        if isinstance(actual, BufferType | RecordType):
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
) -> ValueType:
    try:
        return infer_expr_type(expr, env, functions, records, expected=expected)
    except InscriptionError as expected_error:
        if _should_preserve_expected_error(expected_error):
            raise
        try:
            return infer_expr_type(expr, env, functions, records)
        except InscriptionError:
            raise expected_error


def _should_preserve_expected_error(error: InscriptionError) -> bool:
    message = str(error)
    return ("integer literal" in message and "out of range" in message) or message.startswith("cannot cast")


def _env_types(bindings: dict[str, Binding]) -> dict[str, ValueType]:
    return {name: binding.type_name for name, binding in bindings.items()}


def infer_expr_type(
    expr: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
    *,
    expected: ValueType | None = None,
) -> ValueType:
    if isinstance(expr, Integer):
        if expected is not None:
            if not is_integer_type(expected):
                raise InscriptionError(f"integer literal cannot have type {format_type(expected)}", expr.line)
            assert isinstance(expected, str)
            _check_integer_literal_range(expr.value, expected, expr.line)
            return expected
        _check_integer_literal_range(expr.value, "i32", expr.line)
        return "i32"
    if isinstance(expr, Boolean):
        if expected is not None:
            require_type("i1", expected, expr.line)
        return "i1"
    if isinstance(expr, Variable):
        actual = _lookup_binding_type(expr.name, expr.line, env)
        if isinstance(actual, BufferType):
            raise InscriptionError(f"buffer {expr.name} cannot be used as a scalar value; use `{expr.name} at index`", expr.line)
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
        buffer_type = _require_buffer_type(expr.name, expr.line, env)
        _check_buffer_index(expr.name, buffer_type, expr.index, env, functions, records)
        if expected is not None:
            assert isinstance(expected, str)
            require_type(buffer_type.element_type, expected, expr.line)
        return buffer_type.element_type
    if isinstance(expr, LengthOf):
        binding_type = env.get(expr.name)
        if binding_type is None:
            raise InscriptionError(f"unknown binding {expr.name}", expr.line)
        if not isinstance(binding_type, BufferType):
            raise InscriptionError(f"length of {expr.name} requires a buffer, got {format_type(binding_type)}", expr.line)
        if binding_type.length > INTEGER_RANGES["i32"][1]:
            raise InscriptionError(f"buffer length {binding_type.length} does not fit in i32", expr.line)
        if expected is not None:
            assert isinstance(expected, str)
            require_type("i32", expected, expr.line)
        return "i32"
    if isinstance(expr, FieldAccess):
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
        if isinstance(target.return_type, RecordType):
            raise InscriptionError("record return types are not supported in v0.7", expr.line)
        _check_call_argument_types(expr, target, env, functions, records)
        if expected is not None:
            assert isinstance(expected, str)
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
        if not isinstance(expected, str):
            raise InscriptionError(f"record values cannot be used in value blocks, got {format_type(expected)}", expr.line)
        for case in expr.cases:
            actual = infer_expr_type(case.expr, env, functions, records, expected=expected)
            require_type(actual, expected, case.line)
            condition_type = infer_i1_operand_type(case.condition, env, functions, records)
            if condition_type != "i1":
                raise InscriptionError(f"value block condition must be i1, got {condition_type}", case.line)
        otherwise_type = infer_expr_type(expr.otherwise, env, functions, records, expected=expected)
        require_type(otherwise_type, expected, expr.line)
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
    if not is_integer_type(source_type) or not is_integer_type(target_type):
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

    if expr.op in {"plus", "minus", "times", "divided by", "remainder"}:
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
    if isinstance(left, Integer) and not isinstance(right, Integer):
        right_type = infer_expr_type(right, env, functions, records)
        left_type = infer_integer_operand_type(left, env, functions, records, expected=right_type if is_integer_type(right_type) else None)
    elif isinstance(right, Integer) and not isinstance(left, Integer):
        left_type = infer_expr_type(left, env, functions, records)
        right_type = infer_integer_operand_type(right, env, functions, records, expected=left_type if is_integer_type(left_type) else None)
    else:
        left_type = infer_expr_type(left, env, functions, records)
        right_type = infer_integer_operand_type(right, env, functions, records, expected=left_type if is_integer_type(left_type) else None)

    if not is_integer_type(left_type) or not is_integer_type(right_type):
        raise InscriptionError(
            f"comparison requires integer operands, got {format_type(left_type)} and {format_type(right_type)}", line
        )
    if left_type != right_type:
        raise InscriptionError(
            f"comparison requires matching integer types, got {format_type(left_type)} and {format_type(right_type)}", line
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


def _require_buffer_type(name: str, line: int, env: dict[str, ValueType]) -> BufferType:
    binding_type = env.get(name)
    if binding_type is None:
        raise InscriptionError(f"unknown binding {name}", line)
    if not isinstance(binding_type, BufferType):
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


def _check_buffer_index(
    name: str,
    buffer_type: BufferType,
    index: Expr,
    env: dict[str, ValueType],
    functions: dict[str, Function],
    records: dict[str, RecordDecl],
) -> None:
    if isinstance(index, Integer) and not 0 <= index.value < buffer_type.length:
        raise InscriptionError(
            f"buffer index {index.value} is out of bounds for buffer {name} of length {buffer_type.length}", index.line
        )
    index_type = infer_expr_type(index, env, functions, records)
    if not is_integer_type(index_type):
        raise InscriptionError(
            f"buffer index must be an integer type, got {format_type(index_type)}", getattr(index, "line", None)
        )


def _check_integer_literal_range(value: int, type_name: TypeName, line: int) -> None:
    if type_name not in INTEGER_RANGES:
        raise InscriptionError(f"integer literal cannot have type {type_name}", line)
    low, high = INTEGER_RANGES[type_name]
    if not low <= value <= high:
        raise InscriptionError(f"integer literal {value} is out of range for {type_name}", line)


def require_type(actual: ValueType, expected: ValueType, line: int) -> None:
    if actual != expected:
        raise InscriptionError(f"expected {format_type(expected)}, got {format_type(actual)}", line)
