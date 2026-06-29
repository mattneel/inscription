from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .ast import (
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
    Comparison,
    Expr,
    FieldAccess,
    FieldAssignStmt,
    ForEachStmt,
    ForStmt,
    Function,
    IfStmt,
    Integer,
    AlignmentOfType,
    LengthOf,
    LayoutRead,
    LayoutWriteStmt,
    OffsetOfField,
    Program,
    RecordConstructor,
    RecordType,
    ReturnStmt,
    SetStmt,
    SizeOfType,
    Stmt,
    TypeName,
    Unary,
    Variable,
    WhenCase,
    WhenExpr,
    WhileStmt,
)
from .semantic import (
    ValueType,
    all_ones_constant_value,
    analyze,
    byte_width,
    function_table,
    infer_comparison_operand_type,
    infer_expr_type,
    is_signed_type,
    layout_info,
    memref_type,
    mlir_type,
    record_table,
    type_width,
)


@dataclass(frozen=True)
class Value:
    name: str
    type_name: TypeName


@dataclass(frozen=True)
class BufferStorage:
    name: str
    buffer_type: BufferType


@dataclass(frozen=True)
class RecordStorage:
    record_type: RecordType
    fields: dict[str, Value]


@dataclass(frozen=True)
class CarrySlot:
    name: str
    field: str | None
    type_name: TypeName

    @property
    def label(self) -> str:
        if self.field is None:
            return self.name
        return f"{self.name}_{self.field}"


EnvValue = Value | BufferStorage | RecordStorage
ConstantKey = tuple[str, int | bool, TypeName]


def mlir_value_type(type_name: ValueType) -> str:
    if isinstance(type_name, BufferType):
        return memref_type(type_name)
    if isinstance(type_name, RecordType):
        raise AssertionError("record type must be flattened before MLIR type emission")  # pragma: no cover
    return mlir_type(type_name)


def mlir_env_value_type(value: "EnvValue") -> str:
    if isinstance(value, BufferStorage):
        return memref_type(value.buffer_type)
    if isinstance(value, RecordStorage):
        raise AssertionError("record value must be flattened before MLIR type emission")  # pragma: no cover
    return mlir_type(value.type_name)


def emit_mlir(program: Program) -> str:
    analyze(program)
    emitter = MlirEmitter(program)
    return emitter.emit_program(program)


class MlirEmitter:
    def __init__(self, program: Program):
        self.functions = function_table(program)
        self.records = record_table(program)
        self.counter = 0
        self.constants: dict[ConstantKey, Value] = {}
        self.binding_order: list[str] = []
        self.record_order: list[str] = []
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
        for index, fn in enumerate(program.functions):
            if index:
                lines.append("")
            self.emit_function(fn, lines)
        lines.append("}")
        return "\n".join(lines) + "\n"

    def emit_function(self, fn: Function, lines: list[str]) -> None:
        self.counter = 0
        self.constants = {}
        self.binding_order = [param.name for param in fn.params if not isinstance(param.type_name, BufferType | RecordType)]
        self.record_order = [param.name for param in fn.params if isinstance(param.type_name, RecordType)]
        self.while_counter = 0
        self.while_depth = 0
        self.for_counter = 0
        self.for_depth = 0
        args = ", ".join(self.function_argument_decls(fn))
        return_suffix = "" if fn.return_type is None else f" -> {mlir_type(fn.return_type)}"
        lines.append(f"  func.func @{fn.name}({args}){return_suffix} {{")
        env: dict[str, EnvValue] = {}
        for param in fn.params:
            if isinstance(param.type_name, BufferType):
                env[param.name] = BufferStorage(f"%{param.name}", param.type_name)
            elif isinstance(param.type_name, RecordType):
                env[param.name] = self.record_parameter_storage(param.name, param.type_name)
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
            if isinstance(param.type_name, RecordType):
                for field in self.record_fields(param.type_name):
                    assert isinstance(field.type_name, str)
                    args.append(f"%{param.name}_{field.name}: {mlir_type(field.type_name)}")
                continue
            args.append(f"%{param.name}: {mlir_type(param.type_name)}")
        return args

    def record_parameter_storage(self, name: str, record_type: RecordType) -> RecordStorage:
        return RecordStorage(
            record_type,
            {
                field.name: Value(f"%{name}_{field.name}", field.type_name)  # type: ignore[arg-type]
                for field in self.record_fields(record_type)
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
        return_type: TypeName,
    ) -> None:
        for stmt in statements:
            if isinstance(stmt, ReturnStmt):
                value = self.emit_expr(stmt.expr, env, lines, indent, expected=return_type)
                lines.append(f"{indent}return {value.name} : {mlir_type(return_type)}")
            else:
                self.emit_body_stmt(stmt, env, lines, indent)

    def emit_body_stmt(self, stmt: Stmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        if isinstance(stmt, SetStmt):
            env_types = self.env_types(env)
            type_name = stmt.type_name or infer_expr_type(stmt.expr, env_types, self.functions, self.records)
            if isinstance(type_name, RecordType):
                env[stmt.name] = self.emit_record_expr(stmt.expr, env, lines, indent, expected=type_name)
                self.record_order.append(stmt.name)
            else:
                env[stmt.name] = self.emit_expr(stmt.expr, env, lines, indent, expected=type_name)
                self.binding_order.append(stmt.name)
            return
        if isinstance(stmt, BufferBinding):
            self.emit_buffer_binding(stmt, env, lines, indent)
            return
        if isinstance(stmt, AssignStmt):
            current_value = env[stmt.name]
            if isinstance(current_value, RecordStorage):
                env[stmt.name] = self.emit_record_expr(stmt.expr, env, lines, indent, expected=current_value.record_type)
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
        raise AssertionError(stmt)  # pragma: no cover

    def emit_expr(
        self,
        expr: Expr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        *,
        expected: TypeName | None = None,
    ) -> Value:
        env_types = self.env_types(env)
        type_name = infer_expr_type(expr, env_types, self.functions, self.records, expected=expected)
        if isinstance(type_name, RecordType):
            raise AssertionError("record expression used where scalar value was expected")  # pragma: no cover
        if isinstance(expr, Integer):
            return self.emit_integer(expr.value, type_name, lines, indent)
        if isinstance(expr, Boolean):
            return self.emit_boolean(expr.value, lines, indent)
        if isinstance(expr, Variable):
            return self.require_scalar(env[expr.name])
        if isinstance(expr, BufferLoad):
            return self.emit_buffer_load(expr, env, lines, indent)
        if isinstance(expr, LengthOf):
            buffer = self.require_buffer(env[expr.name])
            return self.emit_integer(buffer.buffer_type.length, "i32", lines, indent)
        if isinstance(expr, SizeOfType):
            return self.emit_integer(layout_info(self.records[expr.type_name]).size, "i32", lines, indent)
        if isinstance(expr, AlignmentOfType):
            return self.emit_integer(layout_info(self.records[expr.type_name]).alignment, "i32", lines, indent)
        if isinstance(expr, OffsetOfField):
            return self.emit_integer(layout_info(self.records[expr.type_name]).field_offsets[expr.field], "i32", lines, indent)
        if isinstance(expr, FieldAccess):
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
            assert not isinstance(target.return_type, RecordType)
            out = Value(self.fresh(), target.return_type)
            arg_values = ", ".join(arg.name for arg in args)
            arg_types = ", ".join(mlir_env_value_type(arg) for arg in args)
            lines.append(
                f"{indent}{out.name} = func.call @{expr.name}({arg_values}) : ({arg_types}) -> {mlir_type(target.return_type)}"
            )
            return out
        if isinstance(expr, Comparison):
            return self.emit_comparison(expr, env, lines, indent)
        if isinstance(expr, WhenExpr):
            return self.emit_when_expr(expr, env, lines, indent, type_name)
        raise AssertionError(expr)  # pragma: no cover

    def emit_unary(self, expr: Unary, env: dict[str, EnvValue], lines: list[str], indent: str, type_name: TypeName) -> Value:
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

    def emit_binary(self, expr: Binary, env: dict[str, EnvValue], lines: list[str], indent: str, type_name: TypeName) -> Value:
        operand_type = "i1" if expr.op in {"and", "or"} else type_name
        left = self.emit_expr(expr.left, env, lines, indent, expected=operand_type)
        right = self.emit_expr(expr.right, env, lines, indent, expected=operand_type)
        out = Value(self.fresh(), type_name)
        op = self.binary_mlir_op(expr.op, type_name)
        lines.append(f"{indent}{out.name} = arith.{op} {left.name}, {right.name} : {mlir_type(type_name)}")
        return out

    def binary_mlir_op(self, op: str, type_name: TypeName) -> str:
        if op == "plus":
            return "addi"
        if op == "minus":
            return "subi"
        if op == "times":
            return "muli"
        if op == "divided by":
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

    def emit_cast(self, expr: Cast, env: dict[str, EnvValue], lines: list[str], indent: str, target_type: TypeName) -> Value:
        source = self.emit_expr(expr.expr, env, lines, indent)
        source_type = source.type_name
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

    def emit_integer(self, value: int, type_name: TypeName, lines: list[str], indent: str) -> Value:
        key: ConstantKey = ("int", value, type_name)
        cached = self.constants.get(key)
        if cached is not None:
            return cached
        out = Value(self.fresh(), type_name)
        self.constants[key] = out
        lines.append(f"{indent}{out.name} = arith.constant {value} : {mlir_type(type_name)}")
        return out

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

    def emit_buffer_binding(self, stmt: BufferBinding, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        buffer_type = stmt.buffer_type
        buffer = BufferStorage(self.fresh(), buffer_type)
        lines.append(f"{indent}{buffer.name} = memref.alloca() : {memref_type(buffer_type)}")
        fill = self.emit_expr(stmt.fill, env, lines, indent, expected=buffer_type.element_type)
        lower = self.emit_index_constant(0, lines, indent)
        upper = self.emit_index_constant(buffer_type.length, lines, indent)
        step = self.emit_index_constant(1, lines, indent)
        iv = self.fresh()
        lines.append(f"{indent}scf.for {iv} = {lower} to {upper} step {step} {{")
        lines.append(f"{indent}  memref.store {fill.name}, {buffer.name}[{iv}] : {memref_type(buffer_type)}")
        lines.append(f"{indent}}}")
        env[stmt.name] = buffer

    def emit_buffer_load(self, expr: BufferLoad, env: dict[str, EnvValue], lines: list[str], indent: str) -> Value:
        buffer = self.require_buffer(env[expr.name])
        index = self.emit_index(expr.index, env, lines, indent)
        out = Value(self.fresh(), buffer.buffer_type.element_type)
        lines.append(f"{indent}{out.name} = memref.load {buffer.name}[{index}] : {memref_type(buffer.buffer_type)}")
        return out

    def emit_buffer_store(self, stmt: BufferStoreStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        buffer = self.require_buffer(env[stmt.name])
        value = self.emit_expr(stmt.value, env, lines, indent, expected=buffer.buffer_type.element_type)
        index = self.emit_index(stmt.index, env, lines, indent)
        lines.append(f"{indent}memref.store {value.name}, {buffer.name}[{index}] : {memref_type(buffer.buffer_type)}")

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
        buffer = self.require_buffer(env[expr.buffer_name])
        base = self.emit_index(expr.index, env, lines, indent)
        fields: dict[str, Value] = {}
        for field in record.fields:
            assert isinstance(field.type_name, str)
            offset = info.field_offsets[field.name]
            fields[field.name] = self.emit_layout_field_read(buffer, base, offset, field.type_name, lines, indent)
        return RecordStorage(expected, fields)

    def emit_layout_field_read(
        self,
        buffer: BufferStorage,
        base: str,
        offset: int,
        type_name: TypeName,
        lines: list[str],
        indent: str,
    ) -> Value:
        width = byte_width(type_name)
        result: Value | None = None
        for byte_index in range(width):
            index_value = self.emit_index_offset(base, offset + byte_index, lines, indent)
            byte = Value(self.fresh(), "u8")
            lines.append(f"{indent}{byte.name} = memref.load {buffer.name}[{index_value}] : {memref_type(buffer.buffer_type)}")
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
        buffer = self.require_buffer(env[stmt.buffer_name])
        base = self.emit_index(stmt.index, env, lines, indent)
        field_bytes: dict[int, tuple[str, int]] = {}
        for field in record_decl.fields:
            assert isinstance(field.type_name, str)
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
            lines.append(f"{indent}memref.store {value.name}, {buffer.name}[{index_value}] : {memref_type(buffer.buffer_type)}")

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
                assert isinstance(field.type_name, str)
                fields[field.name] = self.emit_expr(initializer.expr, env, lines, indent, expected=field.type_name)
            return RecordStorage(expected, fields)
        if isinstance(expr, LayoutRead):
            return self.emit_layout_read(expr, env, lines, indent, expected=expected)
        raise AssertionError("unsupported record expression")  # pragma: no cover

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
        arg_types = ", ".join(mlir_env_value_type(arg) for arg in args)
        lines.append(f"{indent}func.call @{stmt.call.name}({arg_values}) : ({arg_types}) -> ()")

    def emit_call_arguments(
        self,
        call: Call,
        target: Function,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
    ) -> list[EnvValue]:
        args: list[EnvValue] = []
        for arg, param in zip(call.args, target.params, strict=True):
            if isinstance(param.type_name, BufferType):
                assert isinstance(arg, Variable)
                args.append(self.require_buffer(env[arg.name]))
            elif isinstance(param.type_name, RecordType):
                assert isinstance(arg, Variable)
                record = self.require_record(env[arg.name])
                for field in self.record_fields(param.type_name):
                    args.append(record.fields[field.name])
            else:
                args.append(self.emit_expr(arg, env, lines, indent, expected=param.type_name))
        return args

    def emit_index(self, expr: Expr, env: dict[str, EnvValue], lines: list[str], indent: str) -> str:
        if isinstance(expr, Integer):
            return self.emit_index_constant(expr.value, lines, indent)
        value = self.emit_expr(expr, env, lines, indent)
        out = self.fresh()
        op = "index_cast" if is_signed_type(value.type_name) else "index_castui"
        lines.append(f"{indent}{out} = arith.{op} {value.name} : {mlir_type(value.type_name)} to index")
        return out

    def emit_index_to_integer(self, index_value: str, type_name: TypeName, lines: list[str], indent: str) -> Value:
        out = Value(self.fresh(), type_name)
        op = "index_cast" if is_signed_type(type_name) else "index_castui"
        lines.append(f"{indent}{out.name} = arith.{op} {index_value} : index to {mlir_type(type_name)}")
        return out

    def emit_when_expr(
        self, expr: WhenExpr, env: dict[str, EnvValue], lines: list[str], indent: str, type_name: TypeName
    ) -> Value:
        return self.emit_when_cases(list(expr.cases), expr.otherwise, env, lines, indent, type_name)

    def emit_when_cases(
        self,
        cases: list[WhenCase],
        otherwise: Expr,
        env: dict[str, EnvValue],
        lines: list[str],
        indent: str,
        type_name: TypeName,
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

    def emit_comparison(self, condition: Comparison, env: dict[str, EnvValue], lines: list[str], indent: str) -> Value:
        env_types = self.env_types(env)
        type_name = infer_comparison_operand_type(condition, env_types, self.functions, self.records)
        left = self.emit_expr(condition.left, env, lines, indent, expected=type_name)
        right = self.emit_expr(condition.right, env, lines, indent, expected=type_name)
        out = Value(self.fresh(), "i1")
        pred = self.comparison_predicate(condition.pred, type_name)
        lines.append(f"{indent}{out.name} = arith.cmpi {pred}, {left.name}, {right.name} : {mlir_type(type_name)}")
        return out

    def comparison_predicate(self, pred: str, type_name: TypeName) -> str:
        if pred in {"eq", "ne"} or is_signed_type(type_name):
            return pred
        return {"slt": "ult", "sle": "ule", "sgt": "ugt", "sge": "uge"}[pred]

    def emit_while(self, stmt: WhileStmt, env: dict[str, EnvValue], lines: list[str], indent: str) -> None:
        loop_id = self.while_counter
        self.while_counter += 1
        arg_suffix = "" if self.while_depth == 0 else f"_loop{loop_id}"
        visible_binding_order = list(self.binding_order)
        visible_record_order = list(self.record_order)
        carried_slots = self.assigned_binding_slots(stmt.body, visible_binding_order, visible_record_order, env)
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
        carried_types: list[TypeName],
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
        carried_types: list[TypeName],
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
        loop_type = infer_expr_type(stmt.start, env_types, self.functions, self.records)
        assert not isinstance(loop_type, BufferType | RecordType)
        start = self.emit_index(stmt.start, env, lines, indent)
        end = self.emit_index(stmt.end, env, lines, indent)
        step = self.emit_index_constant(stmt.step, lines, indent)
        iv = self.fresh()

        visible_binding_order = list(self.binding_order)
        visible_record_order = list(self.record_order)
        carried_slots = self.assigned_binding_slots(stmt.body, visible_binding_order, visible_record_order, env)
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
        buffer = self.require_buffer(env[stmt.buffer_name])
        lower = self.emit_index_constant(0, lines, indent)
        upper = self.emit_index_constant(buffer.buffer_type.length, lines, indent)
        step = self.emit_index_constant(1, lines, indent)
        iv = self.fresh()

        loop_id = self.for_counter
        self.for_counter += 1
        arg_suffix = "" if self.for_depth == 0 else f"_for{loop_id}"
        visible_binding_order = list(self.binding_order)
        visible_record_order = list(self.record_order)
        carried_slots = self.assigned_binding_slots(stmt.body, visible_binding_order, visible_record_order, env)
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
        carried_types: list[TypeName],
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
        result_slots = self.assigned_binding_slots((*stmt.then_body, *stmt.else_body), visible_binding_order, visible_record_order, env)
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
        result_types: list[TypeName],
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
        try:
            emit()
        finally:
            self.binding_order = saved_binding_order
            self.record_order = saved_record_order

    def assigned_binding_slots(
        self,
        body: tuple[BodyStmt, ...],
        visible_binding_order: list[str],
        visible_record_order: list[str],
        env: dict[str, EnvValue],
    ) -> list[CarrySlot]:
        visible_scalars = set(visible_binding_order)
        visible_records = set(visible_record_order)
        assigned_scalars: set[str] = set()
        assigned_record_fields: set[tuple[str, str]] = set()

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
        return slots

    def slot_value(self, env: dict[str, EnvValue], slot: CarrySlot) -> Value:
        if slot.field is None:
            return self.require_scalar(env[slot.name])
        return self.require_record(env[slot.name]).fields[slot.field]

    def set_slot_value(self, env: dict[str, EnvValue], slot: CarrySlot, value: Value) -> None:
        if slot.field is None:
            env[slot.name] = value
            return
        record = self.require_record(env[slot.name])
        fields = dict(record.fields)
        fields[slot.field] = value
        env[slot.name] = RecordStorage(record.record_type, fields)

    def env_types(self, env: dict[str, EnvValue]) -> dict[str, ValueType]:
        result: dict[str, ValueType] = {}
        for name, value in env.items():
            if isinstance(value, BufferStorage):
                result[name] = value.buffer_type
            elif isinstance(value, RecordStorage):
                result[name] = value.record_type
            else:
                result[name] = value.type_name
        return result

    def require_scalar(self, value: EnvValue) -> Value:
        if isinstance(value, BufferStorage | RecordStorage):
            raise AssertionError("non-scalar used where scalar value was expected")  # pragma: no cover
        return value

    def require_buffer(self, value: EnvValue) -> BufferStorage:
        if not isinstance(value, BufferStorage):
            raise AssertionError("non-buffer used where buffer storage was expected")  # pragma: no cover
        return value

    def require_record(self, value: EnvValue) -> RecordStorage:
        if not isinstance(value, RecordStorage):
            raise AssertionError("non-record used where record storage was expected")  # pragma: no cover
        return value

    def record_fields(self, record_type: RecordType):
        return self.records[record_type.name].fields

    def type_list(self, types: list[TypeName]) -> str:
        return ", ".join(mlir_type(type_name) for type_name in types)

    def result_type_list(self, types: list[TypeName]) -> str:
        if len(types) == 1:
            return mlir_type(types[0])
        return f"({self.type_list(types)})"
