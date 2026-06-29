from __future__ import annotations

from .ast import Binary, Call, Comparison, Expr, Function, IfStmt, Integer, Program, ReturnStmt, SetStmt, Stmt, Variable, WhileStmt
from .diagnostics import InscriptionError


def analyze(program: Program) -> None:
    functions: dict[str, Function] = {}
    for fn in program.functions:
        if fn.name in functions:
            raise InscriptionError(f"duplicate function '{fn.name}'", fn.line)
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
        raise InscriptionError(f"function '{fn.name}' must end with Return", fn.line)
    env = set(fn.params)
    _, returned = _check_block(fn.body, env, functions, allow_tail_return=True)
    if not returned:
        raise InscriptionError(f"function '{fn.name}' must end with Return", fn.line)


def _check_block(
    statements: tuple[Stmt, ...],
    env: set[str],
    functions: dict[str, Function],
    *,
    allow_tail_return: bool,
) -> tuple[set[str], bool]:
    current = set(env)
    returned = False
    for index, stmt in enumerate(statements):
        if returned:
            raise InscriptionError("unreachable statement after Return", getattr(stmt, "line", None))
        is_last = index == len(statements) - 1
        if isinstance(stmt, SetStmt):
            _check_expr(stmt.expr, current, functions)
            current.add(stmt.name)
        elif isinstance(stmt, ReturnStmt):
            if not allow_tail_return or not is_last:
                raise InscriptionError("Return is only supported as the final function statement in v0", stmt.line)
            _check_expr(stmt.expr, current, functions)
            returned = True
        elif isinstance(stmt, IfStmt):
            _check_comparison(stmt.condition, current, functions)
            then_env, then_returned = _check_block(stmt.then_body, set(current), functions, allow_tail_return=False)
            else_env, else_returned = _check_block(stmt.else_body, set(current), functions, allow_tail_return=False)
            if then_returned or else_returned:
                raise InscriptionError("Return inside if/otherwise is not part of v0; set a result and return after End if", stmt.line)
            assigned = _assigned_vars(stmt.then_body) | _assigned_vars(stmt.else_body)
            for name in assigned:
                if name in then_env and name in else_env:
                    current.add(name)
        elif isinstance(stmt, WhileStmt):
            _check_comparison(stmt.condition, current, functions)
            assigned = _assigned_vars(stmt.body)
            if not assigned:
                raise InscriptionError("while body must reassign at least one initialized loop-carried variable", stmt.line)
            for name in assigned:
                if name not in current:
                    raise InscriptionError(f"loop-carried variable '{name}' must be initialized before while", stmt.line)
            body_env, body_returned = _check_block(stmt.body, set(current), functions, allow_tail_return=False)
            if body_returned:
                raise InscriptionError("Return inside while is not part of v0", stmt.line)
            for name in assigned:
                if name not in body_env:
                    raise InscriptionError(f"loop-carried variable '{name}' is not initialized by while body", stmt.line)
        else:  # pragma: no cover
            raise AssertionError(stmt)
    return current, returned


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
            raise InscriptionError(f"unknown function '{expr.name}'", expr.line)
        if len(expr.args) != len(target.params):
            raise InscriptionError(
                f"function '{expr.name}' expects {len(target.params)} argument(s), got {len(expr.args)}", expr.line
            )
        for arg in expr.args:
            _check_expr(arg, env, functions)
        return
    raise AssertionError(expr)  # pragma: no cover


def _check_comparison(condition: Comparison, env: set[str], functions: dict[str, Function]) -> None:
    _check_expr(condition.left, env, functions)
    _check_expr(condition.right, env, functions)


def _assigned_vars(statements: tuple[Stmt, ...]) -> set[str]:
    names: set[str] = set()
    for stmt in statements:
        if isinstance(stmt, SetStmt):
            names.add(stmt.name)
        elif isinstance(stmt, IfStmt):
            names |= _assigned_vars(stmt.then_body)
            names |= _assigned_vars(stmt.else_body)
        elif isinstance(stmt, WhileStmt):
            names |= _assigned_vars(stmt.body)
    return names
