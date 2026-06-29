from __future__ import annotations

from .ast import Binary, Call, Comparison, Expr, Function, IfStmt, Integer, Program, ReturnStmt, SetStmt, Stmt, Variable, WhileStmt
from .semantic import analyze


def emit_mlir(program: Program) -> str:
    analyze(program)
    emitter = MlirEmitter()
    return emitter.emit_program(program)


class MlirEmitter:
    def __init__(self):
        self.counter = 0

    def fresh(self) -> str:
        value = f"%v{self.counter}"
        self.counter += 1
        return value

    def emit_program(self, program: Program) -> str:
        lines = ["module {"]
        for fn in program.functions:
            self.emit_function(fn, lines)
        lines.append("}")
        return "\n".join(lines) + "\n"

    def emit_function(self, fn: Function, lines: list[str]) -> None:
        param_values = [self.fresh() for _ in fn.params]
        args = ", ".join(f"{value}: i32" for value in param_values)
        lines.append(f"  func.func @{fn.name}({args}) -> i32 {{")
        env = dict(zip(fn.params, param_values, strict=True))
        self.emit_block(fn.body, env, lines, "    ")
        lines.append("  }")

    def emit_block(self, statements: tuple[Stmt, ...], env: dict[str, str], lines: list[str], indent: str) -> None:
        for stmt in statements:
            if isinstance(stmt, SetStmt):
                env[stmt.name] = self.emit_expr(stmt.expr, env, lines, indent)
            elif isinstance(stmt, ReturnStmt):
                value = self.emit_expr(stmt.expr, env, lines, indent)
                lines.append(f"{indent}func.return {value} : i32")
            elif isinstance(stmt, IfStmt):
                self.emit_if(stmt, env, lines, indent)
            elif isinstance(stmt, WhileStmt):
                self.emit_while(stmt, env, lines, indent)
            else:  # pragma: no cover
                raise AssertionError(stmt)

    def emit_expr(self, expr: Expr, env: dict[str, str], lines: list[str], indent: str) -> str:
        if isinstance(expr, Integer):
            out = self.fresh()
            lines.append(f"{indent}{out} = arith.constant {expr.value} : i32")
            return out
        if isinstance(expr, Variable):
            return env[expr.name]
        if isinstance(expr, Binary):
            left = self.emit_expr(expr.left, env, lines, indent)
            right = self.emit_expr(expr.right, env, lines, indent)
            out = self.fresh()
            op = {"plus": "addi", "minus": "subi", "times": "muli"}[expr.op]
            lines.append(f"{indent}{out} = arith.{op} {left}, {right} : i32")
            return out
        if isinstance(expr, Call):
            args = [self.emit_expr(arg, env, lines, indent) for arg in expr.args]
            out = self.fresh()
            arg_values = ", ".join(args)
            arg_types = ", ".join("i32" for _ in args)
            lines.append(f"{indent}{out} = func.call @{expr.name}({arg_values}) : ({arg_types}) -> i32")
            return out
        raise AssertionError(expr)  # pragma: no cover

    def emit_comparison(self, condition: Comparison, env: dict[str, str], lines: list[str], indent: str) -> str:
        left = self.emit_expr(condition.left, env, lines, indent)
        right = self.emit_expr(condition.right, env, lines, indent)
        out = self.fresh()
        lines.append(f"{indent}{out} = arith.cmpi {condition.pred}, {left}, {right} : i32")
        return out

    def emit_if(self, stmt: IfStmt, env: dict[str, str], lines: list[str], indent: str) -> None:
        cond = self.emit_comparison(stmt.condition, env, lines, indent)
        assigned = _assigned_vars(stmt.then_body) | _assigned_vars(stmt.else_body)
        join_vars = sorted(name for name in assigned if name in _available_after(stmt.then_body, set(env)) and name in _available_after(stmt.else_body, set(env)))
        result = self.fresh() if join_vars else None
        if join_vars:
            result_prefix = f"{result}:{len(join_vars)}" if len(join_vars) > 1 else result
            types = ", ".join("i32" for _ in join_vars)
            lines.append(f"{indent}{result_prefix} = scf.if {cond} -> ({types}) {{")
        else:
            lines.append(f"{indent}scf.if {cond} {{")

        then_env = dict(env)
        self.emit_block(stmt.then_body, then_env, lines, indent + "  ")
        if join_vars:
            values = ", ".join(then_env[name] for name in join_vars)
            types = ", ".join("i32" for _ in join_vars)
            lines.append(f"{indent}  scf.yield {values} : {types}")
        lines.append(f"{indent}}} else {{")

        else_env = dict(env)
        self.emit_block(stmt.else_body, else_env, lines, indent + "  ")
        if join_vars:
            values = ", ".join(else_env[name] for name in join_vars)
            types = ", ".join("i32" for _ in join_vars)
            lines.append(f"{indent}  scf.yield {values} : {types}")
        lines.append(f"{indent}}}")

        if result is not None:
            for index, name in enumerate(join_vars):
                env[name] = result if len(join_vars) == 1 else f"{result}#{index}"

    def emit_while(self, stmt: WhileStmt, env: dict[str, str], lines: list[str], indent: str) -> None:
        loop_vars = sorted(_assigned_vars(stmt.body))
        result = self.fresh()
        result_prefix = f"{result}:{len(loop_vars)}" if len(loop_vars) > 1 else result
        before_names = [self.fresh() for _ in loop_vars]
        body_names = [self.fresh() for _ in loop_vars]
        init = ", ".join(f"{before} = {env[name]}" for before, name in zip(before_names, loop_vars, strict=True))
        types = ", ".join("i32" for _ in loop_vars)
        lines.append(f"{indent}{result_prefix} = scf.while ({init}) : ({types}) -> ({types}) {{")
        before_env = dict(env)
        before_env.update({name: value for name, value in zip(loop_vars, before_names, strict=True)})
        cond = self.emit_comparison(stmt.condition, before_env, lines, indent + "  ")
        carried = ", ".join(before_env[name] for name in loop_vars)
        lines.append(f"{indent}  scf.condition({cond}) {carried} : {types}")
        lines.append(f"{indent}}} do {{")
        block_args = ", ".join(f"{value}: i32" for value in body_names)
        lines.append(f"{indent}^bb0({block_args}):")
        body_env = dict(env)
        body_env.update({name: value for name, value in zip(loop_vars, body_names, strict=True)})
        self.emit_block(stmt.body, body_env, lines, indent + "  ")
        yielded = ", ".join(body_env[name] for name in loop_vars)
        lines.append(f"{indent}  scf.yield {yielded} : {types}")
        lines.append(f"{indent}}}")
        for index, name in enumerate(loop_vars):
            env[name] = result if len(loop_vars) == 1 else f"{result}#{index}"


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


def _available_after(statements: tuple[Stmt, ...], initial: set[str]) -> set[str]:
    current = set(initial)
    for stmt in statements:
        if isinstance(stmt, SetStmt):
            current.add(stmt.name)
        elif isinstance(stmt, IfStmt):
            assigned = _assigned_vars(stmt.then_body) | _assigned_vars(stmt.else_body)
            then_available = _available_after(stmt.then_body, set(current))
            else_available = _available_after(stmt.else_body, set(current))
            for name in assigned:
                if name in then_available and name in else_available:
                    current.add(name)
        elif isinstance(stmt, WhileStmt):
            # While cannot introduce new variables; semantic analysis has already enforced this.
            current |= (_assigned_vars(stmt.body) & current)
    return current
