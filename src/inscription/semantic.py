from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
    Program,
    ReturnStmt,
    SetStmt,
    TypeName,
    Unary,
    Variable,
    WhenExpr,
    WhileStmt,
)
from .diagnostics import InscriptionError

NUMERIC_TYPES: set[TypeName] = {"i32", "i64"}
BindingKind = Literal["param", "let"]


@dataclass(frozen=True)
class Binding:
    type_name: TypeName
    kind: BindingKind
    line: int


def analyze(program: Program) -> None:
    functions = function_table(program)
    main = functions.get("main")
    if main is not None and main.params:
        raise InscriptionError("main must take no parameters", main.line)
    for fn in program.functions:
        _check_function(fn, functions)


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


def _check_function(fn: Function, functions: dict[str, Function]) -> None:
    if not fn.body:
        raise InscriptionError(f"phrase '{fn.name}' must evaluate to a value", fn.line)
    bindings: dict[str, Binding] = {
        param.name: Binding(param.type_name, "param", fn.line) for param in fn.params
    }
    returned = False
    for index, stmt in enumerate(fn.body):
        if returned:
            raise InscriptionError("unreachable statement after value expression", getattr(stmt, "line", None))
        is_last = index == len(fn.body) - 1
        if isinstance(stmt, ReturnStmt):
            if not is_last:
                raise InscriptionError("value expression must be the final phrase body form", stmt.line)
            actual = infer_expr_type(stmt.expr, _env_types(bindings), functions, expected=fn.return_type)
            require_type(actual, fn.return_type, stmt.line)
            returned = True
        else:
            _check_body_stmt(stmt, bindings, functions)
    if not returned:
        raise InscriptionError(f"phrase '{fn.name}' must evaluate to a value", fn.line)


def _check_body_stmt(stmt: BodyStmt, bindings: dict[str, Binding], functions: dict[str, Function]) -> None:
    if isinstance(stmt, SetStmt):
        _declare_let(stmt, bindings, functions)
        return
    if isinstance(stmt, AssignStmt):
        _check_assignment(stmt, bindings, functions)
        return
    if isinstance(stmt, WhileStmt):
        _check_while(stmt, bindings, functions)
        return
    if isinstance(stmt, IfStmt):
        _check_if(stmt, bindings, functions)
        return
    raise AssertionError(stmt)  # pragma: no cover


def _declare_let(stmt: SetStmt, bindings: dict[str, Binding], functions: dict[str, Function]) -> None:
    existing = bindings.get(stmt.name)
    if existing is not None:
        if existing.kind == "param":
            raise InscriptionError(f"let binding '{stmt.name}' cannot shadow phrase hole", stmt.line)
        raise InscriptionError(f"duplicate let binding '{stmt.name}'", stmt.line)
    if stmt.type_name is not None:
        actual = _infer_declared_type(stmt.expr, stmt.type_name, _env_types(bindings), functions)
        if actual != stmt.type_name:
            raise InscriptionError(f"let {stmt.name} must have type {stmt.type_name}, got {actual}", stmt.line)
        bindings[stmt.name] = Binding(stmt.type_name, "let", stmt.line)
        return
    type_name = infer_expr_type(stmt.expr, _env_types(bindings), functions)
    bindings[stmt.name] = Binding(type_name, "let", stmt.line)


def _check_assignment(stmt: AssignStmt, bindings: dict[str, Binding], functions: dict[str, Function]) -> None:
    binding = bindings.get(stmt.name)
    if binding is None:
        raise InscriptionError(f"unknown binding {stmt.name}", stmt.line)
    actual = _infer_declared_type(stmt.expr, binding.type_name, _env_types(bindings), functions)
    if actual != binding.type_name:
        raise InscriptionError(
            f"assignment to {stmt.name} must have type {binding.type_name}, got {actual}", stmt.line
        )


def _check_while(stmt: WhileStmt, bindings: dict[str, Binding], functions: dict[str, Function]) -> None:
    condition_type = infer_expr_type(stmt.condition, _env_types(bindings), functions)
    if condition_type != "i1":
        raise InscriptionError(f"while condition must be i1, got {condition_type}", stmt.line)
    if not stmt.body:
        raise InscriptionError("while loop requires at least one body step", stmt.line)
    scoped = dict(bindings)
    for body_stmt in stmt.body:
        _check_body_stmt(body_stmt, scoped, functions)


def _check_if(stmt: IfStmt, bindings: dict[str, Binding], functions: dict[str, Function]) -> None:
    condition_type = infer_expr_type(stmt.condition, _env_types(bindings), functions)
    if condition_type != "i1":
        raise InscriptionError(f"if condition must be i1, got {condition_type}", stmt.line)
    if not stmt.then_body:
        raise InscriptionError("if branch must contain at least one step", stmt.line)
    if not stmt.else_body:
        raise InscriptionError("otherwise branch must contain at least one step", stmt.line)

    then_scope = dict(bindings)
    for body_stmt in stmt.then_body:
        _check_body_stmt(body_stmt, then_scope, functions)

    else_scope = dict(bindings)
    for body_stmt in stmt.else_body:
        _check_body_stmt(body_stmt, else_scope, functions)


def _infer_declared_type(
    expr: Expr,
    expected: TypeName,
    env: dict[str, TypeName],
    functions: dict[str, Function],
) -> TypeName:
    try:
        return infer_expr_type(expr, env, functions, expected=expected)
    except InscriptionError:
        try:
            return infer_expr_type(expr, env, functions)
        except InscriptionError:
            raise


def _env_types(bindings: dict[str, Binding]) -> dict[str, TypeName]:
    return {name: binding.type_name for name, binding in bindings.items()}


def infer_expr_type(
    expr: Expr,
    env: dict[str, TypeName],
    functions: dict[str, Function],
    *,
    expected: TypeName | None = None,
) -> TypeName:
    if isinstance(expr, Integer):
        if expected is not None:
            require_numeric(expected, expr.line)
            return expected
        return "i32"
    if isinstance(expr, Boolean):
        if expected is not None:
            require_type("i1", expected, expr.line)
        return "i1"
    if isinstance(expr, Variable):
        try:
            actual = env[expr.name]
        except KeyError as exc:
            raise InscriptionError(
                f"unknown binding {expr.name}; variable '{expr.name}' used before initialization", expr.line
            ) from exc
        if expected is not None:
            require_type(actual, expected, expr.line)
        return actual
    if isinstance(expr, Unary):
        if expr.op == "not":
            actual = infer_i1_operand_type(expr.expr, env, functions)
            if actual != "i1":
                raise InscriptionError("not requires i1 operand", expr.line)
            if expected is not None:
                require_type("i1", expected, expr.line)
            return "i1"
        raise AssertionError(expr)  # pragma: no cover
    if isinstance(expr, Binary):
        if expr.op in {"and", "or"}:
            left_type = infer_i1_operand_type(expr.left, env, functions)
            right_type = infer_i1_operand_type(expr.right, env, functions)
            if left_type != "i1" or right_type != "i1":
                raise InscriptionError(f"{expr.op} requires i1 operands", expr.line)
            if expected is not None:
                require_type("i1", expected, expr.line)
            return "i1"
        target = expected if expected in NUMERIC_TYPES else None
        if expr.op == "remainder":
            return infer_remainder_type(expr.left, expr.right, env, functions, expr.line, expected=target)
        return infer_numeric_pair_type(expr.left, expr.right, env, functions, expr.line, expected=target)
    if isinstance(expr, Call):
        target = functions.get(expr.name)
        if target is None:
            raise InscriptionError(f"unknown phrase '{expr.name}'", expr.line)
        if len(expr.args) != len(target.params):
            raise InscriptionError(
                f"phrase '{expr.name}' expects {len(target.params)} argument(s), got {len(expr.args)}", expr.line
            )
        for arg, param in zip(expr.args, target.params, strict=True):
            actual = infer_expr_type(arg, env, functions, expected=param.type_name)
            require_type(actual, param.type_name, getattr(arg, "line", expr.line))
        if expected is not None:
            require_type(target.return_type, expected, expr.line)
        return target.return_type
    if isinstance(expr, Comparison):
        infer_comparison_operand_type(expr, env, functions)
        if expected is not None:
            require_type("i1", expected, expr.line)
        return "i1"
    if isinstance(expr, WhenExpr):
        if expected is None:
            expected = infer_expr_type(expr.otherwise, env, functions)
        for case in expr.cases:
            actual = infer_expr_type(case.expr, env, functions, expected=expected)
            require_type(actual, expected, case.line)
            condition_type = infer_i1_operand_type(case.condition, env, functions)
            if condition_type != "i1":
                raise InscriptionError(f"value block condition must be i1, got {condition_type}", case.line)
        otherwise_type = infer_expr_type(expr.otherwise, env, functions, expected=expected)
        require_type(otherwise_type, expected, expr.line)
        return expected
    raise AssertionError(expr)  # pragma: no cover


def infer_i1_operand_type(expr: Expr, env: dict[str, TypeName], functions: dict[str, Function]) -> TypeName:
    try:
        return infer_expr_type(expr, env, functions, expected="i1")
    except InscriptionError:
        return infer_expr_type(expr, env, functions)


def infer_numeric_pair_type(
    left: Expr,
    right: Expr,
    env: dict[str, TypeName],
    functions: dict[str, Function],
    line: int,
    *,
    expected: TypeName | None = None,
) -> TypeName:
    if expected is not None:
        require_numeric(expected, line)
        left_type = infer_expr_type(left, env, functions, expected=expected)
        right_type = infer_expr_type(right, env, functions, expected=expected)
        require_type(left_type, expected, line)
        require_type(right_type, expected, line)
        return expected

    if isinstance(left, Integer) and not isinstance(right, Integer):
        right_type = infer_expr_type(right, env, functions)
        require_numeric(right_type, line)
        left_type = infer_expr_type(left, env, functions, expected=right_type)
        require_type(left_type, right_type, line)
        return right_type

    left_type = infer_expr_type(left, env, functions)
    require_numeric(left_type, line)
    right_type = infer_expr_type(right, env, functions, expected=left_type)
    require_type(right_type, left_type, line)
    return left_type


def infer_remainder_type(
    left: Expr,
    right: Expr,
    env: dict[str, TypeName],
    functions: dict[str, Function],
    line: int,
    *,
    expected: TypeName | None = None,
) -> TypeName:
    if expected is not None:
        require_remainder_numeric(expected, line)
        try:
            left_type = infer_expr_type(left, env, functions, expected=expected)
        except InscriptionError:
            left_type = infer_expr_type(left, env, functions)
        try:
            right_type = infer_expr_type(right, env, functions, expected=expected)
        except InscriptionError:
            right_type = infer_expr_type(right, env, functions)
        require_remainder_numeric(left_type, line)
        require_remainder_numeric(right_type, line)
        if left_type != expected or right_type != expected:
            raise InscriptionError(f"remainder operands must have same type, got {left_type} and {right_type}", line)
        return expected

    if isinstance(left, Integer) and not isinstance(right, Integer):
        right_type = infer_expr_type(right, env, functions)
        require_remainder_numeric(right_type, line)
        left_type = infer_expr_type(left, env, functions, expected=right_type)
        require_type(left_type, right_type, line)
        return right_type

    left_type = infer_expr_type(left, env, functions)
    require_remainder_numeric(left_type, line)
    try:
        right_type = infer_expr_type(right, env, functions, expected=left_type)
    except InscriptionError:
        right_type = infer_expr_type(right, env, functions)
    require_remainder_numeric(right_type, line)
    if right_type != left_type:
        raise InscriptionError(f"remainder operands must have same type, got {left_type} and {right_type}", line)
    return left_type


def infer_comparison_operand_type(
    condition: Comparison, env: dict[str, TypeName], functions: dict[str, Function]
) -> TypeName:
    return infer_numeric_pair_type(condition.left, condition.right, env, functions, condition.line)


def require_numeric(type_name: TypeName, line: int) -> None:
    if type_name not in NUMERIC_TYPES:
        raise InscriptionError(f"expected numeric value, got {type_name}", line)


def require_remainder_numeric(type_name: TypeName, line: int) -> None:
    if type_name not in NUMERIC_TYPES:
        raise InscriptionError("remainder requires numeric operands", line)


def require_type(actual: TypeName, expected: TypeName, line: int) -> None:
    if actual != expected:
        raise InscriptionError(f"expected {expected}, got {actual}", line)
