from __future__ import annotations

from .ast import Binary, Call, Comparison, Expr, Function, Integer, Program, ReturnStmt, SetStmt, Stmt, Variable, WhenExpr
from .diagnostics import InscriptionError


def analyze(program: Program) -> None:
    functions: dict[str, Function] = {}
    for fn in program.functions:
        if fn.name in functions:
            raise InscriptionError(f"duplicate phrase '{fn.name}'", fn.line)
        functions[fn.name] = fn
        seen_params: set[str] = set()
        for param in fn.params:
            if param in seen_params:
                raise InscriptionError(f"duplicate parameter '{param}'", fn.line)
            seen_params.add(param)
    main = functions.get("main")
    if main is None:
        raise InscriptionError("program must define main")
    if main.params:
        raise InscriptionError("main must take no parameters", main.line)
    for fn in program.functions:
        _check_function(fn, functions)


def _check_function(fn: Function, functions: dict[str, Function]) -> None:
    if not fn.body:
        raise InscriptionError(f"phrase '{fn.name}' must evaluate to a value", fn.line)
    env = set(fn.params)
    returned = False
    for index, stmt in enumerate(fn.body):
        if returned:
            raise InscriptionError("unreachable statement after value expression", getattr(stmt, "line", None))
        is_last = index == len(fn.body) - 1
        if isinstance(stmt, SetStmt):
            _check_expr(stmt.expr, env, functions)
            env.add(stmt.name)
        elif isinstance(stmt, ReturnStmt):
            if not is_last:
                raise InscriptionError("value expression must be the final phrase body form", stmt.line)
            _check_expr(stmt.expr, env, functions)
            returned = True
        else:  # pragma: no cover
            raise AssertionError(stmt)
    if not returned:
        raise InscriptionError(f"phrase '{fn.name}' must evaluate to a value", fn.line)


def _check_expr(expr: Expr, env: set[str], functions: dict[str, Function]) -> None:
    if isinstance(expr, Integer):
        return
    if isinstance(expr, Variable):
        if expr.name not in env:
            raise InscriptionError(f"variable '{expr.name}' used before initialization", expr.line)
        return
    if isinstance(expr, Binary):
        _check_expr(expr.left, env, functions)
        _check_expr(expr.right, env, functions)
        return
    if isinstance(expr, Call):
        target = functions.get(expr.name)
        if target is None:
            raise InscriptionError(f"unknown phrase '{expr.name}'", expr.line)
        if len(expr.args) != len(target.params):
            raise InscriptionError(
                f"phrase '{expr.name}' expects {len(target.params)} argument(s), got {len(expr.args)}", expr.line
            )
        for arg in expr.args:
            _check_expr(arg, env, functions)
        return
    if isinstance(expr, WhenExpr):
        for case in expr.cases:
            _check_expr(case.expr, env, functions)
            _check_comparison(case.condition, env, functions)
        _check_expr(expr.otherwise, env, functions)
        return
    raise AssertionError(expr)  # pragma: no cover


def _check_comparison(condition: Comparison, env: set[str], functions: dict[str, Function]) -> None:
    _check_expr(condition.left, env, functions)
    _check_expr(condition.right, env, functions)
