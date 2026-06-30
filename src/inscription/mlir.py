from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .ast import (
    ArrayBinding,
    ArrayType,
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
    CheckStmt,
    Comparison,
    EnumCase,
    EnumType,
    Expr,
    FieldAccess,
    FieldAssignStmt,
    Float,
    ForEachStmt,
    ForStmt,
    Function,
    IfStmt,
    Integer,
    AlignmentOfType,
    LengthOf,
    LayoutRead,
    LayoutWriteStmt,
    MatchExpr,
    MatchStep,
    OffsetOfField,
    Program,
    RecordConstructor,
    RecordType,
    RequireStmt,
    ReturnStmt,
    SetStmt,
    SizeOfType,
    Stmt,
    TypeName,
    Unary,
    UnionConstructor,
    UnionPattern,
    UnionType,
    Variable,
    ViewBinding,
    ViewType,
    WhenCase,
    WhenExpr,
    WhileStmt,
)
from .semantic import (
    ValueType,
    all_ones_constant_value,
    analyze,
    byte_width,
    CompileTimeEvaluationError,
    constant_table,
    enum_table,
    evaluate_const_expr,
    function_table,
    infer_comparison_operand_type,
    infer_expr_type,
    is_float_type,
    is_integer_type,
    is_signed_type,
    layout_info,
    memref_type,
    mlir_type,
    record_table,
    resolve_array_type,
    resolve_buffer_type,
    resolve_function_table,
    storage_type,
    type_width,
    union_table,
    validate_union_payloads,
)


@dataclass(frozen=True)
class Value:
    name: str
    type_name: ValueType


@dataclass(frozen=True)
class BufferStorage:
    name: str
    buffer_type: BufferType


@dataclass(frozen=True)
class ArrayStorage:
    name: str
    array_type: ArrayType


@dataclass(frozen=True)
class ViewStorage:
    base: str
    start: Value
    length: Value
    element_type: ValueType
    static_length: int | None
    root: str

    @property
    def name(self) -> str:
        return self.base

    @property
    def view_type(self) -> ViewType:
        return ViewType(self.element_type, self.static_length)


@dataclass(frozen=True)
class RecordStorage:
    record_type: RecordType
    fields: dict[str, Value]


@dataclass(frozen=True)
class UnionStorage:
    union_type: UnionType
    slots: dict[str, Value]


@dataclass(frozen=True)
class CarrySlot:
    name: str
    field: str | None
    type_name: ValueType

    @property
    def label(self) -> str:
        if self.field is None:
            return self.name
        return f"{self.name}_{self.field}"


@dataclass(frozen=True)
class CallArg:
    name: str
    mlir_type: str


EnvValue = Value | BufferStorage | ArrayStorage | ViewStorage | RecordStorage | UnionStorage
ConstantKey = tuple[str, int | bool | float, ValueType]


def mlir_value_type(type_name: ValueType) -> str:
    if isinstance(type_name, BufferType):
        return memref_type(type_name)
    if isinstance(type_name, ArrayType):
        return memref_type(type_name)
    if isinstance(type_name, ViewType):
        return dynamic_memref_type(type_name.element_type)
    if isinstance(type_name, RecordType | UnionType):
        raise AssertionError("aggregate type must be flattened before MLIR type emission")  # pragma: no cover
    return mlir_type(type_name)


def mlir_env_value_type(value: "EnvValue") -> str:
    if isinstance(value, BufferStorage):
        return memref_type(value.buffer_type)
    if isinstance(value, ArrayStorage):
        return memref_type(value.array_type)
    if isinstance(value, ViewStorage):
        return dynamic_memref_type(value.element_type)
    if isinstance(value, RecordStorage | UnionStorage):
        raise AssertionError("aggregate value must be flattened before MLIR type emission")  # pragma: no cover
    return mlir_type(value.type_name)


def dynamic_memref_type(element_type: ValueType) -> str:
    return f"memref<?x{mlir_type(element_type)}>"


def emit_mlir(program: Program, *, runtime_checks: bool = False) -> str:
    analyze(program)
    emitter = MlirEmitter(program, runtime_checks=runtime_checks)
    return emitter.emit_program(program)


class MlirEmitter:
    def __init__(self, program: Program, *, runtime_checks: bool = False):
        self.enums = enum_table(program)
        self.unions = union_table(program)
        self.records = record_table(program)
        validate_union_payloads(self.unions, self.records)
        raw_functions = function_table(program)
        self.top_constants = constant_table(program, self.records, raw_functions)
        self.functions = resolve_function_table(raw_functions, self.records, self.top_constants)
        self.runtime_checks = runtime_checks
        self.counter = 0
        self.constants: dict[ConstantKey, Value] = {}
        self.binding_order: list[str] = []
        self.record_order: list[str] = []
        self.union_order: list[str] = []
        self.while_counter = 0
        self.while_depth = 0
        self.for_counter = 0
        self.for_depth = 0

    def fresh(self) -> str:
        value = f"%{self.counter}"
        self.counter += 1
        return value

    def emit_program(self, program: Program) -> str:
        lines = ["module {"]
        emitted_declarations: set[str] = set()
        emitted_any = False
        for fn in program.functions:
            resolved = self.functions[fn.name]
            if resolved.implementation != "extern" or resolved.extern_symbol in emitted_declarations:
                continue
            self.emit_extern_declaration(resolved, lines)
            emitted_declarations.add(resolved.extern_symbol)
            emitted_any = True
        normal_functions = [fn for fn in program.functions if self.functions[fn.name].implementation != "extern"]
        for index, fn in enumerate(normal_functions):
            if emitted_any or index:
                lines.append("")
            self.emit_function(fn, lines)
            emitted_any = True
        lines.append("}")
        return "\n".join(lines) + "\n"

    def emit_extern_declaration(self, fn: Function, lines: list[str]) -> None:
        assert fn.extern_symbol is not None
        args = ", ".join(self.function_argument_types(fn))
        return_suffix = "" if fn.return_type is None else f" -> {self.return_type_list(fn.return_type)}"
        lines.append(f"  func.func private @{fn.extern_symbol}({args}){return_suffix}")

    def emit_function(self, fn: Function, lines: list[str]) -> None:
        fn = self.functions[fn.name]
        self.counter = 0
        self.constants = {}
        self.binding_order = [
            param.name
            for param in fn.params
            if not isinstance(param.type_name, BufferType | ArrayType | ViewType | RecordType | UnionType)
        ]
        self.record_order = [param.name for param in fn.params if isinstance(param.type_name, RecordType)]
        self.union_order = [param.name for param in fn.params if isinstance(param.type_name, UnionType)]
        self.while_counter = 0
        self.while_depth = 0
        self.for_counter = 0
        self.for_depth = 0
        args = ", ".join(self.function_argument_decls(fn))
        return_suffix = "" if fn.return_type is None else f" -> {self.return_type_list(fn.return_type)}"
        lines.append(f"  func.func @{self.call_symbol(fn)}({args}){return_suffix} {{")
        env: dict[str, EnvValue] = {}
        for param in fn.params:
            if isinstance(param.type_name, BufferType):
                env[param.name] = BufferStorage(f"%{param.name}", param.type_name)
            elif isinstance(param.type_name, ViewType):
                env[param.name] = ViewStorage(
                    f"%{param.name}_base",
                    Value(f"%{param.name}_start", "i32"),
                    Value(f"%{param.name}_length", "i32"),
                    param.type_name.element_type,
                    None,
                    param.name,
                )
            elif isinstance(param.type_name, RecordType):
                env[param.name] = self.record_parameter_storage(param.name, param.type_name)
            elif isinstance(param.type_name, UnionType):
                env[param.name] = self.union_parameter_storage(param.name, param.type_name)
            else:
                env[param.name] = Value(f"%{param.name}", param.type_name)
        if fn.return_type is None:
            self.emit_steps(fn.body, env, lines, "    ")
            lines.append("    return")
        else:
            self.emit_block(fn.body, env, lines, "    ", fn.return_type)
        lines.append("  }")

    def function_argument_decls(self, fn: Function) -> list[str]:
        args: list[str] = []
        for param in fn.params:
            if isinstance(param.type_name, BufferType):
                args.append(f"%{param.name}: {memref_type(param.type_name)}")
                continue
            if isinstance(param.type_name, ViewType):
                args.append(f"%{param.name}_base: {dynamic_memref_type(param.type_name.element_type)}")
                args.append(f"%{param.name}_start: i32")
                args.append(f"%{param.name}_length: i32")
                continue
            if isinstance(param.type_name, RecordType):
                for field in self.record_fields(param.type_name):
                    args.append(f"%{param.name}_{field.name}: {mlir_type(field.type_name)}")
                continue
            if isinstance(param.type_name, UnionType):
                for slot in self.union_slot_types(param.type_name):
                    args.append(f"%{param.name}_{slot[0]}: {mlir_type(slot[1])}")
                continue
            args.append(f"%{param.name}: {mlir_type(param.type_name)}")
        return args

    def function_argument_types(self, fn: Function) -> list[str]:
        args: list[str] = []
        for param in fn.params:
            if isinstance(param.type_name, BufferType):
                args.append(memref_type(param.type_name))
                continue
            if isinstance(param.type_name, ViewType):
                args.append(dynamic_memref_type(param.type_name.element_type))
                args.append("i32")
                args.append("i32")
                continue
            if isinstance(param.type_name, RecordType):
                for field in self.record_fields(param.type_name):
                    args.append(mlir_type(field.type_name))
                continue
            if isinstance(param.type_name, UnionType):
                for _slot_name, slot_type in self.union_slot_types(param.type_name):
                    args.append(mlir_type(slot_type))
                continue
            args.append(mlir_type(param.type_name))
        return args

    def record_parameter_storage(self, name: str, record_type: RecordType) -> RecordStorage:
        return RecordStorage(
            record_type,
            {
                field.name: Value(f"%{name}_{field.name}", field.type_name)
                for field in self.record_fields(record_type)
            },
        )

    def union_parameter_storage(self, name: str, union_type: UnionType) -> UnionStorage:
        return UnionStorage(
            union_type,
            {
                slot_name: Value(f"%{name}_{slot_name}", slot_type)
                for slot_name, slot_type in self.union_slot_types(union_type)
            },
        )

    def emit_steps(
        self,
        statements: tuple[Stmt, ...],
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
    ) -> None:
        for stmt in statements:
            self.emit_body_stmt(stmt, env, lines, indent)

    def emit_block(
        self,
        statements: tuple[Stmt, ...],
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        return_type: TypeName | RecordType | UnionType,
    ) -> None:
        for stmt in statements:
            if isinstance(stmt, ReturnStmt):
                if isinstance(return_type, RecordType):
                    record = self.emit_record_expr(stmt.expr, env, lines, indent, expected=return_type)
                    fields = self.record_fields(return_type)
                    values = [record.fields[field.name] for field in fields]
                    lines.append(
                        f"{indent}return {', '.join(value.name for value in values)} : "
                        f"{', '.join(mlir_type(value.type_name) for value in values)}"
                    )
                elif isinstance(return_type, UnionType):
                    union = self.emit_union_expr(stmt.expr, env, lines, indent, expected=return_type)
                    values = self.union_values(union)
                    lines.append(
                        f"{indent}return {', '.join(value.name for value in values)} : "
                        f"{', '.join(mlir_type(value.type_name) for value in values)}"
                    )
                else:
                    value = self.emit_expr(stmt.expr, env, lines, indent, expected=return_type)
                    lines.append(f"{indent}return {value.name} : {mlir_type(return_type)}")
            else:
                self.emit_body_stmt(stmt, env, lines, indent)

    def emit_body_stmt(self, stmt: Stmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        if isinstance(stmt, CheckStmt):
            return
        if isinstance(stmt, RequireStmt):
            self.emit_require(stmt, env, lines, indent)
            return
        if isinstance(stmt, SetStmt):
            env_types = self.env_types(env)
            type_name = stmt.type_name or infer_expr_type(
                stmt.expr, env_types, self.functions, self.records, constants=self.top_constants
            )
            if isinstance(type_name, RecordType):
                env[stmt.name] = self.emit_record_expr(stmt.expr, env, lines, indent, expected=type_name)
                self.record_order.append(stmt.name)
            elif isinstance(type_name, UnionType):
                env[stmt.name] = self.emit_union_expr(stmt.expr, env, lines, indent, expected=type_name)
                self.union_order.append(stmt.name)
            elif isinstance(type_name, ArrayType | ViewType):
                raise AssertionError("view binding must use view syntax")  # pragma: no cover
            else:
                env[stmt.name] = self.emit_expr(stmt.expr, env, lines, indent, expected=type_name)
                self.binding_order.append(stmt.name)
            return
        if isinstance(stmt, BufferBinding):
            self.emit_buffer_binding(stmt, env, lines, indent)
            return
        if isinstance(stmt, ArrayBinding):
            self.emit_array_binding(stmt, env, lines, indent)
            return
        if isinstance(stmt, ViewBinding):
            self.emit_view_binding(stmt, env, lines, indent)
            return
        if isinstance(stmt, AssignStmt):
            current_value = env[stmt.name]
            if isinstance(current_value, RecordStorage):
                env[stmt.name] = self.emit_record_expr(stmt.expr, env, lines, indent, expected=current_value.record_type)
            elif isinstance(current_value, UnionStorage):
                env[stmt.name] = self.emit_union_expr(stmt.expr, env, lines, indent, expected=current_value.union_type)
            elif isinstance(current_value, ArrayStorage | ViewStorage):
                raise AssertionError("storage rebinding should be rejected by semantic analysis")  # pragma: no cover
            else:
                current = self.require_scalar(current_value)
                env[stmt.name] = self.emit_expr(stmt.expr, env, lines, indent, expected=current.type_name)
            return
        if isinstance(stmt, BufferStoreStmt):
            self.emit_buffer_store(stmt, env, lines, indent)
            return
        if isinstance(stmt, FieldAssignStmt):
            self.emit_field_assign(stmt, env, lines, indent)
            return
        if isinstance(stmt, LayoutWriteStmt):
            self.emit_layout_write(stmt, env, lines, indent)
            return
        if isinstance(stmt, CallStmt):
            self.emit_call_stmt(stmt, env, lines, indent)
            return
        if isinstance(stmt, WhileStmt):
            self.emit_while(stmt, env, lines, indent)
            return
        if isinstance(stmt, ForStmt):
            self.emit_for(stmt, env, lines, indent)
            return
        if isinstance(stmt, ForEachStmt):
            self.emit_for_each(stmt, env, lines, indent)
            return
        if isinstance(stmt, IfStmt):
            self.emit_if(stmt, env, lines, indent)
            return
        if isinstance(stmt, MatchStep):
            self.emit_match_step(stmt, env, lines, indent)
            return
        raise AssertionError(stmt)  # pragma: no cover

    def emit_expr(
        self,
        expr: Expr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        *,
        expected: ValueType | None = None,
    ) -> Value:
        env_types = self.env_types(env)
        type_name = infer_expr_type(
            expr, env_types, self.functions, self.records, expected=expected, constants=self.top_constants
        )
        if isinstance(type_name, RecordType):
            raise AssertionError("record expression used where scalar value was expected")  # pragma: no cover
        if isinstance(type_name, UnionType):
            raise AssertionError("union expression used where scalar value was expected")  # pragma: no cover
        if isinstance(expr, Integer):
            if is_float_type(type_name) and expr.is_word_zero:
                return self.emit_float(0.0, type_name, lines, indent)
            return self.emit_integer(expr.value, type_name, lines, indent)
        if isinstance(expr, Float):
            return self.emit_float(float(expr.text), type_name, lines, indent)
        if isinstance(expr, Boolean):
            return self.emit_boolean(expr.value, lines, indent)
        if isinstance(expr, EnumCase):
            info = self.enums.get(expr.type_name)
            if info is None:
                raise AssertionError("union constructor used where scalar value was expected")  # pragma: no cover
            return self.emit_integer(info.cases[expr.case_name], type_name, lines, indent)
        if isinstance(expr, Variable):
            if expr.name in self.top_constants:
                return self.emit_const_value(self.top_constants[expr.name], lines, indent)
            return self.require_scalar(env[expr.name])
        if isinstance(expr, BufferLoad):
            return self.emit_buffer_load(expr, env, lines, indent)
        if isinstance(expr, LengthOf):
            storage = self.require_indexable(env[expr.name])
            if isinstance(storage, BufferStorage):
                return self.emit_integer(storage.buffer_type.length, "i32", lines, indent)
            if isinstance(storage, ArrayStorage):
                return self.emit_integer(storage.array_type.length, "i32", lines, indent)
            return storage.length
        if isinstance(expr, SizeOfType):
            return self.emit_integer(layout_info(self.records[expr.type_name]).size, "i32", lines, indent)
        if isinstance(expr, AlignmentOfType):
            return self.emit_integer(layout_info(self.records[expr.type_name]).alignment, "i32", lines, indent)
        if isinstance(expr, OffsetOfField):
            return self.emit_integer(layout_info(self.records[expr.type_name]).field_offsets[expr.field], "i32", lines, indent)
        if isinstance(expr, FieldAccess):
            qualified_constant = f"{expr.name}.{expr.field}"
            if expr.name not in env and qualified_constant in self.top_constants:
                return self.emit_const_value(self.top_constants[qualified_constant], lines, indent)
            return self.require_record(env[expr.name]).fields[expr.field]
        if isinstance(expr, RecordConstructor):
            raise AssertionError("record constructor used where scalar value was expected")  # pragma: no cover
        if isinstance(expr, LayoutRead):
            raise AssertionError("layout read used where scalar value was expected")  # pragma: no cover
        if isinstance(expr, Unary):
            return self.emit_unary(expr, env, lines, indent, type_name)
        if isinstance(expr, Cast):
            return self.emit_cast(expr, env, lines, indent, type_name)
        if isinstance(expr, Binary):
            return self.emit_binary(expr, env, lines, indent, type_name)
        if isinstance(expr, Call):
            target = self.functions[expr.name]
            args = self.emit_call_arguments(expr, target, env, lines, indent)
            assert target.return_type is not None
            assert not isinstance(target.return_type, RecordType | UnionType | ViewType)
            out = Value(self.fresh(), target.return_type)
            arg_values = ", ".join(arg.name for arg in args)
            arg_types = ", ".join(arg.mlir_type for arg in args)
            lines.append(
                f"{indent}{out.name} = func.call @{self.call_symbol(target)}({arg_values}) : ({arg_types}) -> {mlir_type(target.return_type)}"
            )
            return out
        if isinstance(expr, Comparison):
            return self.emit_comparison(expr, env, lines, indent)
        if isinstance(expr, WhenExpr):
            return self.emit_when_expr(expr, env, lines, indent, type_name)
        if isinstance(expr, MatchExpr):
            return self.emit_match_expr(expr, env, lines, indent, type_name)
        raise AssertionError(expr)  # pragma: no cover

    def emit_unary(self, expr: Unary, env: dict[str, EnvValue], lines: list[str], indent: str, type_name: ValueType) -> Value:
        if expr.op == "not":
            operand = self.emit_expr(expr.expr, env, lines, indent, expected="i1")
            true = self.emit_boolean(True, lines, indent)
            out = Value(self.fresh(), "i1")
            lines.append(f"{indent}{out.name} = arith.xori {operand.name}, {true.name} : i1")
            return out
        if expr.op == "bitwise not":
            operand = self.emit_expr(expr.expr, env, lines, indent, expected=type_name)
            all_ones = self.emit_integer(all_ones_constant_value(type_name), type_name, lines, indent)
            out = Value(self.fresh(), type_name)
            lines.append(f"{indent}{out.name} = arith.xori {operand.name}, {all_ones.name} : {mlir_type(type_name)}")
            return out
        raise AssertionError(expr)  # pragma: no cover

    def emit_binary(self, expr: Binary, env: dict[str, EnvValue], lines: list[str], indent: str, type_name: ValueType) -> Value:
        operand_type = "i1" if expr.op in {"and", "or"} else type_name
        left = self.emit_expr(expr.left, env, lines, indent, expected=operand_type)
        right = self.emit_expr(expr.right, env, lines, indent, expected=operand_type)
        out = Value(self.fresh(), type_name)
        op = self.binary_mlir_op(expr.op, type_name)
        lines.append(f"{indent}{out.name} = arith.{op} {left.name}, {right.name} : {mlir_type(type_name)}")
        return out

    def binary_mlir_op(self, op: str, type_name: ValueType) -> str:
        if op == "plus":
            return "addf" if is_float_type(type_name) else "addi"
        if op == "minus":
            return "subf" if is_float_type(type_name) else "subi"
        if op == "times":
            return "mulf" if is_float_type(type_name) else "muli"
        if op == "divided by":
            if is_float_type(type_name):
                return "divf"
            return "divsi" if is_signed_type(type_name) else "divui"
        if op == "remainder":
            return "remsi" if is_signed_type(type_name) else "remui"
        if op in {"and", "bitwise and"}:
            return "andi"
        if op in {"or", "bitwise or"}:
            return "ori"
        if op == "bitwise xor":
            return "xori"
        if op == "shifted left by":
            return "shli"
        if op == "shifted right by":
            return "shrsi" if is_signed_type(type_name) else "shrui"
        raise AssertionError(op)  # pragma: no cover

    def emit_cast(self, expr: Cast, env: dict[str, EnvValue], lines: list[str], indent: str, target_type: ValueType) -> Value:
        source_expected: ValueType | None = None
        if isinstance(target_type, EnumType) and isinstance(expr.expr, Integer):
            source_expected = target_type.underlying_type
        source = self.emit_expr(expr.expr, env, lines, indent, expected=source_expected)
        source_type = source.type_name
        if source_type == target_type:
            return Value(source.name, target_type)
        if isinstance(target_type, EnumType):
            if source_type == target_type.underlying_type:
                return Value(source.name, target_type)
            raise AssertionError(f"unsupported cast {source_type} to {target_type}")
        if is_float_type(source_type) or is_float_type(target_type):
            out = Value(self.fresh(), target_type)
            if is_integer_type(source_type) and is_float_type(target_type):
                op = "sitofp" if is_signed_type(source_type) else "uitofp"
            elif is_float_type(source_type) and is_integer_type(target_type):
                op = "fptosi" if is_signed_type(target_type) else "fptoui"
            elif source_type == "f32" and target_type == "f64":
                op = "extf"
            elif source_type == "f64" and target_type == "f32":
                op = "truncf"
            else:  # pragma: no cover - semantic analysis rejects these casts
                raise AssertionError(f"unsupported cast {source_type} to {target_type}")
            lines.append(f"{indent}{out.name} = arith.{op} {source.name} : {mlir_type(source_type)} to {mlir_type(target_type)}")
            return out
        if type_width(source_type) == type_width(target_type):
            return Value(source.name, target_type)
        out = Value(self.fresh(), target_type)
        if type_width(source_type) > type_width(target_type):
            lines.append(
                f"{indent}{out.name} = arith.trunci {source.name} : {mlir_type(source_type)} to {mlir_type(target_type)}"
            )
            return out
        op = "extsi" if is_signed_type(source_type) else "extui"
        lines.append(f"{indent}{out.name} = arith.{op} {source.name} : {mlir_type(source_type)} to {mlir_type(target_type)}")
        return out

    def emit_integer(self, value: int, type_name: ValueType, lines: list[str], indent: str) -> Value:
        key: ConstantKey = ("int", value, type_name)
        cached = self.constants.get(key)
        if cached is not None:
            return cached
        out = Value(self.fresh(), type_name)
        self.constants[key] = out
        lines.append(f"{indent}{out.name} = arith.constant {value} : {mlir_type(type_name)}")
        return out

    def emit_float(self, value: float, type_name: TypeName, lines: list[str], indent: str) -> Value:
        key: ConstantKey = ("float", value, type_name)
        cached = self.constants.get(key)
        if cached is not None:
            return cached
        out = Value(self.fresh(), type_name)
        self.constants[key] = out
        lines.append(f"{indent}{out.name} = arith.constant {self.float_literal(value, type_name)} : {mlir_type(type_name)}")
        return out

    def float_literal(self, value: float, type_name: TypeName) -> str:
        if value == 0.0:
            return "0.0"
        text = format(value, ".9g") if type_name == "f32" else repr(value)
        if "e" not in text and "E" not in text and "." not in text:
            text += ".0"
        return text

    def emit_index_constant(self, value: int, lines: list[str], indent: str) -> str:
        out = self.fresh()
        lines.append(f"{indent}{out} = arith.constant {value} : index")
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

    def emit_const_value(self, value, lines: list[str], indent: str) -> Value:
        if value.type_name == "i1":
            return self.emit_boolean(bool(value.value), lines, indent)
        if is_float_type(value.type_name):
            return self.emit_float(float(value.value), value.type_name, lines, indent)
        return self.emit_integer(int(value.value), value.type_name, lines, indent)

    def emit_require(self, stmt: RequireStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        static = self.static_boolean_value(stmt.expr, env)
        if static is True:
            return
        condition = self.emit_expr(stmt.expr, env, lines, indent, expected="i1")
        self.emit_runtime_assert(condition, f"require failed at line {stmt.line}", lines, indent)

    def emit_runtime_assert(self, condition: Value, message: str, lines: list[str], indent: str) -> None:
        escaped = message.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{indent}cf.assert {condition.name}, "{escaped}"')

    def emit_index_compare(self, pred: str, left: str, right: str, lines: list[str], indent: str) -> Value:
        out = Value(self.fresh(), "i1")
        lines.append(f"{indent}{out.name} = arith.cmpi {pred}, {left}, {right} : index")
        return out

    def emit_i32_compare(self, pred: str, left: Value, right: Value, lines: list[str], indent: str) -> Value:
        out = Value(self.fresh(), "i1")
        lines.append(f"{indent}{out.name} = arith.cmpi {pred}, {left.name}, {right.name} : i32")
        return out

    def emit_storage_length_i32(
        self, storage: BufferStorage | ArrayStorage | ViewStorage, lines: list[str], indent: str
    ) -> Value:
        if isinstance(storage, BufferStorage):
            return self.emit_integer(storage.buffer_type.length, "i32", lines, indent)
        if isinstance(storage, ArrayStorage):
            return self.emit_integer(storage.array_type.length, "i32", lines, indent)
        return storage.length

    def emit_storage_length_index(
        self, storage: BufferStorage | ArrayStorage | ViewStorage, lines: list[str], indent: str
    ) -> str:
        if isinstance(storage, BufferStorage):
            return self.emit_index_constant(storage.buffer_type.length, lines, indent)
        if isinstance(storage, ArrayStorage):
            return self.emit_index_constant(storage.array_type.length, lines, indent)
        return self.emit_value_as_index(storage.length, lines, indent)

    def storage_static_length(self, storage: BufferStorage | ArrayStorage | ViewStorage) -> int | None:
        if isinstance(storage, BufferStorage):
            return storage.buffer_type.length
        if isinstance(storage, ArrayStorage):
            return storage.array_type.length
        return storage.static_length

    def emit_buffer_binding(self, stmt: BufferBinding, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        buffer_type = resolve_buffer_type(
            stmt.buffer_type, stmt.line, self.records, self.top_constants, self.functions, self.env_types(env)
        )
        buffer = BufferStorage(self.fresh(), buffer_type)
        lines.append(f"{indent}{buffer.name} = memref.alloca() : {memref_type(buffer_type)}")
        if stmt.values:
            self.emit_literal_storage_initializers(buffer, buffer_type, stmt.values, env, lines, indent)
            env[stmt.name] = buffer
            return
        assert stmt.fill is not None
        fill = self.emit_expr(stmt.fill, env, lines, indent, expected=buffer_type.element_type)
        lower = self.emit_index_constant(0, lines, indent)
        upper = self.emit_index_constant(buffer_type.length, lines, indent)
        step = self.emit_index_constant(1, lines, indent)
        iv = self.fresh()
        lines.append(f"{indent}scf.for {iv} = {lower} to {upper} step {step} {{")
        lines.append(f"{indent}  memref.store {fill.name}, {buffer.name}[{iv}] : {memref_type(buffer_type)}")
        lines.append(f"{indent}}}")
        env[stmt.name] = buffer

    def emit_array_binding(self, stmt: ArrayBinding, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        array_type = resolve_array_type(
            stmt.array_type, stmt.line, self.records, self.top_constants, self.functions, self.env_types(env)
        )
        array = ArrayStorage(self.fresh(), array_type)
        lines.append(f"{indent}{array.name} = memref.alloca() : {memref_type(array_type)}")
        if stmt.values:
            self.emit_literal_storage_initializers(array, array_type, stmt.values, env, lines, indent)
            env[stmt.name] = array
            return
        assert stmt.fill is not None
        fill = self.emit_expr(stmt.fill, env, lines, indent, expected=array_type.element_type)
        lower = self.emit_index_constant(0, lines, indent)
        upper = self.emit_index_constant(array_type.length, lines, indent)
        step = self.emit_index_constant(1, lines, indent)
        iv = self.fresh()
        lines.append(f"{indent}scf.for {iv} = {lower} to {upper} step {step} {{")
        lines.append(f"{indent}  memref.store {fill.name}, {array.name}[{iv}] : {memref_type(array_type)}")
        lines.append(f"{indent}}}")
        env[stmt.name] = array

    def emit_literal_storage_initializers(
        self,
        storage: BufferStorage | ArrayStorage,
        storage_type: BufferType | ArrayType,
        values: tuple[Expr, ...],
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
    ) -> None:
        for index, expr in enumerate(values):
            value = self.emit_expr(expr, env, lines, indent, expected=storage_type.element_type)
            index_value = self.emit_index_constant(index, lines, indent)
            lines.append(f"{indent}memref.store {value.name}, {storage.name}[{index_value}] : {memref_type(storage_type)}")

    def emit_view_binding(self, stmt: ViewBinding, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        source = self.require_indexable(env[stmt.source_name])
        start = self.emit_expr(stmt.start, env, lines, indent, expected="i32")
        count = self.emit_expr(stmt.count, env, lines, indent, expected="i32")
        self.emit_view_binding_runtime_checks(stmt, source, start, count, env, lines, indent)
        if isinstance(source, BufferStorage | ArrayStorage):
            source_type = source.buffer_type if isinstance(source, BufferStorage) else source.array_type
            base = self.emit_memref_cast_to_dynamic(source.name, memref_type(source_type), source_type.element_type, lines, indent)
            root = stmt.source_name
            static_length = self.static_integer_value(stmt.count, env)
            env[stmt.name] = ViewStorage(base, start, count, source_type.element_type, static_length, root)
            return
        combined_start = self.emit_i32_add(source.start, start, lines, indent)
        static_length = self.static_integer_value(stmt.count, env)
        env[stmt.name] = ViewStorage(source.base, combined_start, count, source.element_type, static_length, source.root)

    def emit_view_binding_runtime_checks(
        self,
        stmt: ViewBinding,
        source: BufferStorage | ArrayStorage | ViewStorage,
        start: Value,
        count: Value,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
    ) -> None:
        if not self.runtime_checks:
            return
        static_start = self.static_integer_value(stmt.start, env)
        static_count = self.static_integer_value(stmt.count, env)
        source_static_length = self.storage_static_length(source)
        if static_start is not None and static_count is not None and source_static_length is not None:
            return
        zero = self.emit_integer(0, "i32", lines, indent)
        if static_start is None:
            nonnegative_start = self.emit_i32_compare("sge", start, zero, lines, indent)
            self.emit_runtime_assert(nonnegative_start, f"view start check failed at line {stmt.line}", lines, indent)
        if static_count is None:
            nonnegative_count = self.emit_i32_compare("sge", count, zero, lines, indent)
            self.emit_runtime_assert(nonnegative_count, f"view count check failed at line {stmt.line}", lines, indent)
        length = self.emit_storage_length_i32(source, lines, indent)
        start_in_range = self.emit_i32_compare("sle", start, length, lines, indent)
        self.emit_runtime_assert(start_in_range, f"view start range check failed at line {stmt.line}", lines, indent)
        remaining = Value(self.fresh(), "i32")
        lines.append(f"{indent}{remaining.name} = arith.subi {length.name}, {start.name} : i32")
        count_in_range = self.emit_i32_compare("sle", count, remaining, lines, indent)
        self.emit_runtime_assert(count_in_range, f"view count range check failed at line {stmt.line}", lines, indent)

    def emit_memref_cast_to_dynamic(
        self,
        name: str,
        source_type: str,
        element_type: ValueType,
        lines: list[str],
        indent: str,
    ) -> str:
        target_type = dynamic_memref_type(element_type)
        if source_type == target_type:
            return name
        out = self.fresh()
        lines.append(f"{indent}{out} = memref.cast {name} : {source_type} to {target_type}")
        return out

    def emit_i32_add(self, left: Value, right: Value, lines: list[str], indent: str) -> Value:
        out = Value(self.fresh(), "i32")
        lines.append(f"{indent}{out.name} = arith.addi {left.name}, {right.name} : i32")
        return out

    def emit_buffer_load(self, expr: BufferLoad, env: dict[str, EnvValue], lines: list[str], indent: str) -> Value:
        storage = self.require_indexable(env[expr.name])
        index = self.emit_storage_index(storage, expr.index, env, lines, indent)
        element_type = self.storage_element_type(storage)
        storage_type = self.storage_mlir_type(storage)
        out = Value(self.fresh(), element_type)
        lines.append(f"{indent}{out.name} = memref.load {storage.name}[{index}] : {storage_type}")
        return out

    def emit_buffer_store(self, stmt: BufferStoreStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        storage = self.require_indexable(env[stmt.name])
        element_type = self.storage_element_type(storage)
        storage_type = self.storage_mlir_type(storage)
        value = self.emit_expr(stmt.value, env, lines, indent, expected=element_type)
        index = self.emit_storage_index(storage, stmt.index, env, lines, indent)
        lines.append(f"{indent}memref.store {value.name}, {storage.name}[{index}] : {storage_type}")

    def emit_layout_read(
        self,
        expr: LayoutRead,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        *,
        expected: RecordType,
    ) -> RecordStorage:
        record = self.records[expected.name]
        info = layout_info(record)
        buffer = self.require_indexable(env[expr.buffer_name])
        base = self.emit_storage_index(buffer, expr.index, env, lines, indent, check_width=info.size)
        fields: dict[str, Value] = {}
        for field in record.fields:
            offset = info.field_offsets[field.name]
            fields[field.name] = self.emit_layout_field_read(buffer, base, offset, field.type_name, lines, indent)
        return RecordStorage(expected, fields)

    def emit_layout_field_read(
        self,
        buffer: BufferStorage | ArrayStorage | ViewStorage,
        base: str,
        offset: int,
        type_name: ValueType,
        lines: list[str],
        indent: str,
    ) -> Value:
        width = byte_width(type_name)
        result: Value | None = None
        for byte_index in range(width):
            index_value = self.emit_index_offset(base, offset + byte_index, lines, indent)
            byte = Value(self.fresh(), "u8")
            lines.append(f"{indent}{byte.name} = memref.load {buffer.name}[{index_value}] : {self.storage_mlir_type(buffer)}")
            if width == 1:
                return Value(byte.name, type_name)
            extended = Value(self.fresh(), type_name)
            lines.append(f"{indent}{extended.name} = arith.extui {byte.name} : i8 to {mlir_type(type_name)}")
            part = extended
            if byte_index:
                shift = self.emit_integer(8 * byte_index, type_name, lines, indent)
                shifted = Value(self.fresh(), type_name)
                lines.append(f"{indent}{shifted.name} = arith.shli {extended.name}, {shift.name} : {mlir_type(type_name)}")
                part = shifted
            if result is None:
                result = part
            else:
                combined = Value(self.fresh(), type_name)
                lines.append(f"{indent}{combined.name} = arith.ori {result.name}, {part.name} : {mlir_type(type_name)}")
                result = combined
        assert result is not None
        return result

    def emit_layout_write(self, stmt: LayoutWriteStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        record = self.require_record(env[stmt.record_name])
        record_decl = self.records[record.record_type.name]
        info = layout_info(record_decl)
        buffer = self.require_indexable(env[stmt.buffer_name])
        base = self.emit_storage_index(buffer, stmt.index, env, lines, indent, check_width=info.size)
        field_bytes: dict[int, tuple[str, int]] = {}
        for field in record_decl.fields:
            field_offset = info.field_offsets[field.name]
            for byte_index in range(byte_width(field.type_name)):
                field_bytes[field_offset + byte_index] = (field.name, byte_index)
        for byte_offset in range(info.size):
            index_value = self.emit_index_offset(base, byte_offset, lines, indent)
            field_byte = field_bytes.get(byte_offset)
            if field_byte is None:
                value = self.emit_integer(0, "u8", lines, indent)
            else:
                field_name, byte_index = field_byte
                value = self.emit_layout_field_byte(record.fields[field_name], byte_index, lines, indent)
            lines.append(f"{indent}memref.store {value.name}, {buffer.name}[{index_value}] : {self.storage_mlir_type(buffer)}")

    def emit_layout_field_byte(self, value: Value, byte_index: int, lines: list[str], indent: str) -> Value:
        if byte_index == 0 and byte_width(value.type_name) == 1:
            return Value(value.name, "u8")
        source = value
        if byte_index:
            shift = self.emit_integer(8 * byte_index, value.type_name, lines, indent)
            shifted = Value(self.fresh(), value.type_name)
            lines.append(f"{indent}{shifted.name} = arith.shrui {value.name}, {shift.name} : {mlir_type(value.type_name)}")
            source = shifted
        out = Value(self.fresh(), "u8")
        lines.append(f"{indent}{out.name} = arith.trunci {source.name} : {mlir_type(source.type_name)} to i8")
        return out

    def emit_index_offset(self, base: str, offset: int, lines: list[str], indent: str) -> str:
        if offset == 0:
            return base
        offset_value = self.emit_index_constant(offset, lines, indent)
        out = self.fresh()
        lines.append(f"{indent}{out} = arith.addi {base}, {offset_value} : index")
        return out

    def emit_record_expr(
        self,
        expr: Expr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        *,
        expected: RecordType,
    ) -> RecordStorage:
        if isinstance(expr, Variable):
            source = self.require_record(env[expr.name])
            assert source.record_type == expected
            return RecordStorage(expected, dict(source.fields))
        if isinstance(expr, RecordConstructor):
            fields: dict[str, Value] = {}
            for initializer, field in zip(expr.fields, self.record_fields(expected), strict=True):
                fields[field.name] = self.emit_expr(initializer.expr, env, lines, indent, expected=field.type_name)
            return RecordStorage(expected, fields)
        if isinstance(expr, LayoutRead):
            return self.emit_layout_read(expr, env, lines, indent, expected=expected)
        if isinstance(expr, Call):
            target = self.functions[expr.name]
            assert target.return_type == expected
            args = self.emit_call_arguments(expr, target, env, lines, indent)
            fields = self.record_fields(expected)
            result_types = [field.type_name for field in fields]
            result_base = self.fresh()
            assignment = f"{result_base}:{len(fields)} = " if len(fields) > 1 else f"{result_base} = "
            arg_values = ", ".join(arg.name for arg in args)
            arg_types = ", ".join(arg.mlir_type for arg in args)
            lines.append(
                f"{indent}{assignment}func.call @{self.call_symbol(target)}({arg_values}) : ({arg_types}) -> "
                f"{self.result_type_list(result_types)}"
            )
            return RecordStorage(
                expected,
                {
                    field.name: Value(result_base if len(fields) == 1 else f"{result_base}#{index}", field.type_name)
                    for index, field in enumerate(fields)
                },
            )
        if isinstance(expr, WhenExpr):
            return self.emit_record_when_expr(expr, env, lines, indent, expected)
        if isinstance(expr, MatchExpr):
            return self.emit_record_match_expr(expr, env, lines, indent, expected)
        raise AssertionError("unsupported record expression")  # pragma: no cover

    def emit_record_when_expr(
        self,
        expr: WhenExpr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        record_type: RecordType,
    ) -> RecordStorage:
        return self.emit_record_when_cases(list(expr.cases), expr.otherwise, env, lines, indent, record_type)

    def emit_record_when_cases(
        self,
        cases: list[WhenCase],
        otherwise: Expr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        record_type: RecordType,
    ) -> RecordStorage:
        if not cases:
            return self.emit_record_expr(otherwise, env, lines, indent, expected=record_type)
        case = cases[0]
        cond = self.emit_expr(case.condition, env, lines, indent, expected="i1")
        fields = self.record_fields(record_type)
        result_types = [field.type_name for field in fields]
        result_base = self.fresh()
        assignment = f"{result_base}:{len(fields)} = " if len(fields) > 1 else f"{result_base} = "
        lines.append(f"{indent}{assignment}scf.if {cond.name} -> ({self.type_list(result_types)}) {{")
        then_holder: dict[str, RecordStorage] = {}
        self.emit_with_local_constants(
            lambda: then_holder.setdefault(
                "record",
                self.emit_record_expr(case.expr, dict(env), lines, indent + "  ", expected=record_type),
            )
        )
        then_record = then_holder["record"]
        then_values = [then_record.fields[field.name] for field in fields]
        lines.append(
            f"{indent}  scf.yield {', '.join(value.name for value in then_values)} : {self.type_list(result_types)}"
        )
        lines.append(f"{indent}}} else {{")
        else_holder: dict[str, RecordStorage] = {}
        self.emit_with_local_constants(
            lambda: else_holder.setdefault(
                "record",
                self.emit_record_when_cases(cases[1:], otherwise, dict(env), lines, indent + "  ", record_type),
            )
        )
        else_record = else_holder["record"]
        else_values = [else_record.fields[field.name] for field in fields]
        lines.append(
            f"{indent}  scf.yield {', '.join(value.name for value in else_values)} : {self.type_list(result_types)}"
        )
        lines.append(f"{indent}}}")
        return RecordStorage(
            record_type,
            {
                field.name: Value(result_base if len(fields) == 1 else f"{result_base}#{index}", field.type_name)
                for index, field in enumerate(fields)
            },
        )

    def emit_record_match_expr(
        self,
        expr: MatchExpr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        record_type: RecordType,
    ) -> RecordStorage:
        scrutinee, scrutinee_type = self.emit_match_scrutinee(expr.scrutinee, env, lines, indent)
        return self.emit_record_match_arms(
            list(expr.arms), expr.otherwise, scrutinee, scrutinee_type, env, lines, indent, record_type
        )

    def emit_record_match_arms(
        self,
        arms,
        otherwise: Expr,
        scrutinee: Value | UnionStorage,
        scrutinee_type: ValueType,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        record_type: RecordType,
    ) -> RecordStorage:
        if not arms:
            return self.emit_record_expr(otherwise, env, lines, indent, expected=record_type)
        arm = arms[0]
        cond = self.emit_match_condition(scrutinee, scrutinee_type, arm.pattern, env, lines, indent)
        fields = self.record_fields(record_type)
        result_types = [field.type_name for field in fields]
        result_base = self.fresh()
        assignment = f"{result_base}:{len(fields)} = " if len(fields) > 1 else f"{result_base} = "
        lines.append(f"{indent}{assignment}scf.if {cond.name} -> ({self.type_list(result_types)}) {{")
        then_holder: dict[str, RecordStorage] = {}
        then_env = self.env_with_union_pattern_payload(arm.pattern, scrutinee_type, scrutinee, dict(env))
        self.emit_with_local_constants(
            lambda: then_holder.setdefault(
                "record",
                self.emit_record_expr(arm.expr, then_env, lines, indent + "  ", expected=record_type),
            )
        )
        then_record = then_holder["record"]
        then_values = [then_record.fields[field.name] for field in fields]
        lines.append(
            f"{indent}  scf.yield {', '.join(value.name for value in then_values)} : {self.type_list(result_types)}"
        )
        lines.append(f"{indent}}} else {{")
        else_holder: dict[str, RecordStorage] = {}
        self.emit_with_local_constants(
            lambda: else_holder.setdefault(
                "record",
                self.emit_record_match_arms(
                    arms[1:], otherwise, scrutinee, scrutinee_type, dict(env), lines, indent + "  ", record_type
                ),
            )
        )
        else_record = else_holder["record"]
        else_values = [else_record.fields[field.name] for field in fields]
        lines.append(
            f"{indent}  scf.yield {', '.join(value.name for value in else_values)} : {self.type_list(result_types)}"
        )
        lines.append(f"{indent}}}")
        return RecordStorage(
            record_type,
            {
                field.name: Value(result_base if len(fields) == 1 else f"{result_base}#{index}", field.type_name)
                for index, field in enumerate(fields)
            },
        )

    def union_slot_types(self, union_type: UnionType) -> list[tuple[str, ValueType]]:
        union = self.unions[union_type.name]
        slots: list[tuple[str, ValueType]] = [("tag", union.tag_type)]
        for variant_name in union.variant_order:
            variant = union.variants[variant_name]
            for payload in variant.payload_fields:
                label = f"{variant.name}_{payload.name}"
                payload_type = payload.type_name
                if isinstance(payload_type, RecordType):
                    for field in self.record_fields(payload_type):
                        slots.append((f"{label}_{field.name}", field.type_name))
                else:
                    slots.append((label, payload_type))
        return slots

    def union_values(self, union: UnionStorage) -> list[Value]:
        return [union.slots[name] for name, _type_name in self.union_slot_types(union.union_type)]

    def zero_for_type(self, type_name: ValueType, lines: list[str], indent: str) -> Value:
        if type_name == "i1":
            return self.emit_boolean(False, lines, indent)
        if is_float_type(type_name):
            assert isinstance(type_name, str)
            return self.emit_float(0.0, type_name, lines, indent)
        return self.emit_integer(0, type_name, lines, indent)

    def emit_union_expr(
        self,
        expr: Expr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        *,
        expected: UnionType,
    ) -> UnionStorage:
        if isinstance(expr, Variable):
            source = self.require_union(env[expr.name])
            assert source.union_type == expected
            return UnionStorage(expected, dict(source.slots))
        if isinstance(expr, EnumCase):
            return self.emit_union_constructor(
                UnionConstructor(expr.type_name, expr.case_name, (), expr.line),
                env,
                lines,
                indent,
                expected=expected,
            )
        if isinstance(expr, UnionConstructor):
            return self.emit_union_constructor(expr, env, lines, indent, expected=expected)
        if isinstance(expr, Call):
            target = self.functions[expr.name]
            assert target.return_type == expected
            args = self.emit_call_arguments(expr, target, env, lines, indent)
            slot_types = self.union_slot_types(expected)
            result_types = [slot_type for _slot_name, slot_type in slot_types]
            result_base = self.fresh()
            assignment = f"{result_base}:{len(slot_types)} = " if len(slot_types) > 1 else f"{result_base} = "
            arg_values = ", ".join(arg.name for arg in args)
            arg_types = ", ".join(arg.mlir_type for arg in args)
            lines.append(
                f"{indent}{assignment}func.call @{self.call_symbol(target)}({arg_values}) : ({arg_types}) -> "
                f"{self.result_type_list(result_types)}"
            )
            return UnionStorage(
                expected,
                {
                    slot_name: Value(result_base if len(slot_types) == 1 else f"{result_base}#{index}", slot_type)
                    for index, (slot_name, slot_type) in enumerate(slot_types)
                },
            )
        if isinstance(expr, WhenExpr):
            return self.emit_union_when_expr(expr, env, lines, indent, expected)
        if isinstance(expr, MatchExpr):
            return self.emit_union_match_expr(expr, env, lines, indent, expected)
        raise AssertionError("unsupported union expression")  # pragma: no cover

    def emit_union_constructor(
        self,
        expr: UnionConstructor,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        *,
        expected: UnionType,
    ) -> UnionStorage:
        union = self.unions[expected.name]
        variant = union.variants[expr.variant_name]
        slots: dict[str, Value] = {}
        for slot_name, slot_type in self.union_slot_types(expected):
            slots[slot_name] = self.zero_for_type(slot_type, lines, indent)
        slots["tag"] = self.emit_integer(variant.tag, union.tag_type, lines, indent)
        for field_init, payload in zip(expr.fields, variant.payload_fields, strict=True):
            label = f"{variant.name}_{payload.name}"
            payload_type = payload.type_name
            if isinstance(payload_type, RecordType):
                record = self.emit_record_expr(field_init.expr, env, lines, indent, expected=payload_type)
                for field in self.record_fields(payload_type):
                    slots[f"{label}_{field.name}"] = record.fields[field.name]
            else:
                slots[label] = self.emit_expr(field_init.expr, env, lines, indent, expected=payload_type)
        return UnionStorage(expected, slots)

    def emit_union_when_expr(
        self,
        expr: WhenExpr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        union_type: UnionType,
    ) -> UnionStorage:
        return self.emit_union_when_cases(list(expr.cases), expr.otherwise, env, lines, indent, union_type)

    def emit_union_when_cases(
        self,
        cases: list[WhenCase],
        otherwise: Expr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        union_type: UnionType,
    ) -> UnionStorage:
        if not cases:
            return self.emit_union_expr(otherwise, env, lines, indent, expected=union_type)
        case = cases[0]
        cond = self.emit_expr(case.condition, env, lines, indent, expected="i1")
        slot_types = self.union_slot_types(union_type)
        result_types = [slot_type for _slot_name, slot_type in slot_types]
        result_base = self.fresh()
        assignment = f"{result_base}:{len(slot_types)} = " if len(slot_types) > 1 else f"{result_base} = "
        lines.append(f"{indent}{assignment}scf.if {cond.name} -> ({self.type_list(result_types)}) {{")
        then_holder: dict[str, UnionStorage] = {}
        self.emit_with_local_constants(
            lambda: then_holder.setdefault(
                "union",
                self.emit_union_expr(case.expr, dict(env), lines, indent + "  ", expected=union_type),
            )
        )
        then_union = then_holder["union"]
        then_values = self.union_values(then_union)
        lines.append(f"{indent}  scf.yield {', '.join(value.name for value in then_values)} : {self.type_list(result_types)}")
        lines.append(f"{indent}}} else {{")
        else_holder: dict[str, UnionStorage] = {}
        self.emit_with_local_constants(
            lambda: else_holder.setdefault(
                "union",
                self.emit_union_when_cases(cases[1:], otherwise, dict(env), lines, indent + "  ", union_type),
            )
        )
        else_union = else_holder["union"]
        else_values = self.union_values(else_union)
        lines.append(f"{indent}  scf.yield {', '.join(value.name for value in else_values)} : {self.type_list(result_types)}")
        lines.append(f"{indent}}}")
        return UnionStorage(
            union_type,
            {
                slot_name: Value(result_base if len(slot_types) == 1 else f"{result_base}#{index}", slot_type)
                for index, (slot_name, slot_type) in enumerate(slot_types)
            },
        )

    def emit_union_match_expr(
        self,
        expr: MatchExpr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        union_type: UnionType,
    ) -> UnionStorage:
        scrutinee, scrutinee_type = self.emit_match_scrutinee(expr.scrutinee, env, lines, indent)
        return self.emit_union_match_arms(
            list(expr.arms), expr.otherwise, scrutinee, scrutinee_type, env, lines, indent, union_type
        )

    def emit_union_match_arms(
        self,
        arms,
        otherwise: Expr,
        scrutinee: Value | UnionStorage,
        scrutinee_type: ValueType,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        union_type: UnionType,
    ) -> UnionStorage:
        if not arms:
            return self.emit_union_expr(otherwise, env, lines, indent, expected=union_type)
        arm = arms[0]
        cond = self.emit_match_condition(scrutinee, scrutinee_type, arm.pattern, env, lines, indent)
        slot_types = self.union_slot_types(union_type)
        result_types = [slot_type for _slot_name, slot_type in slot_types]
        result_base = self.fresh()
        assignment = f"{result_base}:{len(slot_types)} = " if len(slot_types) > 1 else f"{result_base} = "
        lines.append(f"{indent}{assignment}scf.if {cond.name} -> ({self.type_list(result_types)}) {{")
        then_env = self.env_with_union_pattern_payload(arm.pattern, scrutinee_type, scrutinee, dict(env))
        then_holder: dict[str, UnionStorage] = {}
        self.emit_with_local_constants(
            lambda: then_holder.setdefault(
                "union",
                self.emit_union_expr(arm.expr, then_env, lines, indent + "  ", expected=union_type),
            )
        )
        then_union = then_holder["union"]
        then_values = self.union_values(then_union)
        lines.append(f"{indent}  scf.yield {', '.join(value.name for value in then_values)} : {self.type_list(result_types)}")
        lines.append(f"{indent}}} else {{")
        else_holder: dict[str, UnionStorage] = {}
        self.emit_with_local_constants(
            lambda: else_holder.setdefault(
                "union",
                self.emit_union_match_arms(
                    arms[1:], otherwise, scrutinee, scrutinee_type, dict(env), lines, indent + "  ", union_type
                ),
            )
        )
        else_union = else_holder["union"]
        else_values = self.union_values(else_union)
        lines.append(f"{indent}  scf.yield {', '.join(value.name for value in else_values)} : {self.type_list(result_types)}")
        lines.append(f"{indent}}}")
        return UnionStorage(
            union_type,
            {
                slot_name: Value(result_base if len(slot_types) == 1 else f"{result_base}#{index}", slot_type)
                for index, (slot_name, slot_type) in enumerate(slot_types)
            },
        )

    def emit_field_assign(self, stmt: FieldAssignStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        record = self.require_record(env[stmt.name])
        current = record.fields[stmt.field]
        updated = self.emit_expr(stmt.expr, env, lines, indent, expected=current.type_name)
        new_fields = dict(record.fields)
        new_fields[stmt.field] = updated
        env[stmt.name] = RecordStorage(record.record_type, new_fields)

    def emit_call_stmt(self, stmt: CallStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        target = self.functions[stmt.call.name]
        args = self.emit_call_arguments(stmt.call, target, env, lines, indent)
        arg_values = ", ".join(arg.name for arg in args)
        arg_types = ", ".join(arg.mlir_type for arg in args)
        lines.append(f"{indent}func.call @{self.call_symbol(target)}({arg_values}) : ({arg_types}) -> ()")

    def emit_call_arguments(
        self,
        call: Call,
        target: Function,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
    ) -> list[CallArg]:
        args: list[CallArg] = []
        for arg, param in zip(call.args, target.params, strict=True):
            if isinstance(param.type_name, BufferType):
                assert isinstance(arg, Variable)
                buffer = self.require_buffer(env[arg.name])
                args.append(CallArg(buffer.name, memref_type(buffer.buffer_type)))
            elif isinstance(param.type_name, ViewType):
                assert isinstance(arg, Variable)
                storage = self.require_indexable(env[arg.name])
                view = self.as_view_call_storage(storage, lines, indent)
                args.append(CallArg(view.base, dynamic_memref_type(view.element_type)))
                args.append(CallArg(view.start.name, mlir_type(view.start.type_name)))
                args.append(CallArg(view.length.name, mlir_type(view.length.type_name)))
            elif isinstance(param.type_name, RecordType):
                assert isinstance(arg, Variable)
                record = self.require_record(env[arg.name])
                for field in self.record_fields(param.type_name):
                    value = record.fields[field.name]
                    args.append(CallArg(value.name, mlir_type(value.type_name)))
            elif isinstance(param.type_name, UnionType):
                union = self.emit_union_expr(arg, env, lines, indent, expected=param.type_name)
                for value in self.union_values(union):
                    args.append(CallArg(value.name, mlir_type(value.type_name)))
            else:
                value = self.emit_expr(arg, env, lines, indent, expected=param.type_name)
                args.append(CallArg(value.name, mlir_type(value.type_name)))
        return args

    def emit_index(self, expr: Expr, env: dict[str, EnvValue], lines: list[str], indent: str) -> str:
        if isinstance(expr, Integer):
            return self.emit_index_constant(expr.value, lines, indent)
        value = self.emit_expr(expr, env, lines, indent)
        out = self.fresh()
        op = "index_cast" if is_signed_type(value.type_name) else "index_castui"
        lines.append(f"{indent}{out} = arith.{op} {value.name} : {mlir_type(value.type_name)} to index")
        return out

    def emit_storage_index(
        self,
        storage: BufferStorage | ArrayStorage | ViewStorage,
        index_expr: Expr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        *,
        check_width: int = 1,
    ) -> str:
        static_index = self.static_integer_value(index_expr, env)
        if self.runtime_checks and static_index is None:
            index_value = self.emit_expr(index_expr, env, lines, indent)
            index = self.emit_value_as_index(index_value, lines, indent)
            self.emit_storage_index_runtime_checks(storage, index, index_value, check_width, getattr(index_expr, "line", 0), lines, indent)
        else:
            index = self.emit_index(index_expr, env, lines, indent)
        if isinstance(storage, BufferStorage | ArrayStorage):
            return index
        start = self.emit_value_as_index(storage.start, lines, indent)
        out = self.fresh()
        lines.append(f"{indent}{out} = arith.addi {start}, {index} : index")
        return out

    def emit_storage_index_runtime_checks(
        self,
        storage: BufferStorage | ArrayStorage | ViewStorage,
        index: str,
        index_value: Value,
        check_width: int,
        line: int,
        lines: list[str],
        indent: str,
    ) -> None:
        if is_signed_type(index_value.type_name):
            zero = self.emit_index_constant(0, lines, indent)
            nonnegative = self.emit_index_compare("sge", index, zero, lines, indent)
            self.emit_runtime_assert(nonnegative, f"storage lower-bound check failed at line {line}", lines, indent)
        length = self.emit_storage_length_index(storage, lines, indent)
        if check_width == 1:
            in_range = self.emit_index_compare("slt", index, length, lines, indent)
            self.emit_runtime_assert(in_range, f"storage upper-bound check failed at line {line}", lines, indent)
            return
        width = self.emit_index_constant(check_width, lines, indent)
        max_start = self.fresh()
        lines.append(f"{indent}{max_start} = arith.subi {length}, {width} : index")
        in_range = self.emit_index_compare("sle", index, max_start, lines, indent)
        self.emit_runtime_assert(in_range, f"storage range check failed at line {line}", lines, indent)

    def emit_value_as_index(self, value: Value, lines: list[str], indent: str) -> str:
        out = self.fresh()
        op = "index_cast" if is_signed_type(value.type_name) else "index_castui"
        lines.append(f"{indent}{out} = arith.{op} {value.name} : {mlir_type(value.type_name)} to index")
        return out

    def as_view_call_storage(self, storage: BufferStorage | ArrayStorage | ViewStorage, lines: list[str], indent: str) -> ViewStorage:
        if isinstance(storage, ViewStorage):
            return storage
        storage_type = storage.buffer_type if isinstance(storage, BufferStorage) else storage.array_type
        base = self.emit_memref_cast_to_dynamic(storage.name, memref_type(storage_type), storage_type.element_type, lines, indent)
        start = self.emit_integer(0, "i32", lines, indent)
        length = self.emit_integer(storage_type.length, "i32", lines, indent)
        return ViewStorage(base, start, length, storage_type.element_type, storage_type.length, storage.name)

    def static_integer_value(self, expr: Expr, env: dict[str, EnvValue]) -> int | None:
        try:
            value = evaluate_const_expr(expr, self.env_types(env), self.functions, self.records, self.top_constants)
        except (CompileTimeEvaluationError, Exception):
            return None
        if value.type_name == "i1":
            return None
        return int(value.value)

    def static_boolean_value(self, expr: Expr, env: dict[str, EnvValue]) -> bool | None:
        try:
            value = evaluate_const_expr(
                expr, self.env_types(env), self.functions, self.records, self.top_constants, expected="i1"
            )
        except (CompileTimeEvaluationError, Exception):
            return None
        if value.type_name != "i1":
            return None
        return bool(value.value)

    def emit_index_to_integer(self, index_value: str, type_name: TypeName, lines: list[str], indent: str) -> Value:
        out = Value(self.fresh(), type_name)
        op = "index_cast" if is_signed_type(type_name) else "index_castui"
        lines.append(f"{indent}{out.name} = arith.{op} {index_value} : index to {mlir_type(type_name)}")
        return out

    def emit_when_expr(
        self, expr: WhenExpr, env: dict[str, EnvValue], lines: list[str], indent: str, type_name: ValueType
    ) -> Value:
        return self.emit_when_cases(list(expr.cases), expr.otherwise, env, lines, indent, type_name)

    def emit_when_cases(
        self,
        cases: list[WhenCase],
        otherwise: Expr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        type_name: ValueType,
    ) -> Value:
        if not cases:
            return self.emit_expr(otherwise, env, lines, indent, expected=type_name)
        case = cases[0]
        cond = self.emit_expr(case.condition, env, lines, indent, expected="i1")
        result = Value(self.fresh(), type_name)
        mlir_result_type = mlir_type(type_name)
        lines.append(f"{indent}{result.name} = scf.if {cond.name} -> ({mlir_result_type}) {{")
        then_value = self.emit_expr(case.expr, dict(env), lines, indent + "  ", expected=type_name)
        lines.append(f"{indent}  scf.yield {then_value.name} : {mlir_result_type}")
        lines.append(f"{indent}}} else {{")
        else_value = self.emit_when_cases(cases[1:], otherwise, dict(env), lines, indent + "  ", type_name)
        lines.append(f"{indent}  scf.yield {else_value.name} : {mlir_result_type}")
        lines.append(f"{indent}}}")
        return result

    def emit_match_expr(
        self,
        expr: MatchExpr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        type_name: ValueType,
    ) -> Value:
        scrutinee, scrutinee_type = self.emit_match_scrutinee(expr.scrutinee, env, lines, indent)
        return self.emit_match_expr_arms(list(expr.arms), expr.otherwise, scrutinee, scrutinee_type, env, lines, indent, type_name)

    def emit_match_expr_arms(
        self,
        arms,
        otherwise: Expr,
        scrutinee: Value | UnionStorage,
        scrutinee_type: ValueType,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        type_name: ValueType,
    ) -> Value:
        if not arms:
            return self.emit_expr(otherwise, env, lines, indent, expected=type_name)
        arm = arms[0]
        cond = self.emit_match_condition(scrutinee, scrutinee_type, arm.pattern, env, lines, indent)
        result = Value(self.fresh(), type_name)
        mlir_result_type = mlir_type(type_name)
        lines.append(f"{indent}{result.name} = scf.if {cond.name} -> ({mlir_result_type}) {{")
        then_holder: dict[str, Value] = {}
        self.emit_with_local_constants(
            lambda: then_holder.setdefault(
                "value",
                self.emit_expr(
                    arm.expr,
                    self.env_with_union_pattern_payload(arm.pattern, scrutinee_type, scrutinee, dict(env)),
                    lines,
                    indent + "  ",
                    expected=type_name,
                ),
            )
        )
        lines.append(f"{indent}  scf.yield {then_holder['value'].name} : {mlir_result_type}")
        lines.append(f"{indent}}} else {{")
        else_holder: dict[str, Value] = {}
        self.emit_with_local_constants(
            lambda: else_holder.setdefault(
                "value",
                self.emit_match_expr_arms(arms[1:], otherwise, scrutinee, scrutinee_type, dict(env), lines, indent + "  ", type_name),
            )
        )
        lines.append(f"{indent}  scf.yield {else_holder['value'].name} : {mlir_result_type}")
        lines.append(f"{indent}}}")
        return result

    def emit_match_condition(
        self,
        scrutinee: Value | UnionStorage,
        scrutinee_type: ValueType,
        pattern: Expr | UnionPattern,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
    ) -> Value:
        if isinstance(scrutinee_type, UnionType):
            assert isinstance(scrutinee, UnionStorage)
            union = self.unions[scrutinee_type.name]
            if isinstance(pattern, UnionPattern):
                variant_name = pattern.variant_name
            elif isinstance(pattern, EnumCase):
                variant_name = pattern.case_name
            else:  # pragma: no cover - semantic analysis rejects these patterns
                raise AssertionError("invalid union match pattern")
            variant = union.variants[variant_name]
            pattern_value = self.emit_integer(variant.tag, union.tag_type, lines, indent)
            out = Value(self.fresh(), "i1")
            tag = scrutinee.slots["tag"]
            lines.append(f"{indent}{out.name} = arith.cmpi eq, {tag.name}, {pattern_value.name} : {mlir_type(tag.type_name)}")
            return out
        assert isinstance(scrutinee, Value)
        pattern_value = self.emit_expr(pattern, env, lines, indent, expected=scrutinee_type)
        out = Value(self.fresh(), "i1")
        lines.append(
            f"{indent}{out.name} = arith.cmpi eq, {scrutinee.name}, {pattern_value.name} : {mlir_type(scrutinee_type)}"
        )
        return out

    def emit_match_scrutinee(
        self,
        expr: Expr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
    ) -> tuple[Value | UnionStorage, ValueType]:
        env_types = self.env_types(env)
        scrutinee_type = infer_expr_type(expr, env_types, self.functions, self.records, constants=self.top_constants)
        if isinstance(scrutinee_type, UnionType):
            return self.emit_union_expr(expr, env, lines, indent, expected=scrutinee_type), scrutinee_type
        return self.emit_expr(expr, env, lines, indent, expected=scrutinee_type), scrutinee_type

    def env_with_union_pattern_payload(
        self,
        pattern: Expr | UnionPattern,
        scrutinee_type: ValueType,
        scrutinee: Value | UnionStorage,
        env: dict[str, EnvValue],
    ) -> dict[str, EnvValue]:
        if not isinstance(scrutinee_type, UnionType) or not isinstance(pattern, UnionPattern):
            return env
        assert isinstance(scrutinee, UnionStorage)
        union = self.unions[scrutinee_type.name]
        variant = union.variants[pattern.variant_name]
        if not variant.payload_fields:
            return env
        for binding, payload in zip(pattern.bindings, variant.payload_fields, strict=True):
            binding_name = binding.alias_name or binding.field_name
            payload_type = payload.type_name
            label = f"{variant.name}_{payload.name}"
            if isinstance(payload_type, RecordType):
                fields = {
                    field.name: scrutinee.slots[f"{label}_{field.name}"]
                    for field in self.record_fields(payload_type)
                }
                env[binding_name] = RecordStorage(payload_type, fields)
            else:
                env[binding_name] = scrutinee.slots[label]
        return env

    def emit_comparison(self, condition: Comparison, env: dict[str, EnvValue], lines: list[str], indent: str) -> Value:
        env_types = self.env_types(env)
        type_name = infer_comparison_operand_type(condition, env_types, self.functions, self.records)
        left = self.emit_expr(condition.left, env, lines, indent, expected=type_name)
        right = self.emit_expr(condition.right, env, lines, indent, expected=type_name)
        out = Value(self.fresh(), "i1")
        pred = self.comparison_predicate(condition.pred, type_name)
        op = "cmpf" if is_float_type(type_name) else "cmpi"
        lines.append(f"{indent}{out.name} = arith.{op} {pred}, {left.name}, {right.name} : {mlir_type(type_name)}")
        return out

    def comparison_predicate(self, pred: str, type_name: ValueType) -> str:
        if is_float_type(type_name):
            return {"eq": "oeq", "ne": "one", "slt": "olt", "sle": "ole", "sgt": "ogt", "sge": "oge"}[pred]
        if pred in {"eq", "ne"} or is_signed_type(type_name):
            return pred
        return {"slt": "ult", "sle": "ule", "sgt": "ugt", "sge": "uge"}[pred]

    def emit_while(self, stmt: WhileStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        loop_id = self.while_counter
        self.while_counter += 1
        arg_suffix = "" if self.while_depth == 0 else f"_loop{loop_id}"
        visible_binding_order = list(self.binding_order)
        visible_record_order = list(self.record_order)
        visible_union_order = list(self.union_order)
        carried_slots = self.assigned_binding_slots(stmt.body, visible_binding_order, visible_record_order, env, visible_union_order)
        carried_values = [self.slot_value(env, slot) for slot in carried_slots]
        carried_types = [value.type_name for value in carried_values]
        result_base = self.fresh() if carried_slots else None
        initial_operands = ", ".join(
            f"%{slot.label}_before{arg_suffix} = {value.name}"
            for slot, value in zip(carried_slots, carried_values, strict=True)
        )
        input_types = self.type_list(carried_types)
        result_types = self.result_type_list(carried_types)
        if carried_slots:
            assignment = f"{result_base}:{len(carried_slots)} = " if len(carried_slots) > 1 else f"{result_base} = "
            lines.append(f"{indent}{assignment}scf.while ({initial_operands}) : ({input_types}) -> {result_types} {{")
        else:
            lines.append(f"{indent}scf.while : () -> () {{")

        before_env = dict(env)
        for slot, type_name in zip(carried_slots, carried_types, strict=True):
            self.set_slot_value(before_env, slot, Value(f"%{slot.label}_before{arg_suffix}", type_name))
        self.emit_with_local_constants(lambda: self.emit_while_before(stmt, before_env, carried_slots, carried_types, lines, indent))

        lines.append(f"{indent}}} do {{")
        if carried_slots:
            body_args = ", ".join(
                f"%{slot.label}_body{arg_suffix}: {mlir_type(type_name)}"
                for slot, type_name in zip(carried_slots, carried_types, strict=True)
            )
            lines.append(f"{indent}^bb0({body_args}):")
        body_env = dict(env)
        for slot, type_name in zip(carried_slots, carried_types, strict=True):
            self.set_slot_value(body_env, slot, Value(f"%{slot.label}_body{arg_suffix}", type_name))

        saved_while_depth = self.while_depth
        self.while_depth += 1
        try:
            self.emit_with_local_constants(
                lambda: self.emit_with_binding_scope(
                    lambda: self.emit_while_body(stmt, body_env, carried_slots, carried_types, lines, indent)
                )
            )
        finally:
            self.while_depth = saved_while_depth
        lines.append(f"{indent}}}")

        if result_base is not None:
            for index, (slot, type_name) in enumerate(zip(carried_slots, carried_types, strict=True)):
                result_name = result_base if len(carried_slots) == 1 else f"{result_base}#{index}"
                self.set_slot_value(env, slot, Value(result_name, type_name))

    def emit_while_before(
        self,
        stmt: WhileStmt,
        env: dict[str, EnvValue],
        carried_slots: list[CarrySlot],
        carried_types: list[ValueType],
        lines: list[str],
        indent: str,
    ) -> None:
        cond = self.emit_expr(stmt.condition, env, lines, indent + "  ", expected="i1")
        if carried_slots:
            forwarded = ", ".join(self.slot_value(env, slot).name for slot in carried_slots)
            lines.append(f"{indent}  scf.condition({cond.name}) {forwarded} : {self.type_list(carried_types)}")
        else:
            lines.append(f"{indent}  scf.condition({cond.name})")

    def emit_while_body(
        self,
        stmt: WhileStmt,
        env: dict[str, EnvValue],
        carried_slots: list[CarrySlot],
        carried_types: list[ValueType],
        lines: list[str],
        indent: str,
    ) -> None:
        for body_stmt in stmt.body:
            self.emit_body_stmt(body_stmt, env, lines, indent + "  ")
        if carried_slots:
            yielded = ", ".join(self.slot_value(env, slot).name for slot in carried_slots)
            lines.append(f"{indent}  scf.yield {yielded} : {self.type_list(carried_types)}")
        else:
            lines.append(f"{indent}  scf.yield")

    def emit_for(self, stmt: ForStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        loop_id = self.for_counter
        self.for_counter += 1
        arg_suffix = "" if self.for_depth == 0 else f"_for{loop_id}"
        env_types = self.env_types(env)
        loop_type = infer_expr_type(stmt.start, env_types, self.functions, self.records, constants=self.top_constants)
        assert not isinstance(loop_type, BufferType | ArrayType | RecordType | UnionType)
        start = self.emit_index(stmt.start, env, lines, indent)
        end = self.emit_index(stmt.end, env, lines, indent)
        step = self.emit_index_constant(stmt.step, lines, indent)
        iv = self.fresh()

        visible_binding_order = list(self.binding_order)
        visible_record_order = list(self.record_order)
        visible_union_order = list(self.union_order)
        carried_slots = self.assigned_binding_slots(stmt.body, visible_binding_order, visible_record_order, env, visible_union_order)
        carried_values = [self.slot_value(env, slot) for slot in carried_slots]
        carried_types = [value.type_name for value in carried_values]
        result_base = self.fresh() if carried_slots else None
        iter_args = ", ".join(
            f"%{slot.label}_iter{arg_suffix} = {value.name}"
            for slot, value in zip(carried_slots, carried_values, strict=True)
        )

        if carried_slots:
            assignment = f"{result_base}:{len(carried_slots)} = " if len(carried_slots) > 1 else f"{result_base} = "
            lines.append(
                f"{indent}{assignment}scf.for {iv} = {start} to {end} step {step} "
                f"iter_args({iter_args}) -> ({self.type_list(carried_types)}) {{"
            )
        else:
            lines.append(f"{indent}scf.for {iv} = {start} to {end} step {step} {{")

        body_env = dict(env)
        for slot, type_name in zip(carried_slots, carried_types, strict=True):
            self.set_slot_value(body_env, slot, Value(f"%{slot.label}_iter{arg_suffix}", type_name))

        saved_for_depth = self.for_depth
        self.for_depth += 1
        try:
            self.emit_with_local_constants(
                lambda: self.emit_with_binding_scope(
                    lambda: self.emit_for_body(stmt.name, loop_type, stmt.body, body_env, carried_slots, carried_types, iv, lines, indent)
                )
            )
        finally:
            self.for_depth = saved_for_depth

        lines.append(f"{indent}}}")

        if result_base is not None:
            for index, (slot, type_name) in enumerate(zip(carried_slots, carried_types, strict=True)):
                result_name = result_base if len(carried_slots) == 1 else f"{result_base}#{index}"
                self.set_slot_value(env, slot, Value(result_name, type_name))

    def emit_for_each(self, stmt: ForEachStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        storage = self.require_indexable(env[stmt.buffer_name])
        lower = self.emit_index_constant(0, lines, indent)
        if isinstance(storage, BufferStorage):
            upper = self.emit_index_constant(storage.buffer_type.length, lines, indent)
        elif isinstance(storage, ArrayStorage):
            upper = self.emit_index_constant(storage.array_type.length, lines, indent)
        else:
            upper = self.emit_value_as_index(storage.length, lines, indent)
        step = self.emit_index_constant(1, lines, indent)
        iv = self.fresh()

        loop_id = self.for_counter
        self.for_counter += 1
        arg_suffix = "" if self.for_depth == 0 else f"_for{loop_id}"
        visible_binding_order = list(self.binding_order)
        visible_record_order = list(self.record_order)
        visible_union_order = list(self.union_order)
        carried_slots = self.assigned_binding_slots(stmt.body, visible_binding_order, visible_record_order, env, visible_union_order)
        carried_values = [self.slot_value(env, slot) for slot in carried_slots]
        carried_types = [value.type_name for value in carried_values]
        result_base = self.fresh() if carried_slots else None
        iter_args = ", ".join(
            f"%{slot.label}_iter{arg_suffix} = {value.name}"
            for slot, value in zip(carried_slots, carried_values, strict=True)
        )

        if carried_slots:
            assignment = f"{result_base}:{len(carried_slots)} = " if len(carried_slots) > 1 else f"{result_base} = "
            lines.append(
                f"{indent}{assignment}scf.for {iv} = {lower} to {upper} step {step} "
                f"iter_args({iter_args}) -> ({self.type_list(carried_types)}) {{"
            )
        else:
            lines.append(f"{indent}scf.for {iv} = {lower} to {upper} step {step} {{")

        body_env = dict(env)
        for slot, type_name in zip(carried_slots, carried_types, strict=True):
            self.set_slot_value(body_env, slot, Value(f"%{slot.label}_iter{arg_suffix}", type_name))

        saved_for_depth = self.for_depth
        self.for_depth += 1
        try:
            self.emit_with_local_constants(
                lambda: self.emit_with_binding_scope(
                    lambda: self.emit_for_body(stmt.name, "i32", stmt.body, body_env, carried_slots, carried_types, iv, lines, indent)
                )
            )
        finally:
            self.for_depth = saved_for_depth

        lines.append(f"{indent}}}")

        if result_base is not None:
            for index, (slot, type_name) in enumerate(zip(carried_slots, carried_types, strict=True)):
                result_name = result_base if len(carried_slots) == 1 else f"{result_base}#{index}"
                self.set_slot_value(env, slot, Value(result_name, type_name))

    def emit_for_body(
        self,
        name: str,
        loop_type: TypeName,
        body: tuple[BodyStmt, ...],
        env: dict[str, EnvValue],
        carried_slots: list[CarrySlot],
        carried_types: list[ValueType],
        iv: str,
        lines: list[str],
        indent: str,
    ) -> None:
        body_indent = indent + "  "
        env[name] = self.emit_index_to_integer(iv, loop_type, lines, body_indent)
        self.binding_order.append(name)
        for body_stmt in body:
            self.emit_body_stmt(body_stmt, env, lines, body_indent)
        if carried_slots:
            yielded = ", ".join(self.slot_value(env, slot).name for slot in carried_slots)
            lines.append(f"{body_indent}scf.yield {yielded} : {self.type_list(carried_types)}")

    def emit_if(self, stmt: IfStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        visible_binding_order = list(self.binding_order)
        visible_record_order = list(self.record_order)
        visible_union_order = list(self.union_order)
        result_slots = self.assigned_binding_slots((*stmt.then_body, *stmt.else_body), visible_binding_order, visible_record_order, env, visible_union_order)
        result_values = [self.slot_value(env, slot) for slot in result_slots]
        result_types = [value.type_name for value in result_values]

        cond = self.emit_expr(stmt.condition, env, lines, indent, expected="i1")
        result_base = self.fresh() if result_slots else None
        if result_slots:
            assignment = f"{result_base}:{len(result_slots)} = " if len(result_slots) > 1 else f"{result_base} = "
            lines.append(f"{indent}{assignment}scf.if {cond.name} -> ({self.type_list(result_types)}) {{")
        else:
            lines.append(f"{indent}scf.if {cond.name} {{")

        then_env = dict(env)
        self.emit_with_local_constants(
            lambda: self.emit_with_binding_scope(
                lambda: self.emit_if_branch(stmt.then_body, then_env, result_slots, result_types, lines, indent)
            )
        )
        lines.append(f"{indent}}} else {{")
        else_env = dict(env)
        self.emit_with_local_constants(
            lambda: self.emit_with_binding_scope(
                lambda: self.emit_if_branch(stmt.else_body, else_env, result_slots, result_types, lines, indent)
            )
        )
        lines.append(f"{indent}}}")

        if result_base is not None:
            for index, (slot, type_name) in enumerate(zip(result_slots, result_types, strict=True)):
                result_name = result_base if len(result_slots) == 1 else f"{result_base}#{index}"
                self.set_slot_value(env, slot, Value(result_name, type_name))

    def emit_if_branch(
        self,
        body: tuple[BodyStmt, ...],
        env: dict[str, EnvValue],
        result_slots: list[CarrySlot],
        result_types: list[ValueType],
        lines: list[str],
        indent: str,
    ) -> None:
        branch_indent = indent + "  "
        for body_stmt in body:
            self.emit_body_stmt(body_stmt, env, lines, branch_indent)
        if result_slots:
            yielded = ", ".join(self.slot_value(env, slot).name for slot in result_slots)
            lines.append(f"{branch_indent}scf.yield {yielded} : {self.type_list(result_types)}")
        else:
            lines.append(f"{branch_indent}scf.yield")

    def emit_match_step(self, stmt: MatchStep, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        visible_binding_order = list(self.binding_order)
        visible_record_order = list(self.record_order)
        visible_union_order = list(self.union_order)
        all_bodies = tuple(body_stmt for arm in stmt.arms for body_stmt in arm.body) + tuple(stmt.otherwise_body)
        result_slots = self.assigned_binding_slots(all_bodies, visible_binding_order, visible_record_order, env, visible_union_order)
        result_values = [self.slot_value(env, slot) for slot in result_slots]
        result_types = [value.type_name for value in result_values]

        scrutinee, scrutinee_type = self.emit_match_scrutinee(stmt.scrutinee, env, lines, indent)
        result_base = self.fresh() if result_slots else None
        self.emit_match_step_arms(
            list(stmt.arms),
            stmt.otherwise_body,
            scrutinee,
            scrutinee_type,
            env,
            result_slots,
            result_types,
            lines,
            indent,
            result_base,
        )

    def emit_match_step_arms(
        self,
        arms,
        otherwise_body: tuple[BodyStmt, ...],
        scrutinee: Value | UnionStorage,
        scrutinee_type: ValueType,
        env: dict[str, EnvValue],
        result_slots: list[CarrySlot],
        result_types: list[ValueType],
        lines: list[str],
        indent: str,
        result_base: str | None = None,
    ) -> None:
        if not arms:
            for body_stmt in otherwise_body:
                self.emit_body_stmt(body_stmt, env, lines, indent)
            return

        arm = arms[0]
        cond = self.emit_match_condition(scrutinee, scrutinee_type, arm.pattern, env, lines, indent)
        if result_slots:
            prefix = ""
            if result_base is not None:
                prefix = f"{result_base}:{len(result_slots)} = " if len(result_slots) > 1 else f"{result_base} = "
            lines.append(f"{indent}{prefix}scf.if {cond.name} -> ({self.type_list(result_types)}) {{")
        else:
            lines.append(f"{indent}scf.if {cond.name} {{")

        then_env = self.env_with_union_pattern_payload(arm.pattern, scrutinee_type, scrutinee, dict(env))
        self.emit_with_local_constants(
            lambda: self.emit_with_binding_scope(
                lambda: self.emit_if_branch(arm.body, then_env, result_slots, result_types, lines, indent)
            )
        )
        lines.append(f"{indent}}} else {{")
        else_env = dict(env)
        self.emit_with_local_constants(
            lambda: self.emit_with_binding_scope(
                lambda: self.emit_match_step_else_branch(
                    arms[1:],
                    otherwise_body,
                    scrutinee,
                    scrutinee_type,
                    else_env,
                    result_slots,
                    result_types,
                    lines,
                    indent + "  ",
                )
            )
        )
        lines.append(f"{indent}}}")
        if result_base is not None:
            for index, (slot, type_name) in enumerate(zip(result_slots, result_types, strict=True)):
                result_name = result_base if len(result_slots) == 1 else f"{result_base}#{index}"
                self.set_slot_value(env, slot, Value(result_name, type_name))

    def emit_match_step_else_branch(
        self,
        arms,
        otherwise_body: tuple[BodyStmt, ...],
        scrutinee: Value | UnionStorage,
        scrutinee_type: ValueType,
        env: dict[str, EnvValue],
        result_slots: list[CarrySlot],
        result_types: list[ValueType],
        lines: list[str],
        indent: str,
    ) -> None:
        if not arms:
            self.emit_if_branch(otherwise_body, env, result_slots, result_types, lines, indent[:-2] if indent.endswith("  ") else indent)
            return
        nested_base = self.fresh() if result_slots else None
        self.emit_match_step_arms(
            arms,
            otherwise_body,
            scrutinee,
            scrutinee_type,
            env,
            result_slots,
            result_types,
            lines,
            indent,
            nested_base,
        )
        if result_slots:
            yielded = ", ".join(self.slot_value(env, slot).name for slot in result_slots)
            lines.append(f"{indent}scf.yield {yielded} : {self.type_list(result_types)}")
        else:
            lines.append(f"{indent}scf.yield")

    def emit_with_local_constants(self, emit: Callable[[], None]) -> None:
        saved = self.constants
        self.constants = {}
        try:
            emit()
        finally:
            self.constants = saved

    def emit_with_binding_scope(self, emit: Callable[[], None]) -> None:
        saved_binding_order = list(self.binding_order)
        saved_record_order = list(self.record_order)
        saved_union_order = list(self.union_order)
        try:
            emit()
        finally:
            self.binding_order = saved_binding_order
            self.record_order = saved_record_order
            self.union_order = saved_union_order

    def assigned_binding_slots(
        self,
        body: tuple[BodyStmt, ...],
        visible_binding_order: list[str],
        visible_record_order: list[str],
        env: dict[str, EnvValue],
        visible_union_order: list[str],
    ) -> list[CarrySlot]:
        visible_scalars = set(visible_binding_order)
        visible_records = set(visible_record_order)
        visible_unions = set(visible_union_order)
        assigned_scalars: set[str] = set()
        assigned_record_fields: set[tuple[str, str]] = set()
        assigned_unions: set[str] = set()

        def mark_record(name: str) -> None:
            if name not in visible_records:
                return
            record = self.require_record(env[name])
            for field in self.record_fields(record.record_type):
                assigned_record_fields.add((name, field.name))

        def visit(statements: tuple[BodyStmt, ...]) -> None:
            for statement in statements:
                if isinstance(statement, AssignStmt):
                    if statement.name in visible_scalars:
                        assigned_scalars.add(statement.name)
                    elif statement.name in visible_records:
                        mark_record(statement.name)
                    elif statement.name in visible_unions:
                        assigned_unions.add(statement.name)
                elif isinstance(statement, FieldAssignStmt):
                    if statement.name in visible_records:
                        assigned_record_fields.add((statement.name, statement.field))
                elif isinstance(statement, WhileStmt):
                    visit(statement.body)
                elif isinstance(statement, ForStmt):
                    visit(statement.body)
                elif isinstance(statement, ForEachStmt):
                    visit(statement.body)
                elif isinstance(statement, IfStmt):
                    visit(statement.then_body)
                    visit(statement.else_body)
                elif isinstance(statement, MatchStep):
                    for arm in statement.arms:
                        visit(arm.body)
                    visit(statement.otherwise_body)

        visit(body)
        slots: list[CarrySlot] = []
        for name in visible_binding_order:
            if name in assigned_scalars:
                slots.append(CarrySlot(name, None, self.require_scalar(env[name]).type_name))
        for name in visible_record_order:
            if name not in visible_records:
                continue
            record = self.require_record(env[name])
            for field in self.record_fields(record.record_type):
                if (name, field.name) in assigned_record_fields:
                    value = record.fields[field.name]
                    slots.append(CarrySlot(name, field.name, value.type_name))
        for name in visible_union_order:
            if name not in assigned_unions:
                continue
            union = self.require_union(env[name])
            for slot_name, slot_type in self.union_slot_types(union.union_type):
                slots.append(CarrySlot(name, slot_name, slot_type))
        return slots

    def slot_value(self, env: dict[str, EnvValue], slot: CarrySlot) -> Value:
        if slot.field is None:
            return self.require_scalar(env[slot.name])
        value = env[slot.name]
        if isinstance(value, UnionStorage):
            return value.slots[slot.field]
        return self.require_record(value).fields[slot.field]

    def set_slot_value(self, env: dict[str, EnvValue], slot: CarrySlot, value: Value) -> None:
        if slot.field is None:
            env[slot.name] = value
            return
        current = env[slot.name]
        if isinstance(current, UnionStorage):
            slots = dict(current.slots)
            slots[slot.field] = value
            env[slot.name] = UnionStorage(current.union_type, slots)
            return
        record = self.require_record(current)
        fields = dict(record.fields)
        fields[slot.field] = value
        env[slot.name] = RecordStorage(record.record_type, fields)

    def env_types(self, env: dict[str, EnvValue]) -> dict[str, ValueType]:
        result: dict[str, ValueType] = {name: value.type_name for name, value in self.top_constants.items()}
        for name, value in env.items():
            if isinstance(value, BufferStorage):
                result[name] = value.buffer_type
            elif isinstance(value, ArrayStorage):
                result[name] = value.array_type
            elif isinstance(value, ViewStorage):
                result[name] = value.view_type
            elif isinstance(value, RecordStorage):
                result[name] = value.record_type
            elif isinstance(value, UnionStorage):
                result[name] = value.union_type
            else:
                result[name] = value.type_name
        return result

    def require_scalar(self, value: EnvValue) -> Value:
        if isinstance(value, BufferStorage | ArrayStorage | ViewStorage | RecordStorage | UnionStorage):
            raise AssertionError("non-scalar used where scalar value was expected")  # pragma: no cover
        return value

    def require_buffer(self, value: EnvValue) -> BufferStorage:
        if not isinstance(value, BufferStorage):
            raise AssertionError("non-buffer used where buffer storage was expected")  # pragma: no cover
        return value

    def require_indexable(self, value: EnvValue) -> BufferStorage | ArrayStorage | ViewStorage:
        if not isinstance(value, BufferStorage | ArrayStorage | ViewStorage):
            raise AssertionError("non-storage used where indexable storage was expected")  # pragma: no cover
        return value

    def storage_element_type(self, value: BufferStorage | ArrayStorage | ViewStorage) -> ValueType:
        if isinstance(value, BufferStorage):
            return value.buffer_type.element_type
        if isinstance(value, ArrayStorage):
            return value.array_type.element_type
        return value.element_type

    def storage_mlir_type(self, value: BufferStorage | ArrayStorage | ViewStorage) -> str:
        if isinstance(value, BufferStorage):
            return memref_type(value.buffer_type)
        if isinstance(value, ArrayStorage):
            return memref_type(value.array_type)
        return dynamic_memref_type(value.element_type)

    def require_record(self, value: EnvValue) -> RecordStorage:
        if not isinstance(value, RecordStorage):
            raise AssertionError("non-record used where record storage was expected")  # pragma: no cover
        return value

    def require_union(self, value: EnvValue) -> UnionStorage:
        if not isinstance(value, UnionStorage):
            raise AssertionError("non-union used where union storage was expected")  # pragma: no cover
        return value

    def record_fields(self, record_type: RecordType):
        return self.records[record_type.name].fields

    def call_symbol(self, fn: Function) -> str:
        return fn.extern_symbol or fn.name

    def return_types(self, return_type: ValueType | RecordType) -> list[ValueType]:
        if isinstance(return_type, RecordType):
            result: list[ValueType] = []
            for field in self.record_fields(return_type):
                result.append(field.type_name)
            return result
        if isinstance(return_type, UnionType):
            return [slot_type for _slot_name, slot_type in self.union_slot_types(return_type)]
        return [return_type]

    def return_type_list(self, return_type: ValueType | RecordType) -> str:
        return self.result_type_list(self.return_types(return_type))

    def type_list(self, types: list[ValueType]) -> str:
        return ", ".join(mlir_type(type_name) for type_name in types)

    def result_type_list(self, types: list[ValueType]) -> str:
        if len(types) == 1:
            return mlir_type(types[0])
        return f"({self.type_list(types)})"
