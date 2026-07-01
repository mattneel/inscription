from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .ast import (
    AlignmentOfType,
    AlternativePattern,
    AnythingPattern,
    ArrayBinding,
    ArrayType,
    AssignStmt,
    Binary,
    Boolean,
    ByteLiteral,
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
    ExpectStmt,
    Expr,
    FieldAccess,
    FieldAssignStmt,
    Float,
    ForEachStmt,
    ForStmt,
    Function,
    IfStmt,
    Integer,
    LengthOf,
    LengthOfBytes,
    LayoutRead,
    LayoutWriteStmt,
    MatchExpr,
    MatchStep,
    MoveArg,
    OffsetOfField,
    OwnedBufferBinding,
    OwnedBufferType,
    Program,
    RangePattern,
    RecordConstructor,
    RecordType,
    RequireStmt,
    ReturnStmt,
    SetStmt,
    SizeOfType,
    StorageAliasBinding,
    TypeName,
    Unary,
    UnionConstructor,
    UnionPattern,
    UnionType,
    ValueType,
    Variable,
    ViewBinding,
    ViewType,
    WhenExpr,
    WhileStmt,
)
from .diagnostics import InscriptionError
from .semantic import (
    ConstValue,
    analyze,
    cast_const_value,
    constant_table,
    enum_table,
    evaluate_comparison,
    evaluate_numeric_binary,
    format_type,
    function_table,
    infer_cast_type,
    infer_comparison_operand_type,
    infer_expr_type,
    is_float_type,
    is_integer_type,
    normalize_float,
    normalize_integer,
    parse_float_literal,
    record_table,
    resolve_function_table,
    resolve_named_value_type,
    storage_type,
    to_bits,
    type_alias_table,
    union_table,
)


class InterpreterError(InscriptionError):
    """Deterministic diagnostic raised by the internal v0.48 interpreter."""


@dataclass(frozen=True)
class BoolValue:
    type_name: TypeName
    value: bool


@dataclass(frozen=True)
class IntValue:
    type_name: TypeName
    value: int


@dataclass(frozen=True)
class FloatValue:
    type_name: TypeName
    value: float


@dataclass(frozen=True)
class EnumValue:
    type_name: EnumType
    underlying_value: int


@dataclass(frozen=True)
class RecordValue:
    type_name: RecordType
    fields: dict[str, "Value"]


@dataclass(frozen=True)
class UnionValue:
    type_name: UnionType
    variant_name: str
    fields: dict[str, "Value"]


Value: TypeAlias = BoolValue | IntValue | FloatValue | EnumValue | RecordValue | UnionValue


class _ReturnSignal(Exception):
    def __init__(self, value: Value):
        self.value = value


class Interpreter:
    """Internal deterministic interpreter for the pure v0.48 subset."""

    def __init__(self, program: Program, *, step_limit: int = 100_000):
        self.program = program
        self.step_limit = step_limit
        self.remaining_steps = step_limit

        analyze(program)
        type_alias_table(program)
        self.enums = enum_table(program)
        self.unions = union_table(program)
        self.records = record_table(program)
        functions = function_table(program)
        self.constants = constant_table(program, self.records, functions)
        self.functions = resolve_function_table(functions, self.records, self.constants)

    def call_phrase(self, phrase_name_or_symbol: str, args: list[Value | int | bool | float] | tuple[Value | int | bool | float, ...] = ()) -> Value:
        self.remaining_steps = self.step_limit
        fn = self._find_phrase(phrase_name_or_symbol)
        if fn.implementation == "extern":
            raise InterpreterError("interpreter does not support extern phrase calls in v0.48", fn.line)
        if fn.return_type is None:
            raise InterpreterError("interpreter does not support does phrase calls in v0.48", fn.line)
        self._require_supported_type(fn.return_type, "return type", fn.line)
        if len(args) != len(fn.params):
            raise InterpreterError(f"interpreter expected {len(fn.params)} arguments, got {len(args)}", fn.line)
        env: dict[str, Value] = {}
        for param, arg in zip(fn.params, args, strict=True):
            self._require_supported_type(param.type_name, f"parameter {param.name}", fn.line)
            env[param.name] = self._coerce_argument(arg, param.type_name, param.name)
        try:
            self._execute_statements(fn.body, env)
        except _ReturnSignal as signal:
            return signal.value
        raise InterpreterError(f"phrase `{fn.display_name}` did not give a value", fn.line)

    def enum_value(self, type_name: str, case_name: str) -> EnumValue:
        resolved = resolve_named_value_type(RecordType(type_name))
        if not isinstance(resolved, EnumType):
            raise InterpreterError(f"unknown enum type {type_name}")
        info = self.enums.get(resolved.name)
        if info is None or case_name not in info.cases:
            raise InterpreterError(f"enum {type_name} has no case {case_name}")
        return EnumValue(EnumType(info.name, info.underlying_type), info.cases[case_name])

    def record_value(self, type_name: str, fields: dict[str, Value | int | bool | float]) -> RecordValue:
        resolved = resolve_named_value_type(RecordType(type_name))
        if not isinstance(resolved, RecordType) or resolved.name not in self.records:
            raise InterpreterError(f"unknown record type {type_name}")
        record = self.records[resolved.name]
        coerced: dict[str, Value] = {}
        for field in record.fields:
            if field.name not in fields:
                raise InterpreterError(f"record {record.name} missing field {field.name}")
            coerced[field.name] = self._coerce_argument(fields[field.name], field.type_name, field.name)
        return RecordValue(RecordType(record.name), coerced)

    def union_value(self, type_name: str, variant_name: str, fields: dict[str, Value | int | bool | float] | None = None) -> UnionValue:
        resolved = resolve_named_value_type(RecordType(type_name))
        if not isinstance(resolved, UnionType) or resolved.name not in self.unions:
            raise InterpreterError(f"unknown union type {type_name}")
        union = self.unions[resolved.name]
        if variant_name not in union.variants:
            raise InterpreterError(f"union {union.name} has no variant {variant_name}")
        variant = union.variants[variant_name]
        raw_fields = fields or {}
        coerced: dict[str, Value] = {}
        for payload in variant.payload_fields:
            if payload.name not in raw_fields:
                raise InterpreterError(f"variant {union.name}.{variant.name} missing payload {payload.name}")
            coerced[payload.name] = self._coerce_argument(raw_fields[payload.name], payload.type_name, payload.name)
        return UnionValue(UnionType(union.name), variant.name, coerced)

    def _find_phrase(self, phrase_name_or_symbol: str) -> Function:
        if phrase_name_or_symbol in self.functions:
            return self.functions[phrase_name_or_symbol]
        for fn in self.functions.values():
            if fn.display_name == phrase_name_or_symbol or fn.extern_symbol == phrase_name_or_symbol:
                return fn
        raise InterpreterError(f"interpreter cannot find phrase {phrase_name_or_symbol}")

    def _tick(self) -> None:
        self.remaining_steps -= 1
        if self.remaining_steps < 0:
            raise InterpreterError("interpreter step limit exceeded")

    def _execute_statements(self, statements: tuple, env: dict[str, Value]) -> None:
        for stmt in statements:
            self._tick()
            self._execute_statement(stmt, env)

    def _execute_nested(self, statements: tuple, env: dict[str, Value]) -> None:
        parent_names = set(env)
        scoped = dict(env)
        try:
            self._execute_statements(statements, scoped)
        finally:
            for name in parent_names:
                env[name] = scoped[name]

    def _execute_statement(self, stmt: object, env: dict[str, Value]) -> None:
        if isinstance(stmt, SetStmt):
            expected = resolve_named_value_type(stmt.type_name) if stmt.type_name is not None else None
            value = self._eval_expr(stmt.expr, env, expected=expected)
            if expected is not None:
                self._require_value_type(value, expected, stmt.line)
            env[stmt.name] = value
            return
        if isinstance(stmt, AssignStmt):
            if stmt.name not in env:
                raise InterpreterError(f"unknown binding {stmt.name}", stmt.line)
            value = self._eval_expr(stmt.expr, env, expected=self._value_type(env[stmt.name]))
            env[stmt.name] = value
            return
        if isinstance(stmt, FieldAssignStmt):
            target = env.get(stmt.name)
            if not isinstance(target, RecordValue):
                raise InterpreterError(f"{stmt.name} is not a record", stmt.line)
            if stmt.field not in target.fields:
                raise InterpreterError(f"record {target.type_name.name} has no field {stmt.field}", stmt.line)
            value = self._eval_expr(stmt.expr, env, expected=self._value_type(target.fields[stmt.field]))
            fields = dict(target.fields)
            fields[stmt.field] = value
            env[stmt.name] = RecordValue(target.type_name, fields)
            return
        if isinstance(stmt, IfStmt):
            condition = self._eval_i1(stmt.condition, env)
            self._execute_nested(stmt.then_body if condition else stmt.else_body, env)
            return
        if isinstance(stmt, WhileStmt):
            while self._eval_i1(stmt.condition, env):
                self._tick()
                self._execute_nested(stmt.body, env)
            return
        if isinstance(stmt, ForStmt):
            start = self._int_for_loop_bound(stmt.start, env)
            end = self._int_for_loop_bound(stmt.end, env)
            step = stmt.step
            if step == 0:
                raise InterpreterError("interpreter for loop step must not be zero", stmt.line)
            parent_names = set(env)
            scoped = dict(env)
            for index in range(start, end, step):
                self._tick()
                scoped[stmt.name] = IntValue("i32", normalize_integer(index, "i32"))
                self._execute_statements(stmt.body, scoped)
                for name in parent_names:
                    env[name] = scoped[name]
            return
        if isinstance(stmt, MatchStep):
            scrutinee = self._eval_expr(stmt.scrutinee, env)
            for arm in stmt.arms:
                matched, bindings = self._match_pattern(arm.pattern, scrutinee, env)
                if not matched:
                    continue
                scoped = {**env, **bindings}
                if arm.guard is not None and not self._eval_i1(arm.guard, scoped):
                    continue
                self._execute_nested(arm.body, scoped)
                for name in env:
                    env[name] = scoped[name]
                return
            if stmt.otherwise_body is not None:
                self._execute_nested(stmt.otherwise_body, env)
                return
            if stmt.arms:
                scoped = dict(env)
                self._execute_nested(stmt.arms[-1].body, scoped)
                for name in env:
                    env[name] = scoped[name]
                return
            return
        if isinstance(stmt, RequireStmt | CheckStmt):
            if not self._eval_i1(stmt.expr, env):
                raise InterpreterError("interpreter assertion failed", stmt.line)
            return
        if isinstance(stmt, ReturnStmt):
            raise _ReturnSignal(self._eval_expr(stmt.expr, env))
        if isinstance(stmt, BufferBinding):
            raise InterpreterError("interpreter does not support buffers in v0.48", stmt.line)
        if isinstance(stmt, ArrayBinding):
            raise InterpreterError("interpreter does not support arrays in v0.48", stmt.line)
        if isinstance(stmt, StorageAliasBinding):
            if isinstance(resolve_named_value_type(stmt.alias_type), ArrayType):
                raise InterpreterError("interpreter does not support arrays in v0.48", stmt.line)
            raise InterpreterError("interpreter does not support buffers in v0.48", stmt.line)
        if isinstance(stmt, OwnedBufferBinding):
            raise InterpreterError("interpreter does not support owned buffers in v0.48", stmt.line)
        if isinstance(stmt, ViewBinding):
            raise InterpreterError("interpreter does not support views in v0.48", stmt.line)
        if isinstance(stmt, BufferStoreStmt):
            raise InterpreterError("interpreter does not support buffer stores in v0.48", stmt.line)
        if isinstance(stmt, LayoutWriteStmt):
            raise InterpreterError("interpreter does not support layout write in v0.48", stmt.line)
        if isinstance(stmt, ForEachStmt):
            raise InterpreterError("interpreter does not support for-each loops in v0.48", stmt.line)
        if isinstance(stmt, CallStmt):
            raise InterpreterError("interpreter does not support does phrase calls in v0.48", stmt.line)
        if isinstance(stmt, ExpectStmt):
            raise InterpreterError("interpreter does not support tests in v0.48", stmt.line)
        raise InterpreterError(f"interpreter does not support {type(stmt).__name__} in v0.48", getattr(stmt, "line", None))

    def _eval_expr(self, expr: Expr, env: dict[str, Value], *, expected: ValueType | None = None) -> Value:
        self._tick()
        env_types = self._env_types(env)
        if isinstance(expr, Integer):
            type_name = infer_expr_type(expr, env_types, self.functions, self.records, expected=expected, constants=self.constants)
            if is_float_type(type_name) and expr.is_word_zero:
                assert isinstance(type_name, str)
                return FloatValue(type_name, normalize_float(0.0, type_name))
            assert isinstance(type_name, str)
            return IntValue(type_name, normalize_integer(expr.value, type_name))
        if isinstance(expr, ByteLiteral):
            return IntValue("u8", expr.value)
        if isinstance(expr, Float):
            type_name = infer_expr_type(expr, env_types, self.functions, self.records, expected=expected, constants=self.constants)
            assert isinstance(type_name, str)
            return FloatValue(type_name, normalize_float(parse_float_literal(expr.text, expr.line), type_name))
        if isinstance(expr, Boolean):
            return BoolValue("i1", expr.value)
        if isinstance(expr, Variable):
            if expr.name in env:
                value = env[expr.name]
                if expected is not None:
                    self._require_value_type(value, expected, expr.line)
                return value
            if expr.name in self.constants:
                value = self._value_from_const(self.constants[expr.name])
                if expected is not None:
                    self._require_value_type(value, expected, expr.line)
                return value
            raise InterpreterError(f"unknown binding {expr.name}", expr.line)
        if isinstance(expr, EnumCase):
            resolved = resolve_named_value_type(RecordType(expr.type_name))
            if isinstance(resolved, UnionType):
                return self.union_value(resolved.name, expr.case_name)
            if not isinstance(resolved, EnumType):
                raise InterpreterError(f"unknown enum type {expr.type_name}", expr.line)
            info = self.enums[resolved.name]
            if expr.case_name not in info.cases:
                raise InterpreterError(f"enum {expr.type_name} has no case {expr.case_name}", expr.line)
            return EnumValue(EnumType(info.name, info.underlying_type), info.cases[expr.case_name])
        if isinstance(expr, UnionConstructor):
            return self._eval_union_constructor(expr, env)
        if isinstance(expr, RecordConstructor):
            return self._eval_record_constructor(expr, env)
        if isinstance(expr, FieldAccess):
            target = env.get(expr.name)
            if target is None and f"{expr.name}.{expr.field}" in self.constants:
                return self._value_from_const(self.constants[f"{expr.name}.{expr.field}"])
            if not isinstance(target, RecordValue):
                raise InterpreterError(f"{expr.name} is not a record", expr.line)
            try:
                return target.fields[expr.field]
            except KeyError as exc:
                raise InterpreterError(f"record {target.type_name.name} has no field {expr.field}", expr.line) from exc
        if isinstance(expr, LengthOfBytes):
            return IntValue("i32", len(expr.values))
        if isinstance(expr, Cast):
            return self._eval_cast(expr, env)
        if isinstance(expr, Unary):
            return self._eval_unary(expr, env)
        if isinstance(expr, Binary):
            return self._eval_binary(expr, env, expected=expected)
        if isinstance(expr, Comparison):
            return self._eval_comparison(expr, env)
        if isinstance(expr, WhenExpr):
            result_type = infer_expr_type(expr, env_types, self.functions, self.records, expected=expected, constants=self.constants)
            for case in expr.cases:
                if self._eval_i1(case.condition, env):
                    return self._eval_expr(case.expr, env, expected=result_type)
            return self._eval_expr(expr.otherwise, env, expected=result_type)
        if isinstance(expr, MatchExpr):
            return self._eval_match_expr(expr, env, expected=expected)
        if isinstance(expr, Call):
            return self._eval_call(expr, env)
        if isinstance(expr, BufferLoad):
            raise InterpreterError("interpreter does not support arrays in v0.48", expr.line)
        if isinstance(expr, LengthOf):
            raise InterpreterError("interpreter does not support storage lengths in v0.48", expr.line)
        if isinstance(expr, LayoutRead):
            raise InterpreterError("interpreter does not support layout read in v0.48", expr.line)
        if isinstance(expr, SizeOfType | AlignmentOfType | OffsetOfField):
            raise InterpreterError("interpreter does not support layout introspection in v0.48", getattr(expr, "line", None))
        raise InterpreterError(f"interpreter does not support {type(expr).__name__} in v0.48", getattr(expr, "line", None))

    def _eval_call(self, expr: Call, env: dict[str, Value]) -> Value:
        fn = self._find_phrase(expr.name)
        if fn.implementation == "extern":
            raise InterpreterError("interpreter does not support extern phrase calls in v0.48", expr.line)
        if fn.return_type is None:
            raise InterpreterError("interpreter does not support does phrase calls in v0.48", expr.line)
        if len(expr.args) != len(fn.params):
            raise InterpreterError(f"interpreter expected {len(fn.params)} arguments, got {len(expr.args)}", expr.line)
        args: list[Value] = []
        for param, actual in zip(fn.params, expr.args, strict=True):
            if isinstance(actual, MoveArg):
                raise InterpreterError("interpreter does not support moves in v0.48", actual.line)
            args.append(self._eval_expr(actual, env, expected=param.type_name))
        return self._call_function(fn, args)

    def _call_function(self, fn: Function, args: list[Value]) -> Value:
        saved_steps = self.remaining_steps
        env: dict[str, Value] = {}
        for param, value in zip(fn.params, args, strict=True):
            self._require_supported_type(param.type_name, f"parameter {param.name}", fn.line)
            self._require_value_type(value, param.type_name, fn.line)
            env[param.name] = value
        try:
            self._execute_statements(fn.body, env)
        except _ReturnSignal as signal:
            return signal.value
        finally:
            self.remaining_steps = min(self.remaining_steps, saved_steps)
        raise InterpreterError(f"phrase `{fn.display_name}` did not give a value", fn.line)

    def _eval_record_constructor(self, expr: RecordConstructor, env: dict[str, Value]) -> RecordValue:
        resolved = resolve_named_value_type(RecordType(expr.type_name))
        if not isinstance(resolved, RecordType) or resolved.name not in self.records:
            raise InterpreterError(f"unknown record type {expr.type_name}", expr.line)
        record = self.records[resolved.name]
        inits = {field.name: field for field in expr.fields}
        fields: dict[str, Value] = {}
        for field in record.fields:
            init = inits[field.name]
            fields[field.name] = self._eval_expr(init.expr, env, expected=field.type_name)
        return RecordValue(RecordType(record.name), fields)

    def _eval_union_constructor(self, expr: UnionConstructor, env: dict[str, Value]) -> UnionValue:
        resolved = resolve_named_value_type(RecordType(expr.type_name))
        if not isinstance(resolved, UnionType) or resolved.name not in self.unions:
            raise InterpreterError(f"unknown union type {expr.type_name}", expr.line)
        union = self.unions[resolved.name]
        variant = union.variants[expr.variant_name]
        inits = {field.name: field for field in expr.fields}
        fields: dict[str, Value] = {}
        for payload in variant.payload_fields:
            init = inits[payload.name]
            fields[payload.name] = self._eval_expr(init.expr, env, expected=payload.type_name)
        return UnionValue(UnionType(union.name), variant.name, fields)

    def _eval_cast(self, expr: Cast, env: dict[str, Value]) -> Value:
        target_type = infer_cast_type(expr, self._env_types(env), self.functions, self.records)
        source = self._eval_expr(expr.expr, env, expected=target_type.underlying_type if isinstance(target_type, EnumType) and isinstance(expr.expr, Integer) else None)
        if isinstance(target_type, EnumType):
            if isinstance(source, EnumValue):
                return EnumValue(target_type, source.underlying_value)
            if isinstance(source, IntValue):
                return EnumValue(target_type, normalize_integer(source.value, target_type.underlying_type))
            raise InterpreterError(f"cannot cast {format_type(self._value_type(source))} to {format_type(target_type)}", expr.line)
        if not isinstance(target_type, str):
            raise InterpreterError(f"interpreter does not support cast to {format_type(target_type)} in v0.48", expr.line)
        source_type = self._value_type(source)
        if isinstance(source, EnumValue):
            source_scalar_type = source.type_name.underlying_type
            value = source.underlying_value
        else:
            source_scalar_type = source_type
            value = self._scalar_value(source)
        if not isinstance(source_scalar_type, str):
            raise InterpreterError(f"cannot cast {format_type(source_type)} to {target_type}", expr.line)
        casted = cast_const_value(value, source_scalar_type, target_type)
        if is_float_type(target_type):
            return FloatValue(target_type, float(casted))
        if target_type == "i1":
            return BoolValue("i1", bool(casted))
        return IntValue(target_type, int(casted))

    def _eval_unary(self, expr: Unary, env: dict[str, Value]) -> Value:
        if expr.op == "not":
            return BoolValue("i1", not self._eval_i1(expr.expr, env))
        operand = self._eval_expr(expr.expr, env)
        if not isinstance(operand, IntValue):
            raise InterpreterError(f"bitwise not requires integer operand, got {format_type(self._value_type(operand))}", expr.line)
        return IntValue(operand.type_name, normalize_integer(~to_bits(operand.value, operand.type_name), operand.type_name))

    def _eval_binary(self, expr: Binary, env: dict[str, Value], *, expected: ValueType | None = None) -> Value:
        if expr.op in {"and", "or"}:
            if expr.op == "and":
                return BoolValue("i1", self._eval_i1(expr.left, env) and self._eval_i1(expr.right, env))
            return BoolValue("i1", self._eval_i1(expr.left, env) or self._eval_i1(expr.right, env))
        type_name = infer_expr_type(expr, self._env_types(env), self.functions, self.records, expected=expected, constants=self.constants)
        assert isinstance(type_name, str)
        left = self._eval_expr(expr.left, env, expected=type_name)
        right = self._eval_expr(expr.right, env, expected=type_name)
        value = evaluate_numeric_binary(expr.op, self._scalar_value(left), self._scalar_value(right), type_name, expr.line)
        if is_float_type(type_name):
            return FloatValue(type_name, float(value))
        return IntValue(type_name, int(value))

    def _eval_comparison(self, expr: Comparison, env: dict[str, Value]) -> BoolValue:
        operand_type = infer_comparison_operand_type(expr, self._env_types(env), self.functions, self.records)
        left = self._eval_expr(expr.left, env, expected=operand_type)
        right = self._eval_expr(expr.right, env, expected=operand_type)
        return BoolValue("i1", evaluate_comparison(expr.pred, self._scalar_value(left), self._scalar_value(right), operand_type))

    def _eval_match_expr(self, expr: MatchExpr, env: dict[str, Value], *, expected: ValueType | None = None) -> Value:
        result_type = infer_expr_type(expr, self._env_types(env), self.functions, self.records, expected=expected, constants=self.constants)
        scrutinee = self._eval_expr(expr.scrutinee, env)
        for arm in expr.arms:
            matched, bindings = self._match_pattern(arm.pattern, scrutinee, env)
            if not matched:
                continue
            scoped = {**env, **bindings}
            if arm.guard is not None and not self._eval_i1(arm.guard, scoped):
                continue
            return self._eval_expr(arm.expr, scoped, expected=result_type)
        if expr.otherwise is not None:
            return self._eval_expr(expr.otherwise, env, expected=result_type)
        if expr.arms:
            return self._eval_expr(expr.arms[-1].expr, env, expected=result_type)
        raise InterpreterError("match expression has no arms", expr.line)

    def _match_pattern(self, pattern: object, scrutinee: Value, env: dict[str, Value]) -> tuple[bool, dict[str, Value]]:
        if isinstance(pattern, AnythingPattern):
            return True, {}
        if isinstance(pattern, AlternativePattern):
            for alternative in pattern.alternatives:
                matched, bindings = self._match_pattern(alternative, scrutinee, env)
                if matched:
                    return True, bindings
            return False, {}
        if isinstance(pattern, RangePattern):
            scrutinee_type = storage_type(self._value_type(scrutinee))
            if not isinstance(scrutinee_type, str) or not is_integer_type(scrutinee_type):
                raise InterpreterError(f"range patterns require integer scalar scrutinee, got {format_type(self._value_type(scrutinee))}", pattern.line)
            lower = self._eval_expr(pattern.lower, env, expected=scrutinee_type)
            upper = self._eval_expr(pattern.upper, env, expected=scrutinee_type)
            value = self._integer_compare_value(int(self._scalar_value(scrutinee)), scrutinee_type)
            return self._integer_compare_value(int(self._scalar_value(lower)), scrutinee_type) <= value <= self._integer_compare_value(int(self._scalar_value(upper)), scrutinee_type), {}
        if isinstance(pattern, UnionPattern):
            if not isinstance(scrutinee, UnionValue):
                return False, {}
            if scrutinee.type_name.name != pattern.type_name or scrutinee.variant_name != pattern.variant_name:
                return False, {}
            union = self.unions[scrutinee.type_name.name]
            variant = union.variants[pattern.variant_name]
            bindings: dict[str, Value] = {}
            for binding, payload in zip(pattern.bindings, variant.payload_fields, strict=True):
                if binding.ignored:
                    continue
                bindings[binding.alias_name or binding.field_name] = scrutinee.fields[payload.name]
            return True, bindings
        if isinstance(pattern, (Integer, Float, Boolean, EnumCase, Variable, FieldAccess, ByteLiteral, Cast, Binary, Unary, Comparison, WhenExpr, MatchExpr, Call, UnionConstructor, RecordConstructor, LengthOfBytes)):
            value = self._eval_expr(pattern, env, expected=self._value_type(scrutinee))
            return self._values_equal(scrutinee, value), {}
        return False, {}

    def _eval_i1(self, expr: Expr, env: dict[str, Value]) -> bool:
        value = self._eval_expr(expr, env, expected="i1")
        if not isinstance(value, BoolValue):
            raise InterpreterError(f"interpreter expected i1 condition, got {format_type(self._value_type(value))}", getattr(expr, "line", None))
        return value.value

    def _int_for_loop_bound(self, expr: Expr, env: dict[str, Value]) -> int:
        value = self._eval_expr(expr, env)
        if not isinstance(value, IntValue):
            raise InterpreterError(f"interpreter for loop bound must be integer, got {format_type(self._value_type(value))}", getattr(expr, "line", None))
        return int(value.value)

    def _env_types(self, env: dict[str, Value]) -> dict[str, ValueType]:
        return {name: self._value_type(value) for name, value in env.items()}

    def _value_from_const(self, value: ConstValue) -> Value:
        if value.type_name == "i1":
            return BoolValue("i1", bool(value.value))
        if isinstance(value.type_name, EnumType):
            return EnumValue(value.type_name, int(value.value))
        if is_float_type(value.type_name):
            assert isinstance(value.type_name, str)
            return FloatValue(value.type_name, float(value.value))
        if is_integer_type(value.type_name):
            assert isinstance(value.type_name, str)
            return IntValue(value.type_name, int(value.value))
        raise InterpreterError(f"interpreter does not support constant type {format_type(value.type_name)} in v0.48")

    def _coerce_argument(self, arg: Value | int | bool | float, expected: ValueType, name: str) -> Value:
        expected = resolve_named_value_type(expected)
        if isinstance(arg, BoolValue | IntValue | FloatValue | EnumValue | RecordValue | UnionValue):
            self._require_value_type(arg, expected, None, binding_name=name)
            return arg
        if expected == "i1":
            if not isinstance(arg, bool):
                raise InterpreterError(f"interpreter expected i1 argument for {name}, got {type(arg).__name__}")
            return BoolValue("i1", arg)
        if isinstance(expected, str) and is_integer_type(expected):
            if isinstance(arg, bool) or not isinstance(arg, int):
                raise InterpreterError(f"interpreter expected {expected} argument for {name}, got {type(arg).__name__}")
            return IntValue(expected, normalize_integer(arg, expected))
        if isinstance(expected, str) and is_float_type(expected):
            if not isinstance(arg, int | float) or isinstance(arg, bool):
                raise InterpreterError(f"interpreter expected {expected} argument for {name}, got {type(arg).__name__}")
            return FloatValue(expected, normalize_float(float(arg), expected))
        raise InterpreterError(f"interpreter expected {format_type(expected)} argument for {name}, got {type(arg).__name__}")

    def _require_supported_type(self, type_name: ValueType | None, role: str, line: int | None) -> None:
        if type_name is None:
            return
        resolved = resolve_named_value_type(type_name)
        if isinstance(resolved, str) and (is_integer_type(resolved) or is_float_type(resolved) or resolved == "i1"):
            return
        if isinstance(resolved, EnumType | RecordType | UnionType):
            return
        if isinstance(resolved, ArrayType):
            raise InterpreterError(f"interpreter does not support arrays in v0.48", line)
        if isinstance(resolved, BufferType):
            raise InterpreterError(f"interpreter does not support buffers in v0.48", line)
        if isinstance(resolved, ViewType):
            raise InterpreterError(f"interpreter does not support views in v0.48", line)
        if isinstance(resolved, OwnedBufferType):
            raise InterpreterError(f"interpreter does not support owned buffers in v0.48", line)
        raise InterpreterError(f"interpreter does not support {role} {format_type(resolved)} in v0.48", line)

    def _require_value_type(self, value: Value, expected: ValueType, line: int | None, *, binding_name: str | None = None) -> None:
        expected = resolve_named_value_type(expected)
        actual = self._value_type(value)
        if actual != expected:
            if binding_name is None:
                raise InterpreterError(f"interpreter expected {format_type(expected)}, got {format_type(actual)}", line)
            raise InterpreterError(f"interpreter expected {format_type(expected)} argument for {binding_name}, got {format_type(actual)}", line)

    def _value_type(self, value: Value) -> ValueType:
        if isinstance(value, BoolValue | IntValue | FloatValue):
            return value.type_name
        if isinstance(value, EnumValue):
            return value.type_name
        if isinstance(value, RecordValue):
            return value.type_name
        if isinstance(value, UnionValue):
            return value.type_name
        raise AssertionError(value)

    def _scalar_value(self, value: Value) -> int | bool | float:
        if isinstance(value, BoolValue):
            return value.value
        if isinstance(value, IntValue):
            return value.value
        if isinstance(value, FloatValue):
            return value.value
        if isinstance(value, EnumValue):
            return value.underlying_value
        raise InterpreterError(f"interpreter expected scalar value, got {format_type(self._value_type(value))}")

    def _values_equal(self, left: Value, right: Value) -> bool:
        if self._value_type(left) != self._value_type(right):
            return False
        if isinstance(left, RecordValue) and isinstance(right, RecordValue):
            return left.fields.keys() == right.fields.keys() and all(self._values_equal(left.fields[name], right.fields[name]) for name in left.fields)
        if isinstance(left, UnionValue) and isinstance(right, UnionValue):
            return left.variant_name == right.variant_name and left.fields.keys() == right.fields.keys() and all(self._values_equal(left.fields[name], right.fields[name]) for name in left.fields)
        return self._scalar_value(left) == self._scalar_value(right)

    def _integer_compare_value(self, value: int, type_name: TypeName) -> int:
        return int(value) if type_name.startswith("i") else to_bits(int(value), type_name)


def interpret_phrase(program: Program, phrase_name_or_symbol: str, args: list[Value | int | bool | float] | tuple[Value | int | bool | float, ...] = (), *, step_limit: int = 100_000) -> Value:
    return Interpreter(program, step_limit=step_limit).call_phrase(phrase_name_or_symbol, args)
