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
    IfStmt,
    Integer,
    Program,
    ReturnStmt,
    SetStmt,
    Stmt,
    TypeName,
    Unary,
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
        self.binding_order: list[str] = []
        self.while_counter = 0
        self.while_depth = 0

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
        self.binding_order = [param.name for param in fn.params]
        self.while_counter = 0
        self.while_depth = 0
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
            type_name = stmt.type_name or infer_expr_type(stmt.expr, env_types, self.functions)
            env[stmt.name] = self.emit_expr(stmt.expr, env, lines, indent, expected=type_name)
            self.binding_order.append(stmt.name)
            return
        if isinstance(stmt, AssignStmt):
            type_name = env[stmt.name].type_name
            env[stmt.name] = self.emit_expr(stmt.expr, env, lines, indent, expected=type_name)
            return
        if isinstance(stmt, WhileStmt):
            self.emit_while(stmt, env, lines, indent)
            return
        if isinstance(stmt, IfStmt):
            self.emit_if(stmt, env, lines, indent)
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
        if isinstance(expr, Unary):
            if expr.op == "not":
                operand = self.emit_expr(expr.expr, env, lines, indent, expected="i1")
                true = self.emit_boolean(True, lines, indent)
                out = Value(self.fresh(), "i1")
                lines.append(f"{indent}{out.name} = arith.xori {operand.name}, {true.name} : i1")
                return out
            raise AssertionError(expr)  # pragma: no cover
        if isinstance(expr, Binary):
            operand_type = "i1" if expr.op in {"and", "or"} else type_name
            left = self.emit_expr(expr.left, env, lines, indent, expected=operand_type)
            right = self.emit_expr(expr.right, env, lines, indent, expected=operand_type)
            out = Value(self.fresh(), type_name)
            op = {
                "plus": "addi",
                "minus": "subi",
                "times": "muli",
                "divided by": "divsi",
                "remainder": "remsi",
                "and": "andi",
                "or": "ori",
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
        cond = self.emit_expr(case.condition, env, lines, indent, expected="i1")
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
        loop_id = self.while_counter
        self.while_counter += 1
        arg_suffix = "" if self.while_depth == 0 else f"_loop{loop_id}"
        visible_binding_order = list(self.binding_order)
        carried_names = self.assigned_binding_names(stmt.body, visible_binding_order)
        carried_values = [env[name] for name in carried_names]
        carried_types = [value.type_name for value in carried_values]
        result_base = self.fresh() if carried_names else None
        initial_operands = ", ".join(
            f"%{name}_before{arg_suffix} = {value.name}"
            for name, value in zip(carried_names, carried_values, strict=True)
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
            before_env[name] = Value(f"%{name}_before{arg_suffix}", type_name)
        self.emit_with_local_constants(lambda: self.emit_while_before(stmt, before_env, carried_names, carried_types, lines, indent))

        lines.append(f"{indent}}} do {{")
        if carried_names:
            body_args = ", ".join(
                f"%{name}_body{arg_suffix}: {type_name}"
                for name, type_name in zip(carried_names, carried_types, strict=True)
            )
            lines.append(f"{indent}^bb0({body_args}):")
        body_env = dict(env)
        for name, type_name in zip(carried_names, carried_types, strict=True):
            body_env[name] = Value(f"%{name}_body{arg_suffix}", type_name)

        saved_while_depth = self.while_depth
        self.while_depth += 1
        try:
            self.emit_with_local_constants(
                lambda: self.emit_with_binding_scope(
                    lambda: self.emit_while_body(stmt, body_env, carried_names, carried_types, lines, indent)
                )
            )
        finally:
            self.while_depth = saved_while_depth
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

    def emit_if(self, stmt: IfStmt, env: dict[str, Value], lines: list[str], indent: str) -> None:
        visible_binding_order = list(self.binding_order)
        result_names = self.assigned_binding_names((*stmt.then_body, *stmt.else_body), visible_binding_order)
        result_values = [env[name] for name in result_names]
        result_types = [value.type_name for value in result_values]

        cond = self.emit_expr(stmt.condition, env, lines, indent, expected="i1")
        result_base = self.fresh() if result_names else None
        if result_names:
            assignment = f"{result_base}:{len(result_names)} = " if len(result_names) > 1 else f"{result_base} = "
            lines.append(f"{indent}{assignment}scf.if {cond.name} -> ({self.type_list(result_types)}) {{")
        else:
            lines.append(f"{indent}scf.if {cond.name} {{")

        then_env = dict(env)
        self.emit_with_local_constants(
            lambda: self.emit_with_binding_scope(
                lambda: self.emit_if_branch(stmt.then_body, then_env, result_names, result_types, lines, indent)
            )
        )
        lines.append(f"{indent}}} else {{")
        else_env = dict(env)
        self.emit_with_local_constants(
            lambda: self.emit_with_binding_scope(
                lambda: self.emit_if_branch(stmt.else_body, else_env, result_names, result_types, lines, indent)
            )
        )
        lines.append(f"{indent}}}")

        if result_base is not None:
            for index, (name, type_name) in enumerate(zip(result_names, result_types, strict=True)):
                result_name = result_base if len(result_names) == 1 else f"{result_base}#{index}"
                env[name] = Value(result_name, type_name)

    def emit_if_branch(
        self,
        body: tuple[Stmt, ...],
        env: dict[str, Value],
        result_names: list[str],
        result_types: list[TypeName],
        lines: list[str],
        indent: str,
    ) -> None:
        branch_indent = indent + "  "
        for body_stmt in body:
            self.emit_body_stmt(body_stmt, env, lines, branch_indent)
        if result_names:
            yielded = ", ".join(env[name].name for name in result_names)
            lines.append(f"{branch_indent}scf.yield {yielded} : {self.type_list(result_types)}")
        else:
            lines.append(f"{branch_indent}scf.yield")

    def emit_with_local_constants(self, emit: Callable[[], None]) -> None:
        saved = self.constants
        self.constants = {}
        try:
            emit()
        finally:
            self.constants = saved

    def emit_with_binding_scope(self, emit: Callable[[], None]) -> None:
        saved_binding_order = list(self.binding_order)
        try:
            emit()
        finally:
            self.binding_order = saved_binding_order

    def assigned_binding_names(self, body: tuple[Stmt, ...], visible_binding_order: list[str]) -> list[str]:
        visible = set(visible_binding_order)
        assigned: set[str] = set()

        def visit(statements: tuple[Stmt, ...]) -> None:
            for statement in statements:
                if isinstance(statement, AssignStmt):
                    if statement.name in visible:
                        assigned.add(statement.name)
                elif isinstance(statement, WhileStmt):
                    visit(statement.body)
                elif isinstance(statement, IfStmt):
                    visit(statement.then_body)
                    visit(statement.else_body)

        visit(body)
        return [name for name in visible_binding_order if name in assigned]

    def type_list(self, types: list[TypeName]) -> str:
        return ", ".join(types)

    def result_type_list(self, types: list[TypeName]) -> str:
        if len(types) == 1:
            return types[0]
        return f"({self.type_list(types)})"
