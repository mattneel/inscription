from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .ast import (
    AssignStmt,
    Binary,
    Boolean,
    Call,
    Comparison,
    Expr,
    Function,
    Integer,
    Program,
    ReturnStmt,
    SetStmt,
    Stmt,
    TrackStmt,
    TypeName,
    Variable,
    WhenCase,
    WhenExpr,
    WhileStmt,
)
from .semantic import analyze, function_table, infer_comparison_operand_type, infer_expr_type


@dataclass(frozen=True)
class Value:
    name: str
    type_name: TypeName


ConstantKey = tuple[str, int | bool, TypeName]


def emit_mlir(program: Program) -> str:
    analyze(program)
    emitter = MlirEmitter(program)
    return emitter.emit_program(program)


class MlirEmitter:
    def __init__(self, program: Program):
        self.functions = function_table(program)
        self.counter = 0
        self.constants: dict[ConstantKey, Value] = {}
        self.tracked_types: dict[str, TypeName] = {}
        self.track_order: list[str] = []

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
        self.tracked_types = {}
        self.track_order = []
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
            if isinstance(stmt, ReturnStmt):
                value = self.emit_expr(stmt.expr, env, lines, indent, expected=return_type)
                lines.append(f"{indent}return {value.name} : {return_type}")
            else:
                self.emit_body_stmt(stmt, env, lines, indent)

    def emit_body_stmt(self, stmt: Stmt, env: dict[str, Value], lines: list[str], indent: str) -> None:
        if isinstance(stmt, SetStmt):
            env_types = {name: value.type_name for name, value in env.items()}
            type_name = infer_expr_type(stmt.expr, env_types, self.functions)
            env[stmt.name] = self.emit_expr(stmt.expr, env, lines, indent, expected=type_name)
            return
        if isinstance(stmt, TrackStmt):
            value = self.emit_expr(stmt.expr, env, lines, indent, expected=stmt.type_name)
            env[stmt.name] = value
            self.tracked_types[stmt.name] = stmt.type_name
            self.track_order.append(stmt.name)
            return
        if isinstance(stmt, AssignStmt):
            type_name = self.tracked_types[stmt.name]
            env[stmt.name] = self.emit_expr(stmt.expr, env, lines, indent, expected=type_name)
            return
        if isinstance(stmt, WhileStmt):
            self.emit_while(stmt, env, lines, indent)
            return
        raise AssertionError(stmt)  # pragma: no cover

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
        if isinstance(expr, Boolean):
            return self.emit_boolean(expr.value, lines, indent)
        if isinstance(expr, Variable):
            return env[expr.name]
        if isinstance(expr, Binary):
            left = self.emit_expr(expr.left, env, lines, indent, expected=type_name)
            right = self.emit_expr(expr.right, env, lines, indent, expected=type_name)
            out = Value(self.fresh(), type_name)
            op = {
                "plus": "addi",
                "minus": "subi",
                "times": "muli",
                "divided by": "divsi",
                "remainder": "remsi",
            }[expr.op]
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
        key: ConstantKey = ("int", value, type_name)
        cached = self.constants.get(key)
        if cached is not None:
            return cached
        out = Value(self.fresh(), type_name)
        self.constants[key] = out
        lines.append(f"{indent}{out.name} = arith.constant {value} : {type_name}")
        return out

    def emit_boolean(self, value: bool, lines: list[str], indent: str) -> Value:
        key: ConstantKey = ("bool", value, "i1")
        cached = self.constants.get(key)
        if cached is not None:
            return cached
        out = Value(self.fresh(), "i1")
        self.constants[key] = out
        literal = "true" if value else "false"
        lines.append(f"{indent}{out.name} = arith.constant {literal}")
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

    def emit_while(self, stmt: WhileStmt, env: dict[str, Value], lines: list[str], indent: str) -> None:
        carried_names = self.loop_carried_names(stmt)
        carried_values = [env[name] for name in carried_names]
        carried_types = [value.type_name for value in carried_values]
        result_base = self.fresh() if carried_names else None
        initial_operands = ", ".join(
            f"%{name}_before = {value.name}" for name, value in zip(carried_names, carried_values, strict=True)
        )
        input_types = self.type_list(carried_types)
        result_types = self.result_type_list(carried_types)
        if carried_names:
            assignment = f"{result_base}:{len(carried_names)} = " if len(carried_names) > 1 else f"{result_base} = "
            lines.append(f"{indent}{assignment}scf.while ({initial_operands}) : ({input_types}) -> {result_types} {{")
        else:
            lines.append(f"{indent}scf.while : () -> () {{")

        before_env = dict(env)
        for name, type_name in zip(carried_names, carried_types, strict=True):
            before_env[name] = Value(f"%{name}_before", type_name)
        self.emit_with_local_constants(lambda: self.emit_while_before(stmt, before_env, carried_names, carried_types, lines, indent))

        lines.append(f"{indent}}} do {{")
        if carried_names:
            body_args = ", ".join(f"%{name}_body: {type_name}" for name, type_name in zip(carried_names, carried_types, strict=True))
            lines.append(f"{indent}^bb0({body_args}):")
        body_env = dict(env)
        for name, type_name in zip(carried_names, carried_types, strict=True):
            body_env[name] = Value(f"%{name}_body", type_name)
        self.emit_with_local_constants(lambda: self.emit_while_body(stmt, body_env, carried_names, carried_types, lines, indent))
        lines.append(f"{indent}}}")

        if result_base is not None:
            for index, (name, type_name) in enumerate(zip(carried_names, carried_types, strict=True)):
                result_name = result_base if len(carried_names) == 1 else f"{result_base}#{index}"
                env[name] = Value(result_name, type_name)

    def emit_while_before(
        self,
        stmt: WhileStmt,
        env: dict[str, Value],
        carried_names: list[str],
        carried_types: list[TypeName],
        lines: list[str],
        indent: str,
    ) -> None:
        cond = self.emit_expr(stmt.condition, env, lines, indent + "  ", expected="i1")
        if carried_names:
            forwarded = ", ".join(env[name].name for name in carried_names)
            lines.append(f"{indent}  scf.condition({cond.name}) {forwarded} : {self.type_list(carried_types)}")
        else:
            lines.append(f"{indent}  scf.condition({cond.name})")

    def emit_while_body(
        self,
        stmt: WhileStmt,
        env: dict[str, Value],
        carried_names: list[str],
        carried_types: list[TypeName],
        lines: list[str],
        indent: str,
    ) -> None:
        for body_stmt in stmt.body:
            self.emit_body_stmt(body_stmt, env, lines, indent + "  ")
        if carried_names:
            yielded = ", ".join(env[name].name for name in carried_names)
            lines.append(f"{indent}  scf.yield {yielded} : {self.type_list(carried_types)}")
        else:
            lines.append(f"{indent}  scf.yield")

    def emit_with_local_constants(self, emit: Callable[[], None]) -> None:
        saved = self.constants
        self.constants = {}
        try:
            emit()
        finally:
            self.constants = saved

    def loop_carried_names(self, stmt: WhileStmt) -> list[str]:
        assigned = {body_stmt.name for body_stmt in stmt.body if isinstance(body_stmt, AssignStmt)}
        return [name for name in self.track_order if name in assigned]

    def type_list(self, types: list[TypeName]) -> str:
        return ", ".join(types)

    def result_type_list(self, types: list[TypeName]) -> str:
        if len(types) == 1:
            return types[0]
        return f"({self.type_list(types)})"
