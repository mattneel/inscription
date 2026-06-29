from __future__ import annotations

from .ast import Binary, Call, Comparison, Expr, Function, Integer, Program, ReturnStmt, SetStmt, Stmt, Variable, WhenCase, WhenExpr
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
        if isinstance(expr, WhenExpr):
            return self.emit_when_expr(expr, env, lines, indent)
        raise AssertionError(expr)  # pragma: no cover

    def emit_when_expr(self, expr: WhenExpr, env: dict[str, str], lines: list[str], indent: str) -> str:
        return self.emit_when_cases(list(expr.cases), expr.otherwise, env, lines, indent)

    def emit_when_cases(
        self,
        cases: list[WhenCase],
        otherwise: Expr,
        env: dict[str, str],
        lines: list[str],
        indent: str,
    ) -> str:
        if not cases:
            return self.emit_expr(otherwise, env, lines, indent)
        case = cases[0]
        cond = self.emit_comparison(case.condition, env, lines, indent)
        result = self.fresh()
        lines.append(f"{indent}{result} = scf.if {cond} -> (i32) {{")
        then_value = self.emit_expr(case.expr, dict(env), lines, indent + "  ")
        lines.append(f"{indent}  scf.yield {then_value} : i32")
        lines.append(f"{indent}}} else {{")
        else_value = self.emit_when_cases(cases[1:], otherwise, dict(env), lines, indent + "  ")
        lines.append(f"{indent}  scf.yield {else_value} : i32")
        lines.append(f"{indent}}}")
        return result

    def emit_comparison(self, condition: Comparison, env: dict[str, str], lines: list[str], indent: str) -> str:
        left = self.emit_expr(condition.left, env, lines, indent)
        right = self.emit_expr(condition.right, env, lines, indent)
        out = self.fresh()
        lines.append(f"{indent}{out} = arith.cmpi {condition.pred}, {left}, {right} : i32")
        return out
