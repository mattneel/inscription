from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .ast import (
    ArrayBinding,
    ArrayType,
    AssignStmt,
    Binary,
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
    ConstantDecl,
    EnumCase,
    EnumDecl,
    Expr,
    FieldAccess,
    FieldAssignStmt,
    Float,
    ForEachStmt,
    ForStmt,
    Function,
    IfStmt,
    ImportDecl,
    Integer,
    AlignmentOfType,
    LengthOf,
    LayoutRead,
    LayoutWriteStmt,
    MatchExpr,
    MatchExprArm,
    MatchStep,
    MatchStepArm,
    OffsetOfField,
    Parameter,
    Program,
    RecordConstructor,
    RecordDecl,
    RecordFieldDecl,
    RecordFieldInit,
    RecordType,
    RequireStmt,
    ReturnStmt,
    SetStmt,
    SizeOfType,
    Stmt,
    Unary,
    ValueType,
    Variable,
    ViewBinding,
    ViewType,
    WhenCase,
    WhenExpr,
    WhileStmt,
)
from .diagnostics import InscriptionError
from .mlir import emit_mlir
from .parser import Parser, PhrasePart, PhraseTemplate, parse_source

MODULE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*")


def compile_source(
    source: str,
    *,
    source_path: Path | None = None,
    module_root: Path | None = None,
    runtime_checks: bool = False,
) -> str:
    return emit_mlir(load_program(source, source_path=source_path, module_root=module_root), runtime_checks=runtime_checks)


def load_program(
    source: str,
    *,
    source_path: Path | None = None,
    module_root: Path | None = None,
) -> Program:
    if source_path is None and module_root is None and not _source_has_imports(source):
        return parse_source(source)
    resolver = ModuleResolver(module_root or (source_path.parent if source_path is not None else None))
    return resolver.load_entry(source, source_path=source_path)


def compile_file(source_path: Path, *, module_root: Path | None = None, runtime_checks: bool = False) -> str:
    source_path = source_path.resolve()
    return compile_source(
        source_path.read_text(), source_path=source_path, module_root=module_root, runtime_checks=runtime_checks
    )


@dataclass(frozen=True)
class LoadedModule:
    name: str
    path: Path
    program: Program
    exported_templates: tuple[PhraseTemplate, ...]


@dataclass(frozen=True)
class LoadedCompilation:
    program: Program
    root_program: Program
    root_path: Path | None
    module_root: Path | None
    modules: tuple[LoadedModule, ...]


class ModuleResolver:
    def __init__(self, module_root: Path | None):
        self.module_root = module_root.resolve() if module_root is not None else None
        self.cache: dict[str, LoadedModule] = {}
        self.order: list[str] = []

    def load_entry(self, source: str, *, source_path: Path | None = None) -> Program:
        return self.load_entry_compilation(source, source_path=source_path).program

    def load_entry_compilation(self, source: str, *, source_path: Path | None = None) -> LoadedCompilation:
        module_name, imports = scan_module_header(source)
        if imports and self.module_root is None:
            raise InscriptionError("imports require a source path or --module-root", imports[0].line)
        dependencies = [self.load_module(import_decl.module, stack=()) for import_decl in imports]
        external_templates = tuple(template for dep in dependencies for template in dep.exported_templates)
        entry = Parser(source, external_phrases=external_templates).parse_program()
        if entry.module_name != module_name:
            raise AssertionError("module scan and parser disagree")  # pragma: no cover
        modules = [self.cache[name] for name in self.order]
        return LoadedCompilation(
            combine_programs(modules, entry),
            entry,
            source_path.resolve() if source_path is not None else None,
            self.module_root,
            tuple(modules),
        )

    def load_module(self, name: str, *, stack: tuple[str, ...]) -> LoadedModule:
        if name in self.cache:
            return self.cache[name]
        if name in stack:
            cycle = " -> ".join((*stack, name))
            raise InscriptionError(f"import cycle detected: {cycle}")
        if self.module_root is None:
            raise InscriptionError("imports require a source path or --module-root")
        path = module_path(self.module_root, name)
        if not path.exists():
            raise InscriptionError(f"module {name} not found at {path}")
        source = path.read_text()
        declared_module, imports = scan_module_header(source)
        if declared_module is None:
            raise InscriptionError(f"imported file {path} must declare module {name}")
        if declared_module != name:
            raise InscriptionError(f"module declaration {declared_module} does not match import {name}")
        dependencies = [self.load_module(import_decl.module, stack=(*stack, name)) for import_decl in imports]
        external_templates = tuple(template for dep in dependencies for template in dep.exported_templates)
        symbol_prefix = module_symbol(name)
        parser = Parser(source, external_phrases=external_templates, symbol_prefix=symbol_prefix)
        parsed = parser.parse_program()
        if parsed.module_name != name:
            raise InscriptionError(f"module declaration {parsed.module_name} does not match import {name}")
        program = qualify_imported_program(parsed, name)
        exported_templates = tuple(prefix_template_for_import(template, name) for template in parser.local_phrases)
        loaded = LoadedModule(name, path, program, exported_templates)
        self.cache[name] = loaded
        self.order.append(name)
        return loaded


def load_compilation(
    source: str,
    *,
    source_path: Path | None = None,
    module_root: Path | None = None,
) -> LoadedCompilation:
    resolver = ModuleResolver(module_root or (source_path.parent if source_path is not None else None))
    return resolver.load_entry_compilation(source, source_path=source_path)


def _source_has_imports(source: str) -> bool:
    _module_name, imports = scan_module_header(source)
    return bool(imports)


def scan_module_header(source: str) -> tuple[str | None, tuple[ImportDecl, ...]]:
    module_name: str | None = None
    imports: list[ImportDecl] = []
    for number, raw in enumerate(source.splitlines(), start=1):
        indent = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()
        if not text or indent != 0:
            continue
        if text.endswith(":"):
            text = text[:-1].strip()
        if text.startswith("module "):
            if module_name is not None:
                raise InscriptionError("program can declare only one module", number)
            module_name = validate_module_name(text[len("module ") :].strip(), number)
        elif text.startswith("import "):
            imports.append(ImportDecl(validate_module_name(text[len("import ") :].strip(), number), number))
    seen: set[str] = set()
    for imported in imports:
        if imported.module in seen:
            raise InscriptionError(f"module {imported.module} is already imported", imported.line)
        seen.add(imported.module)
    return module_name, tuple(imports)


def validate_module_name(name: str, line: int = 0) -> str:
    if not MODULE_RE.fullmatch(name):
        raise InscriptionError(f"invalid module name '{name}'", line or None)
    return name


def module_path(module_root: Path, name: str) -> Path:
    return module_root.joinpath(*name.split(".")).with_suffix(".ins")


def module_symbol(name: str) -> str:
    return "__".join(name.split("."))


def prefix_template_for_import(template: PhraseTemplate, module_name: str) -> PhraseTemplate:
    prefix_parts: list[PhrasePart] = []
    for index, part in enumerate(module_name.split(".")):
        if index:
            prefix_parts.append(".")
        prefix_parts.append(part)
    prefix_parts.append(".")
    parts = tuple((*prefix_parts, *template.parts))
    display_name = f"{module_name}.{template.display_name}"
    return PhraseTemplate(template.symbol, parts, template.params, template.line, template.return_type, display_name)


def combine_programs(modules: list[LoadedModule], entry: Program) -> Program:
    records: list[RecordDecl] = []
    enums: list[EnumDecl] = []
    constants: list[ConstantDecl] = []
    checks: list[CheckStmt] = []
    functions: list[Function] = []
    for module in modules:
        records.extend(module.program.records)
        enums.extend(module.program.enums)
        constants.extend(module.program.constants)
        checks.extend(module.program.checks)
        functions.extend(module.program.functions)
    records.extend(entry.records)
    enums.extend(entry.enums)
    constants.extend(entry.constants)
    checks.extend(entry.checks)
    functions.extend(entry.functions)
    return Program(tuple(records), tuple(enums), tuple(constants), tuple(checks), tuple(functions), entry.module_name, entry.imports)


def qualify_imported_program(program: Program, module_name: str) -> Program:
    record_names = {record.name for record in program.records}
    enum_names = {enum.name for enum in program.enums}
    type_names = record_names | enum_names
    constant_names = {constant.name for constant in program.constants}
    records = tuple(qualify_record_decl(record, module_name, type_names) for record in program.records)
    enums = tuple(qualify_enum_decl(enum, module_name, type_names, constant_names) for enum in program.enums)
    constants = tuple(qualify_constant(constant, module_name, type_names, constant_names) for constant in program.constants)
    checks = tuple(qualify_stmt(check, module_name, type_names, constant_names) for check in program.checks)
    functions = tuple(qualify_function(function, module_name, type_names, constant_names) for function in program.functions)
    return Program(records, enums, constants, checks, functions, program.module_name, program.imports)


def qname(module_name: str, name: str) -> str:
    return f"{module_name}.{name}"


def qualify_record_decl(record: RecordDecl, module_name: str, record_names: set[str]) -> RecordDecl:
    return RecordDecl(
        qname(module_name, record.name),
        tuple(
            RecordFieldDecl(field.name, qualify_type(field.type_name, module_name, record_names, set()), field.line)
            for field in record.fields
        ),
        record.line,
        record.layout_kind,
        record.layout_info,
    )


def qualify_enum_decl(enum: EnumDecl, module_name: str, type_names: set[str], constant_names: set[str]) -> EnumDecl:
    return EnumDecl(
        qname(module_name, enum.name),
        enum.underlying_type,
        tuple(type(case)(case.name, qualify_expr(case.value, module_name, type_names, constant_names), case.line) for case in enum.cases),
        enum.line,
    )


def qualify_constant(
    constant: ConstantDecl,
    module_name: str,
    record_names: set[str],
    constant_names: set[str],
) -> ConstantDecl:
    return ConstantDecl(
        qname(module_name, constant.name),
        qualify_type(constant.type_name, module_name, record_names, constant_names),
        qualify_expr(constant.expr, module_name, record_names, constant_names),
        constant.line,
    )


def qualify_function(
    function: Function,
    module_name: str,
    record_names: set[str],
    constant_names: set[str],
) -> Function:
    return Function(
        function.name,
        tuple(Parameter(param.name, qualify_type(param.type_name, module_name, record_names, constant_names)) for param in function.params),
        qualify_return_type(function.return_type, module_name, record_names),
        tuple(qualify_stmt(stmt, module_name, record_names, constant_names) for stmt in function.body),
        function.line,
        function.display_name,
        function.extern_symbol,
        function.implementation,
    )


def qualify_type(type_name: ValueType, module_name: str, record_names: set[str], constant_names: set[str]) -> ValueType:
    if isinstance(type_name, BufferType):
        return BufferType(qualify_buffer_length(type_name.length, module_name, record_names, constant_names), qualify_type(type_name.element_type, module_name, record_names, constant_names))
    if isinstance(type_name, ArrayType):
        return ArrayType(qualify_buffer_length(type_name.length, module_name, record_names, constant_names), qualify_type(type_name.element_type, module_name, record_names, constant_names))
    if isinstance(type_name, ViewType):
        return ViewType(qualify_type(type_name.element_type, module_name, record_names, constant_names), type_name.length)
    if isinstance(type_name, RecordType) and type_name.name in record_names:
        return RecordType(qname(module_name, type_name.name))
    return type_name


def qualify_return_type(type_name, module_name: str, record_names: set[str]):
    if isinstance(type_name, ArrayType):
        return ArrayType(qualify_buffer_length(type_name.length, module_name, record_names, set()), qualify_return_type(type_name.element_type, module_name, record_names))
    if isinstance(type_name, ViewType):
        return ViewType(qualify_return_type(type_name.element_type, module_name, record_names), type_name.length)
    if isinstance(type_name, RecordType) and type_name.name in record_names:
        return RecordType(qname(module_name, type_name.name))
    return type_name


def qualify_buffer_length(length, module_name: str, record_names: set[str], constant_names: set[str]):
    if isinstance(length, int):
        return length
    return qualify_expr(length, module_name, record_names, constant_names)


def qualify_stmt(stmt: Stmt, module_name: str, record_names: set[str], constant_names: set[str]):
    if isinstance(stmt, CheckStmt):
        return CheckStmt(qualify_expr(stmt.expr, module_name, record_names, constant_names), stmt.line)
    if isinstance(stmt, RequireStmt):
        return RequireStmt(qualify_expr(stmt.expr, module_name, record_names, constant_names), stmt.line)
    if isinstance(stmt, SetStmt):
        type_name = qualify_type(stmt.type_name, module_name, record_names, constant_names) if stmt.type_name is not None else None
        return SetStmt(stmt.name, type_name, qualify_expr(stmt.expr, module_name, record_names, constant_names), stmt.line)
    if isinstance(stmt, BufferBinding):
        buffer_type = qualify_type(stmt.buffer_type, module_name, record_names, constant_names)
        assert isinstance(buffer_type, BufferType)
        fill = qualify_expr(stmt.fill, module_name, record_names, constant_names) if stmt.fill is not None else None
        values = tuple(qualify_expr(value, module_name, record_names, constant_names) for value in stmt.values)
        return BufferBinding(stmt.name, buffer_type, stmt.line, fill, values)
    if isinstance(stmt, ArrayBinding):
        array_type = qualify_type(stmt.array_type, module_name, record_names, constant_names)
        assert isinstance(array_type, ArrayType)
        fill = qualify_expr(stmt.fill, module_name, record_names, constant_names) if stmt.fill is not None else None
        values = tuple(qualify_expr(value, module_name, record_names, constant_names) for value in stmt.values)
        return ArrayBinding(stmt.name, array_type, stmt.line, fill, values)
    if isinstance(stmt, ViewBinding):
        return ViewBinding(
            stmt.name,
            stmt.source_name,
            qualify_expr(stmt.start, module_name, record_names, constant_names),
            qualify_expr(stmt.count, module_name, record_names, constant_names),
            stmt.line,
        )
    if isinstance(stmt, AssignStmt):
        return AssignStmt(stmt.name, qualify_expr(stmt.expr, module_name, record_names, constant_names), stmt.line)
    if isinstance(stmt, BufferStoreStmt):
        return BufferStoreStmt(
            stmt.name,
            qualify_expr(stmt.index, module_name, record_names, constant_names),
            qualify_expr(stmt.value, module_name, record_names, constant_names),
            stmt.line,
        )
    if isinstance(stmt, FieldAssignStmt):
        return FieldAssignStmt(stmt.name, stmt.field, qualify_expr(stmt.expr, module_name, record_names, constant_names), stmt.line)
    if isinstance(stmt, LayoutWriteStmt):
        return LayoutWriteStmt(stmt.record_name, stmt.buffer_name, qualify_expr(stmt.index, module_name, record_names, constant_names), stmt.line)
    if isinstance(stmt, CallStmt):
        return CallStmt(qualify_expr(stmt.call, module_name, record_names, constant_names), stmt.line)
    if isinstance(stmt, WhileStmt):
        return WhileStmt(qualify_expr(stmt.condition, module_name, record_names, constant_names), tuple(qualify_stmt(s, module_name, record_names, constant_names) for s in stmt.body), stmt.line)
    if isinstance(stmt, ForStmt):
        return ForStmt(stmt.name, qualify_expr(stmt.start, module_name, record_names, constant_names), qualify_expr(stmt.end, module_name, record_names, constant_names), stmt.step, tuple(qualify_stmt(s, module_name, record_names, constant_names) for s in stmt.body), stmt.line)
    if isinstance(stmt, ForEachStmt):
        return ForEachStmt(stmt.name, stmt.buffer_name, tuple(qualify_stmt(s, module_name, record_names, constant_names) for s in stmt.body), stmt.line)
    if isinstance(stmt, IfStmt):
        return IfStmt(
            qualify_expr(stmt.condition, module_name, record_names, constant_names),
            tuple(qualify_stmt(s, module_name, record_names, constant_names) for s in stmt.then_body),
            tuple(qualify_stmt(s, module_name, record_names, constant_names) for s in stmt.else_body),
            stmt.line,
        )
    if isinstance(stmt, MatchStep):
        return MatchStep(
            qualify_expr(stmt.scrutinee, module_name, record_names, constant_names),
            tuple(
                MatchStepArm(
                    qualify_expr(arm.pattern, module_name, record_names, constant_names),
                    tuple(qualify_stmt(s, module_name, record_names, constant_names) for s in arm.body),
                    arm.line,
                )
                for arm in stmt.arms
            ),
            tuple(qualify_stmt(s, module_name, record_names, constant_names) for s in stmt.otherwise_body),
            stmt.line,
        )
    if isinstance(stmt, ReturnStmt):
        return ReturnStmt(qualify_expr(stmt.expr, module_name, record_names, constant_names), stmt.line)
    raise AssertionError(stmt)  # pragma: no cover


def qualify_expr(expr: Expr, module_name: str, record_names: set[str], constant_names: set[str]) -> Expr:
    if isinstance(expr, Integer | Float | Boolean):
        return expr
    if isinstance(expr, Variable):
        if expr.name in constant_names:
            return Variable(qname(module_name, expr.name), expr.line)
        return expr
    if isinstance(expr, BufferLoad):
        return BufferLoad(expr.name, qualify_expr(expr.index, module_name, record_names, constant_names), expr.line)
    if isinstance(expr, LengthOf):
        return expr
    if isinstance(expr, SizeOfType):
        return SizeOfType(qname(module_name, expr.type_name) if expr.type_name in record_names else expr.type_name, expr.line)
    if isinstance(expr, AlignmentOfType):
        return AlignmentOfType(qname(module_name, expr.type_name) if expr.type_name in record_names else expr.type_name, expr.line)
    if isinstance(expr, OffsetOfField):
        return OffsetOfField(expr.field, qname(module_name, expr.type_name) if expr.type_name in record_names else expr.type_name, expr.line)
    if isinstance(expr, FieldAccess):
        return expr
    if isinstance(expr, EnumCase):
        parts = expr.type_name.split(".")
        if len(parts) == 1 and expr.type_name in record_names:
            return EnumCase(qname(module_name, expr.type_name), expr.case_name, expr.line)
        return expr
    if isinstance(expr, RecordConstructor):
        return RecordConstructor(
            qname(module_name, expr.type_name) if expr.type_name in record_names else expr.type_name,
            tuple(RecordFieldInit(field.name, qualify_expr(field.expr, module_name, record_names, constant_names), field.line) for field in expr.fields),
            expr.line,
        )
    if isinstance(expr, LayoutRead):
        return LayoutRead(qname(module_name, expr.type_name) if expr.type_name in record_names else expr.type_name, expr.buffer_name, qualify_expr(expr.index, module_name, record_names, constant_names), expr.line)
    if isinstance(expr, Binary):
        return Binary(expr.op, qualify_expr(expr.left, module_name, record_names, constant_names), qualify_expr(expr.right, module_name, record_names, constant_names), expr.line)
    if isinstance(expr, Unary):
        return Unary(expr.op, qualify_expr(expr.expr, module_name, record_names, constant_names), expr.line)
    if isinstance(expr, Cast):
        return Cast(qualify_expr(expr.expr, module_name, record_names, constant_names), qualify_type(expr.target_type, module_name, record_names, constant_names), expr.line)
    if isinstance(expr, Call):
        return Call(expr.name, tuple(qualify_expr(arg, module_name, record_names, constant_names) for arg in expr.args), expr.line)
    if isinstance(expr, Comparison):
        return Comparison(expr.pred, qualify_expr(expr.left, module_name, record_names, constant_names), qualify_expr(expr.right, module_name, record_names, constant_names), expr.line)
    if isinstance(expr, WhenExpr):
        return WhenExpr(
            tuple(WhenCase(qualify_expr(case.expr, module_name, record_names, constant_names), qualify_expr(case.condition, module_name, record_names, constant_names), case.line) for case in expr.cases),
            qualify_expr(expr.otherwise, module_name, record_names, constant_names),
            expr.line,
        )
    if isinstance(expr, MatchExpr):
        return MatchExpr(
            qualify_expr(expr.scrutinee, module_name, record_names, constant_names),
            tuple(
                MatchExprArm(
                    qualify_expr(arm.pattern, module_name, record_names, constant_names),
                    qualify_expr(arm.expr, module_name, record_names, constant_names),
                    arm.line,
                )
                for arm in expr.arms
            ),
            qualify_expr(expr.otherwise, module_name, record_names, constant_names),
            expr.line,
        )
    raise AssertionError(expr)  # pragma: no cover
