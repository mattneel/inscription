from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .ast import (
    AlignmentOfType,
    AlternativePattern,
    AnythingPattern,
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
    ByteLiteral,
    ByteString,
    Call,
    CallStmt,
    Cast,
    CheckStmt,
    Comparison,
    ComptimeExpr,
    ConstantDecl,
    EnumCase,
    EnumDecl,
    ExpectStmt,
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
    RecordConstructor,
    RecordDecl,
    RecordType,
    RangePattern,
    RequireStmt,
    ReturnStmt,
    SetStmt,
    SizeOfType,
    StorageAliasBinding,
    TestDecl,
    TypeAliasDecl,
    Unary,
    UnionConstructor,
    UnionDecl,
    UnionPattern,
    ValueType,
    Variable,
    ViewBinding,
    ViewType,
    WhenExpr,
    WhileStmt,
)
from .buildscript import BUILD_SCRIPT_NAME, BuildScript, load_build_script
from .compiler import LoadedCompilation, LoadedModule, load_compilation, module_path
from .diagnostics import InscriptionError, SourceSpan
from .package import (
    MANIFEST_NAME,
    PackageContext,
    PackageGraph,
    PackageModuleResolver,
    checked_package_graph,
    load_package_compilation,
    package_import_modules,
    package_test_files,
)
from .semantic import analyze, format_type
from .version import SYMBOL_INDEX_FORMAT


@dataclass(frozen=True)
class IndexedFile:
    path: str
    module: str | None = None
    role: str | None = None


@dataclass(frozen=True)
class Symbol:
    id: str
    kind: str
    name: str
    qualified_name: str | None
    module: str | None
    path: str
    span: SourceSpan | None
    documentation: str | None = None
    type: str | None = None
    detail: dict[str, object] | None = None


@dataclass(frozen=True)
class Reference:
    kind: str
    name: str
    target_id: str | None
    path: str
    span: SourceSpan | None
    detail: dict[str, object] | None = None


@dataclass(frozen=True)
class SourceIndex:
    source: str
    package: dict[str, object] | None
    files: tuple[IndexedFile, ...]
    symbols: tuple[Symbol, ...]
    references: tuple[Reference, ...]

    def payload(self, *, include_references: bool = True) -> dict[str, object]:
        out: dict[str, object] = {
            "format": SYMBOL_INDEX_FORMAT,
            "source": self.source,
            "package": self.package,
            "files": [_file_payload(file) for file in self.files],
            "symbols": [_symbol_payload(symbol) for symbol in self.symbols],
        }
        if include_references:
            out["references"] = [_reference_payload(reference) for reference in self.references]
        return out

    def json_text(self, *, pretty: bool = False, include_references: bool = True) -> str:
        indent = 2 if pretty else None
        return json.dumps(self.payload(include_references=include_references), indent=indent, ensure_ascii=False) + "\n"


@dataclass
class _IndexedProgram:
    program: Program
    path: Path
    display_path: str
    source: str
    module: str | None
    role: str


@dataclass
class _IndexState:
    base: Path | None
    files: list[IndexedFile]
    symbols: list[Symbol]
    references: list[Reference]
    source_by_path: dict[str, str]
    symbol_by_lookup: dict[str, str]
    field_targets: dict[str, str]
    build_step_targets: dict[str, str]

    def add_file(self, path: str, *, module: str | None, role: str | None) -> None:
        item = IndexedFile(path, module, role)
        if item not in self.files:
            self.files.append(item)

    def add_symbol(
        self,
        kind: str,
        name: str,
        qualified_name: str | None,
        module: str | None,
        path: str,
        line: int | None,
        *,
        documentation: str | None = None,
        type_text: str | None = None,
        detail: dict[str, object] | None = None,
        lookup_names: Iterable[str] = (),
    ) -> Symbol:
        source = self.source_by_path.get(path)
        resolved_line = _resolve_symbol_line(kind, name, line, source)
        span = _span_for_line(path, resolved_line, source) if resolved_line is not None else None
        symbol_id = _symbol_id(kind, qualified_name or name, path, resolved_line)
        symbol = Symbol(symbol_id, kind, name, qualified_name, module, path, span, documentation, type_text, detail or {})
        self.symbols.append(symbol)
        for lookup in _lookup_keys(kind, name, qualified_name, lookup_names):
            self.symbol_by_lookup.setdefault(lookup, symbol_id)
        return symbol

    def add_reference(
        self,
        kind: str,
        name: str,
        target_id: str | None,
        path: str,
        line: int | None,
        *,
        detail: dict[str, object] | None = None,
    ) -> None:
        span = _span_for_line(path, line, self.source_by_path.get(path)) if line is not None else None
        self.references.append(Reference(kind, name, target_id, path, span, detail or {}))


def build_source_index(source_path: Path, *, module_root: Path | None = None) -> SourceIndex:
    """Build a deterministic symbol/reference index for a single source entry."""

    source_path = source_path.resolve()
    source = source_path.read_text()
    try:
        compilation = load_compilation(source, source_path=source_path, module_root=module_root)
        analyze(compilation.program)
    except InscriptionError as exc:
        raise exc.attach_source(source, source_path) from exc
    base = Path.cwd().resolve()
    programs = _programs_from_compilation(compilation, base=base, role="source")
    state = _new_state(base)
    for indexed in programs:
        _register_program_file(state, indexed)
    for indexed in programs:
        _index_program_symbols(state, indexed)
    _finalize_field_targets(state)
    for indexed in programs:
        _index_program_references(state, indexed)
    return SourceIndex(_display_path(source_path, base), None, tuple(state.files), tuple(state.symbols), tuple(state.references))


def build_package_source_index(root: Path, *, include_dependencies: bool = False) -> SourceIndex:
    """Build a deterministic package-aware source index."""

    graph = checked_package_graph(root, verify=False)
    base = graph.root.root
    state = _new_state(base)
    contexts = graph.packages if include_dependencies else (graph.root,)
    for context in contexts:
        _index_package_manifest_symbols(state, context)
    package_programs: list[_IndexedProgram] = []
    test_programs: list[_IndexedProgram] = []
    for context in contexts:
        package_programs.extend(_load_package_programs(context, graph, base=base))
        test_programs.extend(_load_test_programs(context, graph, base=base))
    for indexed in (*package_programs, *test_programs):
        _register_program_file(state, indexed)
    for indexed in package_programs:
        _index_program_symbols(state, indexed)
    for indexed in test_programs:
        _index_program_symbols(state, indexed)
    _finalize_field_targets(state)
    for context in contexts:
        _index_build_script_symbols(state, context)
    for context in contexts:
        _index_package_manifest_references(state, context)
    for indexed in (*package_programs, *test_programs):
        _index_program_references(state, indexed)
    for context in contexts:
        _index_build_script_references(state, context)
    manifest = graph.root.manifest
    package_payload: dict[str, object] = {
        "name": manifest.package_name,
        "version": manifest.version,
        "root": ".",
    }
    return SourceIndex(MANIFEST_NAME, package_payload, tuple(state.files), tuple(state.symbols), tuple(state.references))


def _new_state(base: Path | None) -> _IndexState:
    return _IndexState(base, [], [], [], {}, {}, {}, {})


def _programs_from_compilation(compilation: LoadedCompilation, *, base: Path, role: str) -> tuple[_IndexedProgram, ...]:
    programs: list[_IndexedProgram] = []
    for module in compilation.modules:
        programs.append(_indexed_loaded_module(module, base=base, role="source"))
    if compilation.root_path is not None:
        display = _display_path(compilation.root_path, base)
        source = compilation.root_path.read_text()
        programs.append(_IndexedProgram(compilation.root_program, compilation.root_path, display, source, compilation.root_program.module_name, role))
    return tuple(programs)


def _indexed_loaded_module(module: LoadedModule, *, base: Path, role: str) -> _IndexedProgram:
    path = module.path.resolve()
    return _IndexedProgram(module.program, path, _display_path(path, base), path.read_text(), module.program.module_name, role)


def _load_package_programs(context: PackageContext, graph: PackageGraph, *, base: Path) -> tuple[_IndexedProgram, ...]:
    try:
        compilation = load_package_compilation(context, graph)
        analyze(compilation.program)
    except InscriptionError as exc:
        raise exc
    programs: list[_IndexedProgram] = []
    source_root = context.sources_dir.resolve()
    for module in compilation.modules:
        path = module.path.resolve()
        try:
            path.relative_to(source_root)
        except ValueError:
            continue
        programs.append(_indexed_loaded_module(module, base=base, role="source"))
    return tuple(programs)


def _load_test_programs(context: PackageContext, graph: PackageGraph, *, base: Path) -> tuple[_IndexedProgram, ...]:
    programs: list[_IndexedProgram] = []
    for path in package_test_files(context):
        resolver = PackageModuleResolver(graph, context)
        source = path.read_text()
        try:
            compilation = load_compilation(source, source_path=path, module_root=context.sources_dir, module_path_resolver=resolver)
            analyze(compilation.program)
        except InscriptionError as exc:
            raise exc.attach_source(source, path) from exc
        programs.append(
            _IndexedProgram(
                compilation.root_program,
                path.resolve(),
                _display_path(path.resolve(), base),
                source,
                compilation.root_program.module_name,
                "test",
            )
        )
    return tuple(programs)


def _register_program_file(state: _IndexState, indexed: _IndexedProgram) -> None:
    state.source_by_path[indexed.display_path] = indexed.source
    state.add_file(indexed.display_path, module=indexed.module, role=indexed.role)


def _index_program_symbols(state: _IndexState, indexed: _IndexedProgram) -> None:
    program = indexed.program
    path = indexed.display_path
    module = program.module_name
    if module is not None:
        state.add_symbol("module", _display_module_name(module), module, module, path, _module_line(program), documentation=program.documentation)
    for alias in program.type_aliases:
        qn = _qualified_type_name(module, alias.name)
        state.add_symbol(
            "type_alias",
            _simple_name(alias.name),
            qn,
            module,
            path,
            alias.line,
            documentation=alias.documentation,
            type_text=_type_text(alias.target),
            detail={"target": _type_text(alias.target)},
            lookup_names=(alias.name, _simple_name(alias.name)),
        )
    for record in program.records:
        record_kind = {"value": "record", "natural": "layout_record", "packed": "packed_layout_record"}[record.layout_kind]
        qn = _qualified_type_name(module, record.name)
        detail: dict[str, object] = {"layout": record.layout_kind}
        if record.layout_info is not None:
            detail.update(
                {
                    "size": record.layout_info.size,
                    "alignment": record.layout_info.alignment,
                    "field_offsets": dict(sorted(record.layout_info.field_offsets.items())),
                }
            )
        state.add_symbol(
            record_kind,
            _simple_name(record.name),
            qn,
            module,
            path,
            record.line,
            documentation=record.documentation,
            detail=detail,
            lookup_names=(record.name, _simple_name(record.name)),
        )
        for field in record.fields:
            field_qn = f"{qn}.{field.name}" if qn else f"{record.name}.{field.name}"
            state.add_symbol(
                "record_field",
                field.name,
                field_qn,
                module,
                path,
                field.line,
                type_text=_type_text(field.type_name),
                detail={"record": qn or record.name},
                lookup_names=(field.name, f"{record.name}.{field.name}", field_qn),
            )
    for enum in program.enums:
        qn = _qualified_type_name(module, enum.name)
        state.add_symbol(
            "enum",
            _simple_name(enum.name),
            qn,
            module,
            path,
            enum.line,
            documentation=enum.documentation,
            type_text=_type_text(enum.underlying_type),
            detail={"underlying_type": _type_text(enum.underlying_type)},
            lookup_names=(enum.name, _simple_name(enum.name)),
        )
        for case in enum.cases:
            case_qn = f"{qn}.{case.name}" if qn else f"{enum.name}.{case.name}"
            state.add_symbol(
                "enum_case",
                case.name,
                case_qn,
                module,
                path,
                case.line,
                type_text=qn or enum.name,
                detail={"enum": qn or enum.name},
                lookup_names=(case_qn, f"{enum.name}.{case.name}", case.name),
            )
    for union in program.unions:
        qn = _qualified_type_name(module, union.name)
        state.add_symbol(
            "union",
            _simple_name(union.name),
            qn,
            module,
            path,
            union.line,
            documentation=union.documentation,
            lookup_names=(union.name, _simple_name(union.name)),
        )
        for variant in union.variants:
            variant_qn = f"{qn}.{variant.name}" if qn else f"{union.name}.{variant.name}"
            state.add_symbol(
                "union_variant",
                variant.name,
                variant_qn,
                module,
                path,
                variant.line,
                type_text=qn or union.name,
                detail={"union": qn or union.name},
                lookup_names=(variant_qn, f"{union.name}.{variant.name}", variant.name),
            )
            for payload in variant.payload_fields:
                payload_qn = f"{variant_qn}.{payload.name}"
                state.add_symbol(
                    "union_payload",
                    payload.name,
                    payload_qn,
                    module,
                    path,
                    payload.line,
                    type_text=_type_text(payload.type_name),
                    detail={"union": qn or union.name, "variant": variant_qn},
                    lookup_names=(payload_qn, payload.name),
                )
    for constant in program.constants:
        qn = _qualified_value_name(module, constant.name)
        state.add_symbol(
            "constant",
            _simple_name(constant.name),
            qn,
            module,
            path,
            constant.line,
            documentation=constant.documentation,
            type_text=_type_text(constant.type_name),
            lookup_names=(constant.name, _simple_name(constant.name), qn or constant.name),
        )
    for fn in program.functions:
        kind = "external_phrase" if fn.implementation == "extern" else "exported_phrase" if fn.implementation == "export" else "phrase"
        qn = _qualified_phrase_name(module, fn)
        result = _type_text(fn.return_type) if fn.return_type is not None else None
        detail: dict[str, object] = {
            "result": result,
            "parameters": [{"name": param.name, "type": _type_text(param.type_name)} for param in fn.params],
            "exported": fn.implementation == "export",
            "external": fn.implementation == "extern",
        }
        if fn.extern_symbol is not None:
            detail["symbol"] = fn.extern_symbol
        state.add_symbol(
            kind,
            fn.display_name,
            qn,
            module,
            path,
            fn.line,
            documentation=fn.documentation,
            type_text=result,
            detail=detail,
            lookup_names=(fn.name, fn.display_name, qn or fn.name, _phrase_lookup_alias(module, fn)),
        )
        for param in fn.params:
            state.add_symbol(
                "phrase_parameter",
                param.name,
                f"{qn}.{param.name}" if qn else f"{fn.name}.{param.name}",
                module,
                path,
                fn.line,
                type_text=_type_text(param.type_name),
                detail={"phrase": qn or fn.name},
            )
    for test in program.tests:
        qn = f"{module}::{test.display_name}" if module else f"test::{test.display_name}"
        state.add_symbol(
            "test",
            test.display_name,
            qn,
            module,
            path,
            test.line,
            documentation=test.documentation,
            lookup_names=(test.name, test.display_name, qn),
        )


def _index_program_references(state: _IndexState, indexed: _IndexedProgram) -> None:
    program = indexed.program
    path = indexed.display_path
    for imported in program.imports:
        target = state.symbol_by_lookup.get(f"module:{imported.module}") or state.symbol_by_lookup.get(imported.module)
        state.add_reference("import_module", imported.module, target, path, imported.line)
    for alias in program.type_aliases:
        _index_type_reference(state, alias.target, path, alias.line)
    for record in program.records:
        for field in record.fields:
            _index_type_reference(state, field.type_name, path, field.line)
    for enum in program.enums:
        _index_type_reference(state, enum.underlying_type, path, enum.line)
        for case in enum.cases:
            _index_expr(state, case.value, path)
    for union in program.unions:
        for variant in union.variants:
            for payload in variant.payload_fields:
                _index_type_reference(state, payload.type_name, path, payload.line)
    for constant in program.constants:
        _index_type_reference(state, constant.type_name, path, constant.line)
        _index_expr(state, constant.expr, path)
    for check in program.checks:
        _index_expr(state, check.expr, path)
    for fn in program.functions:
        for param in fn.params:
            _index_type_reference(state, param.type_name, path, fn.line)
        if fn.return_type is not None:
            _index_type_reference(state, fn.return_type, path, fn.line)
        for stmt in fn.body:
            _index_stmt(state, stmt, path)
    for test in program.tests:
        for stmt in test.body:
            _index_stmt(state, stmt, path)


def _index_expr(state: _IndexState, expr: Expr, path: str) -> None:
    if isinstance(expr, (Integer, Float, ByteLiteral, ByteString, Boolean, LengthOfBytes)):
        return
    if isinstance(expr, Variable):
        target = _lookup_constant(state, expr.name)
        if target is not None:
            state.add_reference("constant_reference", expr.name, target, path, expr.line)
        return
    if isinstance(expr, MoveArg):
        _index_expr(state, expr.source, path)
        return
    if isinstance(expr, BufferLoad):
        _index_expr(state, expr.index, path)
        return
    if isinstance(expr, LengthOf):
        return
    if isinstance(expr, SizeOfType):
        _index_named_type_reference(state, expr.type_name, path, expr.line)
        return
    if isinstance(expr, AlignmentOfType):
        _index_named_type_reference(state, expr.type_name, path, expr.line)
        return
    if isinstance(expr, OffsetOfField):
        _index_named_type_reference(state, expr.type_name, path, expr.line)
        target = state.field_targets.get(f"{expr.type_name}.{expr.field}") or state.field_targets.get(expr.field)
        state.add_reference("field_reference", expr.field, target, path, expr.line, detail={"type": expr.type_name})
        return
    if isinstance(expr, FieldAccess):
        target = state.field_targets.get(expr.field)
        state.add_reference("field_reference", expr.field, target, path, expr.line, detail={"base": expr.name})
        return
    if isinstance(expr, EnumCase):
        _index_named_type_reference(state, expr.type_name, path, expr.line)
        name = f"{expr.type_name}.{expr.case_name}"
        target = _lookup_enum_case(state, name, expr.case_name)
        state.add_reference("enum_case_reference", name, target, path, expr.line)
        return
    if isinstance(expr, UnionConstructor):
        _index_named_type_reference(state, expr.type_name, path, expr.line)
        name = f"{expr.type_name}.{expr.variant_name}"
        target = _lookup_union_variant(state, name, expr.variant_name)
        state.add_reference("union_constructor_reference", name, target, path, expr.line)
        for field in expr.fields:
            payload_target = state.symbol_by_lookup.get(f"union_payload:{name}.{field.name}") or state.symbol_by_lookup.get(
                f"union_payload:{field.name}"
            )
            state.add_reference("field_reference", field.name, payload_target, path, field.line, detail={"variant": name})
            _index_expr(state, field.expr, path)
        return
    if isinstance(expr, RecordConstructor):
        _index_named_type_reference(state, expr.type_name, path, expr.line)
        for field in expr.fields:
            target = state.field_targets.get(f"{expr.type_name}.{field.name}") or state.field_targets.get(field.name)
            state.add_reference("field_reference", field.name, target, path, field.line, detail={"type": expr.type_name})
            _index_expr(state, field.expr, path)
        return
    if isinstance(expr, LayoutRead):
        _index_named_type_reference(state, expr.type_name, path, expr.line)
        _index_expr(state, expr.index, path)
        return
    if isinstance(expr, Unary):
        _index_expr(state, expr.expr, path)
        return
    if isinstance(expr, Cast):
        _index_expr(state, expr.expr, path)
        _index_type_reference(state, expr.target_type, path, expr.line)
        return
    if isinstance(expr, Binary):
        _index_expr(state, expr.left, path)
        _index_expr(state, expr.right, path)
        return
    if isinstance(expr, Call):
        _index_call(state, expr, path)
        return
    if isinstance(expr, ComptimeExpr):
        _index_call(state, expr.call, path)
        return
    if isinstance(expr, Comparison):
        _index_expr(state, expr.left, path)
        _index_expr(state, expr.right, path)
        return
    if isinstance(expr, WhenExpr):
        for case in expr.cases:
            _index_expr(state, case.expr, path)
            _index_expr(state, case.condition, path)
        _index_expr(state, expr.otherwise, path)
        return
    if isinstance(expr, MatchExpr):
        _index_expr(state, expr.scrutinee, path)
        for arm in expr.arms:
            _index_pattern(state, arm.pattern, path)
            if arm.guard is not None:
                _index_expr(state, arm.guard, path)
            _index_expr(state, arm.expr, path)
        if expr.otherwise is not None:
            _index_expr(state, expr.otherwise, path)
        return
    raise AssertionError(f"unhandled expression {expr!r}")  # pragma: no cover


def _index_stmt(state: _IndexState, stmt: BodyStmt | ReturnStmt, path: str) -> None:
    if isinstance(stmt, (CheckStmt, RequireStmt, ExpectStmt, ReturnStmt)):
        _index_expr(state, stmt.expr, path)
        return
    if isinstance(stmt, SetStmt):
        if stmt.type_name is not None:
            _index_type_reference(state, stmt.type_name, path, stmt.line)
        _index_expr(state, stmt.expr, path)
        return
    if isinstance(stmt, BufferBinding):
        _index_buffer_type(state, stmt.buffer_type, path, stmt.line)
        if stmt.fill is not None:
            _index_expr(state, stmt.fill, path)
        for value in stmt.values:
            _index_storage_element(state, value, path)
        return
    if isinstance(stmt, ArrayBinding):
        _index_array_type(state, stmt.array_type, path, stmt.line)
        if stmt.fill is not None:
            _index_expr(state, stmt.fill, path)
        for value in stmt.values:
            _index_storage_element(state, value, path)
        return
    if isinstance(stmt, StorageAliasBinding):
        _index_type_reference(state, stmt.alias_type, path, stmt.line)
        if stmt.fill is not None:
            _index_expr(state, stmt.fill, path)
        for value in stmt.values:
            _index_storage_element(state, value, path)
        return
    if isinstance(stmt, OwnedBufferBinding):
        if stmt.length is not None:
            _index_expr(state, stmt.length, path)
        if stmt.element_type is not None:
            _index_type_reference(state, stmt.element_type, path, stmt.line)
        if stmt.fill is not None:
            _index_expr(state, stmt.fill, path)
        for value in stmt.values:
            _index_storage_element(state, value, path)
        return
    if isinstance(stmt, ViewBinding):
        _index_expr(state, stmt.start, path)
        _index_expr(state, stmt.count, path)
        return
    if isinstance(stmt, AssignStmt):
        _index_expr(state, stmt.expr, path)
        return
    if isinstance(stmt, BufferStoreStmt):
        _index_expr(state, stmt.index, path)
        _index_expr(state, stmt.value, path)
        return
    if isinstance(stmt, FieldAssignStmt):
        target = state.field_targets.get(stmt.field)
        state.add_reference("field_reference", stmt.field, target, path, stmt.line, detail={"base": stmt.name})
        _index_expr(state, stmt.expr, path)
        return
    if isinstance(stmt, LayoutWriteStmt):
        _index_named_type_reference(state, stmt.record_name, path, stmt.line)
        _index_expr(state, stmt.index, path)
        return
    if isinstance(stmt, CallStmt):
        _index_call(state, stmt.call, path)
        return
    if isinstance(stmt, WhileStmt):
        _index_expr(state, stmt.condition, path)
        for nested in stmt.body:
            _index_stmt(state, nested, path)
        return
    if isinstance(stmt, ForStmt):
        _index_expr(state, stmt.start, path)
        _index_expr(state, stmt.end, path)
        for nested in stmt.body:
            _index_stmt(state, nested, path)
        return
    if isinstance(stmt, ForEachStmt):
        for nested in stmt.body:
            _index_stmt(state, nested, path)
        return
    if isinstance(stmt, IfStmt):
        _index_expr(state, stmt.condition, path)
        for nested in stmt.then_body:
            _index_stmt(state, nested, path)
        for nested in stmt.else_body:
            _index_stmt(state, nested, path)
        return
    if isinstance(stmt, MatchStep):
        _index_expr(state, stmt.scrutinee, path)
        for arm in stmt.arms:
            _index_pattern(state, arm.pattern, path)
            if arm.guard is not None:
                _index_expr(state, arm.guard, path)
            for nested in arm.body:
                _index_stmt(state, nested, path)
        if stmt.otherwise_body is not None:
            for nested in stmt.otherwise_body:
                _index_stmt(state, nested, path)
        return
    raise AssertionError(f"unhandled statement {stmt!r}")  # pragma: no cover


def _index_call(state: _IndexState, call: Call, path: str) -> None:
    target = _lookup_phrase(state, call.name)
    state.add_reference("phrase_call", call.name, target, path, call.line)
    for actual in call.args:
        if isinstance(actual, MoveArg):
            _index_expr(state, actual.source, path)
        else:
            _index_expr(state, actual, path)


def _index_pattern(state: _IndexState, pattern, path: str) -> None:
    if isinstance(pattern, UnionPattern):
        _index_named_type_reference(state, pattern.type_name, path, pattern.line)
        name = f"{pattern.type_name}.{pattern.variant_name}"
        target = _lookup_union_variant(state, name, pattern.variant_name)
        state.add_reference("union_pattern_reference", name, target, path, pattern.line)
        for binding in pattern.bindings:
            payload_target = state.symbol_by_lookup.get(f"union_payload:{name}.{binding.field_name}") or state.symbol_by_lookup.get(
                f"union_payload:{binding.field_name}"
            )
            state.add_reference("field_reference", binding.field_name, payload_target, path, binding.line, detail={"variant": name})
        return
    if isinstance(pattern, RangePattern):
        _index_expr(state, pattern.lower, path)
        _index_expr(state, pattern.upper, path)
        return
    if isinstance(pattern, AlternativePattern):
        for alternative in pattern.alternatives:
            _index_pattern(state, alternative, path)
        return
    if isinstance(pattern, AnythingPattern):
        return
    _index_expr(state, pattern, path)


def _index_storage_element(state: _IndexState, value, path: str) -> None:
    if isinstance(value, ByteString):
        return
    _index_expr(state, value, path)


def _index_buffer_type(state: _IndexState, buffer_type: BufferType, path: str, line: int) -> None:
    if not isinstance(buffer_type.length, int):
        _index_expr(state, buffer_type.length, path)
    _index_type_reference(state, buffer_type.element_type, path, line)


def _index_array_type(state: _IndexState, array_type: ArrayType, path: str, line: int) -> None:
    if not isinstance(array_type.length, int):
        _index_expr(state, array_type.length, path)
    _index_type_reference(state, array_type.element_type, path, line)


def _index_type_reference(state: _IndexState, type_name: ValueType | None, path: str, line: int) -> None:
    if type_name is None:
        return
    if isinstance(type_name, str):
        return
    if isinstance(type_name, RecordType):
        _index_named_type_reference(state, type_name.name, path, line)
        return
    if type_name.__class__.__name__ in {"EnumType", "UnionType"}:
        _index_named_type_reference(state, type_name.name, path, line)
        return
    if isinstance(type_name, BufferType):
        _index_buffer_type(state, type_name, path, line)
        return
    if isinstance(type_name, ArrayType):
        _index_array_type(state, type_name, path, line)
        return
    if isinstance(type_name, ViewType):
        _index_type_reference(state, type_name.element_type, path, line)
        return
    if isinstance(type_name, OwnedBufferType):
        _index_type_reference(state, type_name.element_type, path, line)
        return


def _index_named_type_reference(state: _IndexState, name: str, path: str, line: int) -> None:
    target = _lookup_type(state, name)
    state.add_reference("type_reference", name, target, path, line)


def _index_package_manifest_symbols(state: _IndexState, context: PackageContext) -> None:
    path = _display_path(context.manifest_path, context.root if state.base is None else state.base)
    source = context.manifest_path.read_text()
    state.source_by_path[path] = source
    state.add_file(path, module=None, role="package")
    lines = context.manifest.declaration_lines or {}
    manifest = context.manifest
    state.add_symbol(
        "package",
        manifest.package_name,
        manifest.package_name,
        None,
        path,
        lines.get("Package"),
        documentation=manifest.documentation,
        detail={"version": manifest.version, "sources": manifest.sources, "tests": manifest.tests},
        lookup_names=(manifest.package_name,),
    )
    seen_modules: set[str] = set()
    for module in (manifest.root_module, *manifest.exposed_modules):
        if module in seen_modules:
            continue
        seen_modules.add(module)
        state.add_symbol(
            "exposed_module",
            module,
            module,
            module,
            path,
            lines.get(f"Expose module {module}") or lines.get("Root module"),
            detail={"root": module == manifest.root_module},
            lookup_names=(module,),
        )
    for dependency in manifest.dependencies:
        state.add_symbol(
            "package_dependency",
            dependency.name,
            dependency.name,
            None,
            path,
            dependency.line,
            detail={"path": dependency.path},
            lookup_names=(dependency.name,),
        )


def _index_package_manifest_references(state: _IndexState, context: PackageContext) -> None:
    path = _display_path(context.manifest_path, context.root if state.base is None else state.base)
    lines = context.manifest.declaration_lines or {}
    for module in package_import_modules(context.manifest):
        target = state.symbol_by_lookup.get(f"module:{module}") or state.symbol_by_lookup.get(f"exposed_module:{module}")
        state.add_reference("import_module", module, target, path, lines.get(f"Expose module {module}") or lines.get("Root module"))
    for dependency in context.manifest.dependencies:
        target = state.symbol_by_lookup.get(f"package:{dependency.name}") or state.symbol_by_lookup.get(
            f"package_dependency:{dependency.name}"
        )
        state.add_reference("package_dependency_reference", dependency.name, target, path, dependency.line, detail={"path": dependency.path})


def _index_build_script_symbols(state: _IndexState, context: PackageContext) -> None:
    path_obj = context.root / BUILD_SCRIPT_NAME
    if not path_obj.exists():
        return
    script = load_build_script(context.root)
    path = _display_path(path_obj, context.root if state.base is None else state.base)
    state.source_by_path[path] = path_obj.read_text()
    state.add_file(path, module=None, role="build")
    for step in script.steps:
        kind = "build_group" if step.emit == "group" else "build_step"
        symbol = state.add_symbol(
            kind,
            step.name,
            f"build.{step.name}",
            None,
            path,
            step.line,
            detail={"step_kind": step.emit, "dependencies": list(step.dependencies), "package_default": step.package_default},
            lookup_names=(step.name, f"build.{step.name}"),
        )
        state.build_step_targets[step.name] = symbol.id
    if script.default_step is not None:
        line = _find_default_step_line(script, state.source_by_path[path])
        state.add_symbol(
            "build_default",
            "default",
            "build.default",
            None,
            path,
            line,
            detail={"step": script.default_step},
            lookup_names=("default", "build.default"),
        )


def _index_build_script_references(state: _IndexState, context: PackageContext) -> None:
    path_obj = context.root / BUILD_SCRIPT_NAME
    if not path_obj.exists():
        return
    script = load_build_script(context.root)
    path = _display_path(path_obj, context.root if state.base is None else state.base)
    for step in script.steps:
        if step.emit != "group":
            continue
        for dependency in step.dependencies:
            state.add_reference("build_step_reference", dependency, state.build_step_targets.get(dependency), path, step.line, detail={"group": step.name})
    if script.default_step is not None:
        line = _find_default_step_line(script, state.source_by_path.get(path, ""))
        state.add_reference("build_step_reference", script.default_step, state.build_step_targets.get(script.default_step), path, line, detail={"default": True})


def _find_default_step_line(script: BuildScript, source: str) -> int | None:
    needle = f'Build.default step is "{script.default_step}"'
    for number, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return number
    return None


def _finalize_field_targets(state: _IndexState) -> None:
    field_ids: dict[str, list[str]] = {}
    for symbol in state.symbols:
        if symbol.kind not in {"record_field", "union_payload"}:
            continue
        field_ids.setdefault(symbol.name, []).append(symbol.id)
        if symbol.qualified_name is not None:
            state.field_targets[symbol.qualified_name] = symbol.id
            parts = symbol.qualified_name.split(".")
            if len(parts) >= 2:
                state.field_targets[f"{parts[-2]}.{parts[-1]}"] = symbol.id
    for name, ids in field_ids.items():
        if len(ids) == 1:
            state.field_targets[name] = ids[0]


def _lookup_keys(kind: str, name: str, qualified_name: str | None, extra: Iterable[str]) -> tuple[str, ...]:
    keys: list[str] = []
    for value in (name, qualified_name, *extra):
        if value:
            keys.append(value)
            keys.append(f"{kind}:{value}")
    return tuple(dict.fromkeys(keys))


def _lookup_type(state: _IndexState, name: str) -> str | None:
    simple = _simple_name(name)
    for kind in ("type_alias", "record", "layout_record", "packed_layout_record", "enum", "union"):
        for key in (f"{kind}:{name}", f"{kind}:{simple}"):
            target = state.symbol_by_lookup.get(key)
            if target is not None:
                return target
    return state.symbol_by_lookup.get(name) or state.symbol_by_lookup.get(simple)


def _lookup_constant(state: _IndexState, name: str) -> str | None:
    return state.symbol_by_lookup.get(f"constant:{name}") or state.symbol_by_lookup.get(f"constant:{_simple_name(name)}")


def _lookup_phrase(state: _IndexState, name: str) -> str | None:
    normalized = name.replace("__", ".")
    for kind in ("phrase", "exported_phrase", "external_phrase"):
        for key in (f"{kind}:{name}", f"{kind}:{normalized}"):
            target = state.symbol_by_lookup.get(key)
            if target is not None:
                return target
    return state.symbol_by_lookup.get(name) or state.symbol_by_lookup.get(normalized)


def _lookup_enum_case(state: _IndexState, full_name: str, case_name: str) -> str | None:
    for key in (f"enum_case:{full_name}", f"enum_case:{case_name}"):
        target = state.symbol_by_lookup.get(key)
        if target is not None:
            return target
    return None


def _lookup_union_variant(state: _IndexState, full_name: str, variant_name: str) -> str | None:
    for key in (f"union_variant:{full_name}", f"union_variant:{variant_name}"):
        target = state.symbol_by_lookup.get(key)
        if target is not None:
            return target
    return None


def _symbol_payload(symbol: Symbol) -> dict[str, object]:
    return {
        "id": symbol.id,
        "kind": symbol.kind,
        "name": symbol.name,
        "qualified_name": symbol.qualified_name,
        "module": symbol.module,
        "path": symbol.path,
        "span": _span_payload(symbol.span),
        "documentation": symbol.documentation,
        "type": symbol.type,
        "detail": symbol.detail or {},
    }


def _reference_payload(reference: Reference) -> dict[str, object]:
    return {
        "kind": reference.kind,
        "name": reference.name,
        "target_id": reference.target_id,
        "path": reference.path,
        "span": _span_payload(reference.span),
        "detail": reference.detail or {},
    }


def _file_payload(file: IndexedFile) -> dict[str, object]:
    return {"path": file.path, "module": file.module, "role": file.role}


def _span_payload(span: SourceSpan | None) -> dict[str, object] | None:
    if span is None:
        return None
    return {
        "path": span.path,
        "line": span.line,
        "column": span.column or 1,
        "end_line": span.end_line if span.end_line is not None else span.line,
        "end_column": span.end_column if span.end_column is not None else (span.column or 1),
    }



def _resolve_symbol_line(kind: str, name: str, line: int | None, source: str | None) -> int | None:
    if line is None or source is None:
        return line
    prefixes = _symbol_line_prefixes(kind, name)
    if not prefixes:
        return line
    lines = source.splitlines()
    if 1 <= line <= len(lines) and any(lines[line - 1].lstrip().startswith(prefix) for prefix in prefixes):
        return line
    for number, text in enumerate(lines, start=1):
        stripped = text.lstrip()
        if any(stripped.startswith(prefix) for prefix in prefixes):
            return number
    return line


def _symbol_line_prefixes(kind: str, name: str) -> tuple[str, ...]:
    if kind == "module":
        return (f"Module {name}",)
    if kind == "type_alias":
        return (f"Type {name} ",)
    if kind == "constant":
        return (f"Constant {name}:", f"Constant {name} ")
    if kind in {"record", "record_field"}:
        return (f"Record {name}",) if kind == "record" else ()
    if kind == "layout_record":
        return (f"Layout record {name}",)
    if kind == "packed_layout_record":
        return (f"Packed layout record {name}",)
    if kind == "enum":
        return (f"Enum {name} ",)
    if kind == "union":
        return (f"Union {name} ",)
    if kind in {"phrase", "exported_phrase", "external_phrase"}:
        head = name.split(" _", 1)[0]
        return (f"To {head}", f"External {head}")
    if kind == "test":
        return (f"Test {name}",)
    return ()

def _span_for_line(path: str, line: int | None, source: str | None) -> SourceSpan | None:
    if line is None:
        return None
    end_column = 1
    if source is not None:
        lines = source.splitlines()
        if 1 <= line <= len(lines):
            end_column = max(2, len(lines[line - 1]) + 1)
    return SourceSpan(path, line, 1, line, end_column)


def _symbol_id(kind: str, qualified_name: str, path: str, line: int | None) -> str:
    location = f"{path}:{line or 0}"
    safe_name = qualified_name.replace(" ", "_")
    return f"{kind}:{safe_name}:{location}"


def _display_path(path: Path, base: Path | None) -> str:
    path = path.resolve()
    if base is not None:
        try:
            return path.relative_to(base.resolve()).as_posix()
        except ValueError:
            pass
    try:
        return path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _simple_name(name: str) -> str:
    return name.split(".")[-1].split("__")[-1]


def _display_module_name(module: str) -> str:
    return module.replace("__", ".")


def _qualified_type_name(module: str | None, name: str) -> str:
    display = name.replace("__", ".")
    if "." in display:
        return display
    return f"{module}.{display}" if module else display


def _qualified_value_name(module: str | None, name: str) -> str:
    display = name.replace("__", ".")
    if "." in display:
        return display
    return f"{module}.{display}" if module else display


def _qualified_phrase_name(module: str | None, fn: Function) -> str:
    base = fn.name.replace("__", ".")
    if "." in base:
        return base if fn.display_name == "main" else f"{module}.{fn.display_name}" if module else base
    return f"{module}.{fn.display_name}" if module else fn.display_name


def _phrase_lookup_alias(module: str | None, fn: Function) -> str:
    if module is None:
        return fn.display_name
    return f"{module}.{fn.display_name}"


def _type_text(type_name: ValueType | None) -> str | None:
    if type_name is None:
        return None
    return format_type(type_name)


def _module_line(program: Program) -> int | None:
    return 1 if program.module_name is not None else None
