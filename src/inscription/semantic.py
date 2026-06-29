from __future__ import annotations

from .ast import Binary, Call, Comparison, Expr, Function, Integer, Program, ReturnStmt, SetStmt, TypeName, Variable, WhenExpr
from .diagnostics import InscriptionError

NUMERIC_TYPES: set[TypeName] = {"i32", "i64"}


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
    env: dict[str, TypeName] = {param.name: param.type_name for param in fn.params}
    returned = False
    for index, stmt in enumerate(fn.body):
        if returned:
            raise InscriptionError("unreachable statement after value expression", getattr(stmt, "line", None))
        is_last = index == len(fn.body) - 1
        if isinstance(stmt, SetStmt):
            env[stmt.name] = infer_expr_type(stmt.expr, env, functions)
        elif isinstance(stmt, ReturnStmt):
            if not is_last:
                raise InscriptionError("value expression must be the final phrase body form", stmt.line)
            actual = infer_expr_type(stmt.expr, env, functions, expected=fn.return_type)
            require_type(actual, fn.return_type, stmt.line)
            returned = True
        else:  # pragma: no cover
            raise AssertionError(stmt)
    if not returned:
        raise InscriptionError(f"phrase '{fn.name}' must evaluate to a value", fn.line)


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
    if isinstance(expr, Variable):
        try:
            actual = env[expr.name]
        except KeyError as exc:
            raise InscriptionError(f"variable '{expr.name}' used before initialization", expr.line) from exc
        if expected is not None:
            require_type(actual, expected, expr.line)
        return actual
    if isinstance(expr, Binary):
        target = expected if expected in NUMERIC_TYPES else None
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
            infer_comparison_operand_type(case.condition, env, functions)
        otherwise_type = infer_expr_type(expr.otherwise, env, functions, expected=expected)
        require_type(otherwise_type, expected, expr.line)
        return expected
    raise AssertionError(expr)  # pragma: no cover


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


def infer_comparison_operand_type(
    condition: Comparison, env: dict[str, TypeName], functions: dict[str, Function]
) -> TypeName:
    return infer_numeric_pair_type(condition.left, condition.right, env, functions, condition.line)


def require_numeric(type_name: TypeName, line: int) -> None:
    if type_name not in NUMERIC_TYPES:
        raise InscriptionError(f"expected numeric value, got {type_name}", line)


def require_type(actual: TypeName, expected: TypeName, line: int) -> None:
    if actual != expected:
        raise InscriptionError(f"expected {expected}, got {actual}", line)
