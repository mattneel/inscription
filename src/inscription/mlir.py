from __future__ import annotations

from dataclasses import dataclass

from .ast import Binary, Call, Comparison, Expr, Function, Integer, Program, ReturnStmt, SetStmt, Stmt, TypeName, Variable, WhenCase, WhenExpr
from .semantic import analyze, function_table, infer_comparison_operand_type, infer_expr_type


@dataclass(frozen=True)
class Value:
    name: str
    type_name: TypeName


def emit_mlir(program: Program) -> str:
    analyze(program)
    emitter = MlirEmitter(program)
    return emitter.emit_program(program)


class MlirEmitter:
    def __init__(self, program: Program):
        self.functions = function_table(program)
        self.counter = 0
        self.constants: dict[tuple[int, TypeName], Value] = {}

    def fresh(self) -> str:
        value = f"%{self.counter}"
        self.counter += 1
        return value

    def emit_program(self, program: Program) -> str:
        lines = ["module {"]
        for index, fn in enumerate(program.functions):
            if index:
                lines.append("")
            self.emit_function(fn, lines)
        lines.append("}")
        return "\n".join(lines) + "\n"

    def emit_function(self, fn: Function, lines: list[str]) -> None:
        self.counter = 0
        self.constants = {}
        args = ", ".join(f"%{param.name}: {param.type_name}" for param in fn.params)
        lines.append(f"  func.func @{fn.name}({args}) -> {fn.return_type} {{")
        env = {param.name: Value(f"%{param.name}", param.type_name) for param in fn.params}
        self.emit_block(fn.body, env, lines, "    ", fn.return_type)
        lines.append("  }")

    def emit_block(
        self,
        statements: tuple[Stmt, ...],
        env: dict[str, Value],
        lines: list[str],
        indent: str,
        return_type: TypeName,
    ) -> None:
        for stmt in statements:
            if isinstance(stmt, SetStmt):
                env_types = {name: value.type_name for name, value in env.items()}
                type_name = infer_expr_type(stmt.expr, env_types, self.functions)
                env[stmt.name] = self.emit_expr(stmt.expr, env, lines, indent, expected=type_name)
            elif isinstance(stmt, ReturnStmt):
                value = self.emit_expr(stmt.expr, env, lines, indent, expected=return_type)
                lines.append(f"{indent}return {value.name} : {return_type}")
            else:  # pragma: no cover
                raise AssertionError(stmt)

    def emit_expr(
        self,
        expr: Expr,
        env: dict[str, Value],
        lines: list[str],
        indent: str,
        *,
        expected: TypeName | None = None,
    ) -> Value:
        env_types = {name: value.type_name for name, value in env.items()}
        type_name = infer_expr_type(expr, env_types, self.functions, expected=expected)
        if isinstance(expr, Integer):
            return self.emit_integer(expr.value, type_name, lines, indent)
        if isinstance(expr, Variable):
            return env[expr.name]
        if isinstance(expr, Binary):
            left = self.emit_expr(expr.left, env, lines, indent, expected=type_name)
            right = self.emit_expr(expr.right, env, lines, indent, expected=type_name)
            out = Value(self.fresh(), type_name)
            op = {"plus": "addi", "minus": "subi", "times": "muli", "divided by": "divsi"}[expr.op]
            lines.append(f"{indent}{out.name} = arith.{op} {left.name}, {right.name} : {type_name}")
            return out
        if isinstance(expr, Call):
            target = self.functions[expr.name]
            args = [
                self.emit_expr(arg, env, lines, indent, expected=param.type_name)
                for arg, param in zip(expr.args, target.params, strict=True)
            ]
            out = Value(self.fresh(), target.return_type)
            arg_values = ", ".join(arg.name for arg in args)
            arg_types = ", ".join(arg.type_name for arg in args)
            lines.append(f"{indent}{out.name} = func.call @{expr.name}({arg_values}) : ({arg_types}) -> {target.return_type}")
            return out
        if isinstance(expr, Comparison):
            return self.emit_comparison(expr, env, lines, indent)
        if isinstance(expr, WhenExpr):
            return self.emit_when_expr(expr, env, lines, indent, type_name)
        raise AssertionError(expr)  # pragma: no cover

    def emit_integer(self, value: int, type_name: TypeName, lines: list[str], indent: str) -> Value:
        key = (value, type_name)
        cached = self.constants.get(key)
        if cached is not None:
            return cached
        out = Value(self.fresh(), type_name)
        self.constants[key] = out
        lines.append(f"{indent}{out.name} = arith.constant {value} : {type_name}")
        return out

    def emit_when_expr(
        self, expr: WhenExpr, env: dict[str, Value], lines: list[str], indent: str, type_name: TypeName
    ) -> Value:
        return self.emit_when_cases(list(expr.cases), expr.otherwise, env, lines, indent, type_name)

    def emit_when_cases(
        self,
        cases: list[WhenCase],
        otherwise: Expr,
        env: dict[str, Value],
        lines: list[str],
        indent: str,
        type_name: TypeName,
    ) -> Value:
        if not cases:
            return self.emit_expr(otherwise, env, lines, indent, expected=type_name)
        case = cases[0]
        cond = self.emit_comparison(case.condition, env, lines, indent)
        result = Value(self.fresh(), type_name)
        lines.append(f"{indent}{result.name} = scf.if {cond.name} -> ({type_name}) {{")
        then_value = self.emit_expr(case.expr, dict(env), lines, indent + "  ", expected=type_name)
        lines.append(f"{indent}  scf.yield {then_value.name} : {type_name}")
        lines.append(f"{indent}}} else {{")
        else_value = self.emit_when_cases(cases[1:], otherwise, dict(env), lines, indent + "  ", type_name)
        lines.append(f"{indent}  scf.yield {else_value.name} : {type_name}")
        lines.append(f"{indent}}}")
        return result

    def emit_comparison(self, condition: Comparison, env: dict[str, Value], lines: list[str], indent: str) -> Value:
        env_types = {name: value.type_name for name, value in env.items()}
        type_name = infer_comparison_operand_type(condition, env_types, self.functions)
        left = self.emit_expr(condition.left, env, lines, indent, expected=type_name)
        right = self.emit_expr(condition.right, env, lines, indent, expected=type_name)
        out = Value(self.fresh(), "i1")
        lines.append(f"{indent}{out.name} = arith.cmpi {condition.pred}, {left.name}, {right.name} : {type_name}")
        return out
