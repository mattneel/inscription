from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .compiler import LoadedCompilation, load_compilation, load_program, module_path, validate_module_name
from .diagnostics import InscriptionError
from .mlir import emit_mlir
from .parser import (
    SourceComment,
    _split_line_comment,
    _split_punctuation_sentences_no_comments,
)
from .interface import emit_c_header, emit_interface_json, make_interface_context
from .runner import EMIT_MODES, Toolchain, build_artifacts, selected_artifact, validate_executable_main
from .semantic import analyze
from .tester import TestRunItem, TestRunSummary, list_tests, run_tests, test_slug
from .version import INSCRIPTION_VERSION, LANGUAGE_VERSION, RELEASE_FORMAT

MANIFEST_NAME = "package.ins"
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')
MODULE_RE_FRAGMENT = r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*"


@dataclass(frozen=True)
class ManifestCommentInfo:
    source: str
    comments: tuple[SourceComment, ...]
    module_documentation: str | None
    comments_by_line: dict[int, tuple[SourceComment, ...]]


@dataclass(frozen=True)
class PackageDependency:
    name: str
    path: str
    line: int


@dataclass(frozen=True)
class PackageManifest:
    package_name: str
    sources: str
    root_module: str
    version: str | None = None
    tests: str | None = None
    exposed_modules: tuple[str, ...] = ()
    dependencies: tuple[PackageDependency, ...] = ()
    documentation: str | None = None
    comments_by_line: dict[int, tuple[SourceComment, ...]] | None = None
    declaration_lines: dict[str, int] | None = None


@dataclass(frozen=True)
class PackageContext:
    root: Path
    manifest_path: Path
    manifest: PackageManifest

    @property
    def sources_dir(self) -> Path:
        return self.root / self.manifest.sources

    @property
    def tests_dir(self) -> Path | None:
        if self.manifest.tests is None:
            return None
        return self.root / self.manifest.tests


@dataclass(frozen=True)
class PackageGraph:
    root: PackageContext
    packages: tuple[PackageContext, ...]
    dependencies_by_name: dict[str, tuple[PackageContext, ...]]
    contexts_by_name: dict[str, PackageContext]


@dataclass(frozen=True)
class PackageTestSummary:
    package_name: str
    passed: int
    failed: int
    results: tuple[TestRunItem, ...]

    @property
    def exit_status(self) -> int:
        return 0 if self.failed == 0 else 1


@dataclass(frozen=True)
class PackageBuildResult:
    package_name: str
    emit: str
    output_path: Path | None = None
    text: str | None = None
    data: bytes | None = None


@dataclass(frozen=True)
class PackageFormatResult:
    package_name: str
    files: tuple[Path, ...]
    changed: tuple[Path, ...]


@dataclass(frozen=True)
class PackageCleanResult:
    package_name: str
    root: Path
    target: Path
    removed: bool
    dry_run: bool


@dataclass(frozen=True)
class PackageReleaseArtifact:
    kind: str
    path: str


@dataclass(frozen=True)
class PackageReleaseResult:
    package_name: str
    output_dir: Path
    artifacts: tuple[PackageReleaseArtifact, ...]
    archive_path: Path | None = None
    checksum_path: Path | None = None
    archive_checksum_path: Path | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class PackageInitResult:
    root: Path
    package_name: str
    files: tuple[Path, ...]


def is_manifest_source(source: str) -> bool:
    try:
        comments = collect_manifest_comments(source)
        sentences = _split_punctuation_sentences_no_comments(comments.source)
    except InscriptionError:
        return False
    return bool(sentences and sentences[0].text.startswith("Package"))


def load_package_context(root: Path) -> PackageContext:
    root = root.resolve()
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.exists():
        raise InscriptionError(f"package manifest not found at {MANIFEST_NAME}")
    manifest = parse_manifest(manifest_path.read_text())
    return PackageContext(root, manifest_path, manifest)


class PackageGraphLoader:
    def __init__(self) -> None:
        self.contexts_by_root: dict[Path, PackageContext] = {}
        self.contexts_by_name: dict[str, PackageContext] = {}
        self.dependencies_by_name: dict[str, tuple[PackageContext, ...]] = {}
        self.order: list[PackageContext] = []

    def load(self, root: Path) -> PackageGraph:
        root_context = self._load_package(root.resolve(), expected_name=None, dependency_path=None, stack=())
        return PackageGraph(
            root_context,
            tuple(self.order),
            self.dependencies_by_name,
            self.contexts_by_name,
        )

    def _load_package(
        self,
        root: Path,
        *,
        expected_name: str | None,
        dependency_path: str | None,
        stack: tuple[PackageContext, ...],
    ) -> PackageContext:
        root = root.resolve()
        manifest_path = root / MANIFEST_NAME
        if not manifest_path.exists():
            if expected_name is not None and dependency_path is not None:
                raise InscriptionError(f"dependency {expected_name} not found at {dependency_path}/{MANIFEST_NAME}")
            raise InscriptionError(f"package manifest not found at {MANIFEST_NAME}")
        for index, context in enumerate(stack):
            if context.root == root:
                cycle_names = [item.manifest.package_name for item in stack[index:]]
                cycle_names.append(expected_name or context.manifest.package_name)
                raise InscriptionError(f"package dependency cycle detected: {' -> '.join(cycle_names)}")
        if root in self.contexts_by_root:
            context = self.contexts_by_root[root]
            if expected_name is not None and context.manifest.package_name != expected_name:
                raise InscriptionError(
                    f"dependency {expected_name} resolved to package {context.manifest.package_name}; expected {expected_name}"
                )
            return context

        context = load_package_context(root)
        if expected_name is not None and context.manifest.package_name != expected_name:
            raise InscriptionError(
                f"dependency {expected_name} resolved to package {context.manifest.package_name}; expected {expected_name}"
            )
        previous = self.contexts_by_name.get(context.manifest.package_name)
        if previous is not None and previous.root != context.root:
            raise InscriptionError(f"dependency {context.manifest.package_name} resolves to multiple package roots")

        self.contexts_by_root[root] = context
        self.contexts_by_name[context.manifest.package_name] = context
        self.order.append(context)

        direct_dependencies: list[PackageContext] = []
        dependency_path_names: dict[Path, str] = {}
        for dependency in context.manifest.dependencies:
            dependency_root = (context.root / dependency.path).resolve()
            previous_name = dependency_path_names.get(dependency_root)
            if previous_name is not None and previous_name != dependency.name:
                raise InscriptionError(
                    f"dependency path {dependency.path} is declared for both {previous_name} and {dependency.name}",
                    dependency.line,
                )
            dependency_path_names[dependency_root] = dependency.name
            loaded = self._load_package(
                dependency_root,
                expected_name=dependency.name,
                dependency_path=dependency.path,
                stack=(*stack, context),
            )
            known = self.contexts_by_name.get(dependency.name)
            if known is not None and known.root != loaded.root:
                raise InscriptionError(f"dependency {dependency.name} resolves to multiple package roots", dependency.line)
            direct_dependencies.append(loaded)
        self.dependencies_by_name[context.manifest.package_name] = tuple(direct_dependencies)
        return context


def load_package_graph(root: Path) -> PackageGraph:
    return PackageGraphLoader().load(root)


class PackageModuleResolver:
    def __init__(self, graph: PackageGraph, current_package: PackageContext):
        self.graph = graph
        self.current_package = current_package
        self.module_package_names: dict[str, str] = {}

    def __call__(self, module: str, stack: tuple[str, ...]) -> Path:
        importer = self._importer_package(stack)
        local = module_path(importer.sources_dir, module)
        if local.exists():
            self.module_package_names[module] = importer.manifest.package_name
            return local
        for dependency in self.graph.dependencies_by_name.get(importer.manifest.package_name, ()):
            dependency_path = module_path(dependency.sources_dir, module)
            if module in _dependency_visible_modules(dependency):
                self.module_package_names[module] = dependency.manifest.package_name
                return dependency_path
            if dependency_path.exists():
                raise InscriptionError(f"module {module} is not exposed by package {dependency.manifest.package_name}")
        return local

    def _importer_package(self, stack: tuple[str, ...]) -> PackageContext:
        if not stack:
            return self.current_package
        importer_module = stack[-1]
        package_name = self.module_package_names.get(importer_module)
        if package_name is not None:
            return self.graph.contexts_by_name[package_name]
        for context in self.graph.packages:
            if module_path(context.sources_dir, importer_module).exists():
                self.module_package_names[importer_module] = context.manifest.package_name
                return context
        return self.current_package


def _dependency_visible_modules(context: PackageContext) -> set[str]:
    return {context.manifest.root_module, *context.manifest.exposed_modules}


def parse_manifest(source: str) -> PackageManifest:
    comments = collect_manifest_comments(source)
    sentences = _split_punctuation_sentences_no_comments(comments.source)
    if not sentences or not sentences[0].text.startswith("Package"):
        raise InscriptionError("package manifest must start with Package declaration", sentences[0].line if sentences else None)

    package_name: str | None = None
    version: str | None = None
    sources: str | None = None
    tests: str | None = None
    root_module: str | None = None
    exposed: list[str] = []
    exposed_seen: set[str] = set()
    dependencies: list[PackageDependency] = []
    dependency_names: set[str] = set()
    declaration_lines: dict[str, int] = {}

    for index, sentence in enumerate(sentences):
        text = sentence.text
        line = sentence.line
        if text.startswith("Package"):
            if package_name is not None:
                raise InscriptionError("package manifest declares package more than once", line)
            if index != 0:
                raise InscriptionError("Package declaration must be first in package manifest", line)
            name = text[len("Package") :].strip()
            if not name:
                raise InscriptionError("package declaration requires a package name", line)
            package_name = _validate_manifest_module_path(name, "package name", line)
            declaration_lines["Package"] = line
            continue
        if text.startswith("Version"):
            if version is not None:
                raise InscriptionError("package manifest declares version more than once", line)
            literal = text[len("Version") :].strip()
            version = _parse_manifest_string(literal, line)
            if SEMVER_RE.fullmatch(version) is None:
                raise InscriptionError("package version must use MAJOR.MINOR.PATCH format", line)
            declaration_lines["Version"] = line
            continue
        if text.startswith("Sources"):
            if sources is not None:
                raise InscriptionError("package manifest declares sources more than once", line)
            match = re.fullmatch(rf"Sources\s+are\s+in\s+({STRING_RE.pattern})", text)
            if match is None:
                raise InscriptionError("malformed sources declaration", line)
            sources = _validate_manifest_path(_parse_manifest_string(match.group(1), line), line)
            declaration_lines["Sources"] = line
            continue
        if text.startswith("Tests"):
            if tests is not None:
                raise InscriptionError("package manifest declares tests more than once", line)
            match = re.fullmatch(rf"Tests\s+are\s+in\s+({STRING_RE.pattern})", text)
            if match is None:
                raise InscriptionError("malformed tests declaration", line)
            tests = _validate_manifest_path(_parse_manifest_string(match.group(1), line), line)
            declaration_lines["Tests"] = line
            continue
        if text.startswith("Root"):
            if root_module is not None:
                raise InscriptionError("package manifest declares root module more than once", line)
            prefix = "Root module is "
            if not text.startswith(prefix):
                raise InscriptionError("malformed root module declaration", line)
            root_module = _validate_manifest_module_path(text[len(prefix) :].strip(), "root module", line)
            declaration_lines["Root module"] = line
            continue
        if text.startswith("Expose"):
            prefix = "Expose module "
            if not text.startswith(prefix):
                raise InscriptionError("malformed exposed module declaration", line)
            module = _validate_manifest_module_path(text[len(prefix) :].strip(), "exposed module", line)
            if module in exposed_seen:
                raise InscriptionError(f"package manifest exposes module {module} more than once", line)
            exposed_seen.add(module)
            exposed.append(module)
            declaration_lines[f"Expose module {module}"] = line
            continue
        if text.startswith("Depend"):
            match = re.fullmatch(rf"Depend\s+on\s+({MODULE_RE_FRAGMENT})\s+from\s+path\s+({STRING_RE.pattern})", text)
            if match is None:
                raise InscriptionError("malformed dependency declaration", line)
            name = _validate_manifest_module_path(match.group(1), "dependency", line)
            if name in dependency_names:
                raise InscriptionError(f"package manifest declares dependency {name} more than once", line)
            dependency_names.add(name)
            path = _validate_dependency_path(_parse_manifest_string(match.group(2), line), line)
            dependencies.append(PackageDependency(name, path, line))
            declaration_lines[f"Depend on {name}"] = line
            continue
        _reject_manifest_sentence(text, line)

    assert package_name is not None
    if sources is None:
        raise InscriptionError("package manifest must declare a sources directory")
    if root_module is None:
        raise InscriptionError("package manifest must declare a root module")
    return PackageManifest(
        package_name,
        sources,
        root_module,
        version,
        tests,
        tuple(exposed),
        tuple(dependencies),
        comments.module_documentation,
        comments.comments_by_line,
        declaration_lines,
    )


def collect_manifest_comments(source: str) -> ManifestCommentInfo:
    stripped_lines: list[str] = []
    comments: list[SourceComment] = []
    module_doc_lines: list[str] = []
    saw_declaration = False
    pending_line_comments: list[SourceComment] = []
    comments_by_line: dict[int, list[SourceComment]] = {}

    for number, raw in enumerate(source.splitlines(), start=1):
        code, kind, text = _split_line_comment(raw, number)
        stripped_lines.append(code)
        if kind is not None:
            trailing = bool(code.strip())
            comment = SourceComment(number, kind, text, trailing)
            comments.append(comment)
            if kind == "module":
                if trailing or saw_declaration:
                    raise InscriptionError("module documentation comments must appear before the first declaration", number)
                module_doc_lines.append(text)
            elif not trailing:
                pending_line_comments.append(comment)
            elif kind == "doc":
                raise InscriptionError("documentation comments are only supported before manifest declarations", number)
        if code.strip():
            saw_declaration = True
            if pending_line_comments:
                comments_by_line.setdefault(number, []).extend(pending_line_comments)
                pending_line_comments = []
            for comment in comments:
                if comment.trailing and comment.line == number:
                    comments_by_line.setdefault(number, []).append(comment)

    stripped_source = "\n".join(stripped_lines) + ("\n" if source.endswith("\n") else "")
    return ManifestCommentInfo(
        stripped_source,
        tuple(comments),
        "\n".join(module_doc_lines) if module_doc_lines else None,
        {line: tuple(items) for line, items in comments_by_line.items()},
    )


def format_manifest_source(source: str) -> str:
    manifest = parse_manifest(source)
    comments_by_line = manifest.comments_by_line or {}
    declaration_lines = manifest.declaration_lines or {}
    out: list[str] = []

    if manifest.documentation:
        for line in manifest.documentation.split("\n"):
            out.append("//!" if not line else f"//! {line}")
        out.append("")

    def append_decl(key: str, lines: list[str]) -> None:
        source_line = declaration_lines.get(key)
        attached = comments_by_line.get(source_line, ()) if source_line is not None else ()
        if out and out[-1] != "":
            out.append("")
        for comment in attached:
            if comment.kind == "module":
                continue
            out.append(_format_manifest_comment(comment))
        if attached and out and out[-1] != "" and out[-1].startswith("///"):
            pass
        out.extend(lines)

    append_decl("Package", [f"Package {manifest.package_name}."])
    if manifest.version is not None:
        append_decl("Version", [f"Version {_quote_manifest_string(manifest.version)}."])
    append_decl("Sources", [f"Sources are in {_quote_manifest_string(manifest.sources)}."])
    if manifest.tests is not None:
        # Tests belongs to the same group as Sources.
        source_line = declaration_lines.get("Tests")
        for comment in comments_by_line.get(source_line, ()) if source_line is not None else ():
            out.append(_format_manifest_comment(comment))
        out.append(f"Tests are in {_quote_manifest_string(manifest.tests)}.")
    append_decl("Root module", [f"Root module is {manifest.root_module}."])
    first_expose = True
    for module in manifest.exposed_modules:
        key = f"Expose module {module}"
        if first_expose:
            append_decl(key, [f"Expose module {module}."])
            first_expose = False
            continue
        source_line = declaration_lines.get(key)
        for comment in comments_by_line.get(source_line, ()) if source_line is not None else ():
            out.append(_format_manifest_comment(comment))
        out.append(f"Expose module {module}.")
    first_dependency = True
    for dependency in manifest.dependencies:
        key = f"Depend on {dependency.name}"
        line_text = f"Depend on {dependency.name} from path {_quote_manifest_string(dependency.path)}."
        if first_dependency:
            append_decl(key, [line_text])
            first_dependency = False
            continue
        source_line = declaration_lines.get(key)
        for comment in comments_by_line.get(source_line, ()) if source_line is not None else ():
            out.append(_format_manifest_comment(comment))
        out.append(line_text)

    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def _format_manifest_comment(comment: SourceComment) -> str:
    marker = {"ordinary": "//", "doc": "///", "module": "//!"}[comment.kind]
    return marker if not comment.text else f"{marker} {comment.text}"


def _quote_manifest_string(value: str) -> str:
    out = ['"']
    for char in value:
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append('\\\\')
        elif char == "\n":
            out.append('\\n')
        elif char == "\r":
            out.append('\\r')
        elif char == "\t":
            out.append('\\t')
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _parse_manifest_string(token: str, line: int) -> str:
    if STRING_RE.fullmatch(token) is None:
        raise InscriptionError("expected manifest string literal", line)
    body = token[1:-1]
    out: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char != "\\":
            if char == "\x00":
                raise InscriptionError("manifest strings may not contain NUL", line)
            out.append(char)
            index += 1
            continue
        if index + 1 >= len(body):
            raise InscriptionError("unterminated string literal", line)
        escaped = body[index + 1]
        if escaped == '"':
            out.append('"')
        elif escaped == "\\":
            out.append("\\")
        elif escaped == "n":
            out.append("\n")
        elif escaped == "r":
            out.append("\r")
        elif escaped == "t":
            out.append("\t")
        else:
            raise InscriptionError(f"invalid manifest string escape \\{escaped}", line)
        index += 2
    return "".join(out)


def _validate_manifest_path(path_text: str, line: int) -> str:
    if not path_text:
        raise InscriptionError("package paths may not be empty", line)
    if "\x00" in path_text:
        raise InscriptionError("package paths may not contain NUL", line)
    pure = PurePosixPath(path_text)
    if pure.is_absolute() or Path(path_text).is_absolute():
        raise InscriptionError("package paths must be relative", line)
    if ".." in pure.parts:
        raise InscriptionError("package paths may not contain `..`", line)
    return path_text


def _validate_dependency_path(path_text: str, line: int) -> str:
    if not path_text:
        raise InscriptionError("dependency path must not be empty", line)
    if "\x00" in path_text:
        raise InscriptionError("dependency paths may not contain NUL", line)
    if PurePosixPath(path_text).is_absolute() or Path(path_text).is_absolute():
        raise InscriptionError("dependency paths must be relative", line)
    return path_text


def _validate_manifest_module_path(name: str, context: str, line: int) -> str:
    if not name:
        raise InscriptionError(f"{context} declaration requires a module path", line)
    return validate_module_name(name, line)


def _reject_manifest_sentence(text: str, line: int) -> None:
    if text.startswith("To "):
        raise InscriptionError("package manifests do not support phrase declarations", line)
    if text.startswith("Let "):
        raise InscriptionError("package manifests do not support Let", line)
    if text.startswith("Import "):
        raise InscriptionError("package manifests do not support imports", line)
    if text.startswith("Test "):
        raise InscriptionError("package manifests do not support test declarations", line)
    if text.startswith("Depend "):
        raise InscriptionError("malformed dependency declaration", line)
    raise InscriptionError("package manifests support only Package, Version, Sources, Tests, Root module, Expose module, and Depend on declarations", line)


def check_package(root: Path, *, verify: bool = False, toolchain: Toolchain | None = None) -> PackageContext:
    return checked_package_graph(root, verify=verify, toolchain=toolchain).root


def checked_package_graph(root: Path, *, verify: bool = False, toolchain: Toolchain | None = None) -> PackageGraph:
    graph = load_package_graph(root)
    for context in graph.packages:
        _validate_package_context(context, graph=graph, verify=verify, toolchain=toolchain)
    return graph


def _validate_package_context(
    context: PackageContext,
    *,
    graph: PackageGraph,
    verify: bool,
    toolchain: Toolchain | None,
) -> None:
    sources_dir = context.sources_dir
    if not sources_dir.is_dir():
        raise InscriptionError(f"package sources directory `{context.manifest.sources}` does not exist")
    tests_dir = context.tests_dir
    if context.manifest.tests is not None and (tests_dir is None or not tests_dir.is_dir()):
        raise InscriptionError(f"package tests directory `{context.manifest.tests}` does not exist")
    checked_modules: set[str] = set()
    _check_module(context, graph, context.manifest.root_module, kind="root", verify=verify, toolchain=toolchain)
    checked_modules.add(context.manifest.root_module)
    for module in context.manifest.exposed_modules:
        if module in checked_modules:
            continue
        _check_module(context, graph, module, kind="exposed", verify=verify, toolchain=toolchain)
        checked_modules.add(module)


def _check_module(
    context: PackageContext,
    graph: PackageGraph,
    module: str,
    *,
    kind: str,
    verify: bool,
    toolchain: Toolchain | None,
) -> None:
    path = module_path(context.sources_dir, module)
    relative = _relative_for_message(path, context.root)
    if not path.exists():
        if kind == "root":
            raise InscriptionError(f"root module {module} not found at {relative}")
        raise InscriptionError(f"exposed module {module} not found at {relative}")
    resolver = PackageModuleResolver(graph, context)
    program = load_program(path.read_text(), source_path=path, module_root=context.sources_dir, module_path_resolver=resolver)
    if program.module_name != module:
        if kind == "root":
            raise InscriptionError(f"root module {module} resolved to module {program.module_name}; expected {module}")
        raise InscriptionError(f"exposed module {module} resolved to module {program.module_name}; expected {module}")
    analyze(program)
    if verify:
        mlir = emit_mlir(program)
        build_artifacts(mlir, emit="mlir", verify=True, toolchain=toolchain, stem=path.stem)


def _relative_for_message(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def package_stem(manifest: PackageManifest) -> str:
    return manifest.package_name.split(".")[-1]


def package_metadata(manifest: PackageManifest, graph: PackageGraph | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": manifest.package_name,
    }
    if manifest.version is not None:
        payload["version"] = manifest.version
    payload["sources"] = manifest.sources
    if manifest.tests is not None:
        payload["tests"] = manifest.tests
    payload["root_module"] = manifest.root_module
    payload["exposed_modules"] = list(manifest.exposed_modules)
    dependencies: list[dict[str, object]] = []
    for dependency in manifest.dependencies:
        item: dict[str, object] = {
            "name": dependency.name,
            "path": dependency.path,
        }
        if graph is not None:
            dependency_context = graph.contexts_by_name.get(dependency.name)
            if dependency_context is not None and dependency_context.manifest.version is not None:
                item["version"] = dependency_context.manifest.version
        dependencies.append(item)
    if dependencies:
        payload["dependencies"] = dependencies
    return payload


def package_import_modules(manifest: PackageManifest) -> tuple[str, ...]:
    modules: list[str] = []
    seen: set[str] = set()
    for module in (manifest.root_module, *manifest.exposed_modules):
        if module in seen:
            continue
        modules.append(module)
        seen.add(module)
    return tuple(modules)


def load_package_compilation(context: PackageContext, graph: PackageGraph) -> LoadedCompilation:
    imports = "".join(f"Import {module}.\n" for module in package_import_modules(context.manifest))
    resolver = PackageModuleResolver(graph, context)
    return load_compilation(
        imports,
        source_path=context.manifest_path,
        module_root=context.sources_dir,
        module_path_resolver=resolver,
    )


def build_package_artifact(
    root: Path,
    *,
    emit: str = "static-library",
    output: Path | None = None,
    runtime_checks: bool = False,
    opt_level: str = "none",
    save_temps: Path | None = None,
    link_objects: tuple[Path, ...] = (),
    archive_objects: tuple[Path, ...] = (),
    verify: bool = False,
    toolchain: Toolchain | None = None,
) -> PackageBuildResult:
    if emit not in EMIT_MODES:
        raise InscriptionError(f"invalid emit mode {emit}")
    if emit == "object" and output is None:
        raise InscriptionError("object emission requires -o OUTPUT")
    if emit == "executable" and output is None:
        raise InscriptionError("executable emission requires -o OUTPUT")
    if link_objects and emit != "executable":
        raise InscriptionError("--link-object is supported only with --emit executable")
    if archive_objects and emit != "static-library":
        raise InscriptionError("--archive-object is only valid with --emit static-library")
    for path in link_objects:
        if not path.exists():
            raise InscriptionError(f"link object {path} does not exist")
    for path in archive_objects:
        if not path.exists():
            raise InscriptionError(f"archive object {path} does not exist")

    graph = checked_package_graph(root, verify=False, toolchain=toolchain)
    context = graph.root
    stem = package_stem(context.manifest)
    output_path = output
    if emit == "static-library" and output_path is None:
        output_path = context.root / "build" / f"lib{stem}.a"
        output_path.parent.mkdir(parents=True, exist_ok=True)

    if emit in {"interface-json", "c-header"}:
        compilation = load_package_compilation(context, graph)
        interface_context = make_interface_context(compilation, root_dir=context.sources_dir)
        if verify:
            mlir = emit_mlir(compilation.program, runtime_checks=runtime_checks)
            build_artifacts(
                mlir,
                emit="mlir",
                verify=True,
                save_temps=save_temps,
                stem=stem,
                opt_level=opt_level,
                toolchain=toolchain,
            )
        if emit == "interface-json":
            text = emit_interface_json(
                interface_context,
                package_metadata=package_metadata(context.manifest, graph),
                include_root_module=False,
                root_module=context.manifest.root_module,
            )
        else:
            text = emit_c_header(interface_context, include_modules=set(package_import_modules(context.manifest)))
        return PackageBuildResult(context.manifest.package_name, emit, output_path, text=text)

    if emit == "executable":
        root_path = module_path(context.sources_dir, context.manifest.root_module)
        resolver = PackageModuleResolver(graph, context)
        program = load_program(
            root_path.read_text(),
            source_path=root_path,
            module_root=context.sources_dir,
            module_path_resolver=resolver,
        )
        validate_executable_main(program)
        strip_main_for_static_library = False
    else:
        compilation = load_package_compilation(context, graph)
        program = compilation.program
        strip_main_for_static_library = emit == "static-library" and any(
            fn.implementation == "export" for fn in program.functions
        )

    mlir = emit_mlir(program, runtime_checks=runtime_checks)
    artifacts = build_artifacts(
        mlir,
        emit=emit,
        verify=verify,
        save_temps=save_temps,
        stem=stem,
        opt_level=opt_level,
        executable_output=output_path if emit == "executable" else None,
        link_objects=link_objects,
        static_library_output=output_path if emit == "static-library" else None,
        archive_objects=archive_objects,
        strip_main_for_static_library=strip_main_for_static_library,
        toolchain=toolchain,
    )
    if emit in {"executable", "static-library"}:
        return PackageBuildResult(context.manifest.package_name, emit, output_path)
    selected = selected_artifact(artifacts, emit)
    if isinstance(selected, bytes):
        return PackageBuildResult(context.manifest.package_name, emit, output_path, data=selected)
    return PackageBuildResult(context.manifest.package_name, emit, output_path, text=selected)


def package_test_files(context: PackageContext) -> tuple[Path, ...]:
    tests_dir = context.tests_dir
    if tests_dir is None or not tests_dir.is_dir():
        return ()
    return tuple(sorted(tests_dir.rglob("*.ins")))


def list_package_tests(
    root: Path,
    *,
    filter_text: str | None = None,
    include_dependencies: bool = False,
) -> tuple[str, ...] | str:
    graph = checked_package_graph(root, verify=False)
    contexts = _test_contexts(graph, include_dependencies=include_dependencies)
    if not any(package_test_files(context) for context in contexts):
        return "no tests found"
    displays: list[str] = []
    for context in contexts:
        for path in package_test_files(context):
            prefix = _package_test_prefix(path, context)
            resolver = PackageModuleResolver(graph, context)
            displays.extend(
                list_tests(
                    path,
                    module_root=context.sources_dir,
                    module_path_resolver=resolver,
                    filter_text=filter_text,
                    display_prefix=prefix,
                )
            )
    if not displays:
        if filter_text is None:
            return "no tests found"
        return f"no tests matched filter `{filter_text}`"
    return tuple(displays)


def run_package_tests(
    root: Path,
    *,
    filter_text: str | None = None,
    include_dependencies: bool = False,
    runtime_checks: bool = False,
    opt_level: str = "none",
    save_temps: Path | None = None,
    toolchain: Toolchain | None = None,
) -> PackageTestSummary | str:
    graph = checked_package_graph(root, verify=False)
    contexts = _test_contexts(graph, include_dependencies=include_dependencies)
    if not any(package_test_files(context) for context in contexts):
        return "no tests found"
    all_results: list[TestRunItem] = []
    passed = 0
    failed = 0
    matched_any = False
    for context in contexts:
        for path in package_test_files(context):
            prefix = _package_test_prefix(path, context)
            resolver = PackageModuleResolver(graph, context)
            summary = run_tests(
                path,
                module_root=context.sources_dir,
                module_path_resolver=resolver,
                runtime_checks=runtime_checks,
                opt_level=opt_level,
                save_temps=save_temps,
                filter_text=filter_text,
                toolchain=toolchain,
                display_prefix=prefix,
            )
            if isinstance(summary, str):
                continue
            matched_any = True
            for result in summary.results:
                all_results.append(result)
                if result.passed:
                    passed += 1
                else:
                    failed += 1
    if not matched_any or not all_results:
        if filter_text is None:
            return "no tests found"
        return f"no tests matched filter `{filter_text}`"
    return PackageTestSummary(graph.root.manifest.package_name, passed, failed, tuple(all_results))


def _test_contexts(graph: PackageGraph, *, include_dependencies: bool) -> tuple[PackageContext, ...]:
    if include_dependencies:
        return graph.packages
    return (graph.root,)


def _package_test_prefix(path: Path, context: PackageContext) -> str:
    return f"{context.manifest.package_name}::{_relative_for_message(path.resolve(), context.root.resolve())}"


def package_format_files(context: PackageContext) -> tuple[Path, ...]:
    paths: list[Path] = []
    seen: set[Path] = set()

    def append(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen or not path.exists() or not path.is_file():
            return
        seen.add(resolved)
        paths.append(path)

    append(context.manifest_path)
    append(context.root / "build.ins")
    if context.sources_dir.is_dir():
        for path in sorted(context.sources_dir.rglob("*.ins")):
            if _is_package_format_path(path, context.root):
                append(path)
    tests_dir = context.tests_dir
    if tests_dir is not None and tests_dir.is_dir():
        for path in sorted(tests_dir.rglob("*.ins")):
            if _is_package_format_path(path, context.root):
                append(path)
    return tuple(paths)


def format_package(
    root: Path,
    *,
    check: bool,
    in_place: bool,
    include_dependencies: bool = False,
    include_book: bool = False,
) -> PackageFormatResult:
    if check and in_place:
        raise InscriptionError("--check cannot be used with --in-place")
    if not check and not in_place:
        raise InscriptionError("package format requires --check or --in-place")
    if include_book and in_place:
        raise InscriptionError("package format --include-book --in-place is not supported in v0.57")

    graph = load_package_graph(root)
    contexts = graph.packages if include_dependencies else (graph.root,)
    formatted_by_path: dict[Path, str] = {}
    failures: list[str] = []
    all_files: list[Path] = []
    changed: list[Path] = []

    from .formatter import format_file

    for context in contexts:
        for path in package_format_files(context):
            all_files.append(path)
            original = path.read_text()
            try:
                formatted = format_file(path)
            except InscriptionError as exc:
                raise InscriptionError(f"{_relative_for_message(path, context.root)}: {exc}") from exc
            formatted_by_path[path] = formatted
            if formatted != original:
                changed.append(path)
                failures.append(f"formatting check failed: {_relative_for_message(path, context.root)} is not formatted")
        if include_book:
            _check_package_book_examples(context)

    if check and failures:
        raise InscriptionError("\n".join(failures))
    if in_place:
        for path in changed:
            path.write_text(formatted_by_path[path])
    return PackageFormatResult(graph.root.manifest.package_name, tuple(all_files), tuple(changed))


def _is_package_format_path(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    parts = relative.parts
    if any(part.startswith(".") for part in parts):
        return False
    if "__pycache__" in parts or ".venv" in parts or ".git" in parts:
        return False
    if parts and parts[0] == "build":
        return False
    if len(parts) >= 2 and parts[0] == "book" and parts[1] == "book":
        return False
    return True


def _check_package_book_examples(context: PackageContext) -> None:
    book_toml = context.root / "book" / "book.toml"
    if not book_toml.exists():
        return
    checker = context.root / "book" / "tools" / "check_book_examples.py"
    if not checker.exists():
        raise InscriptionError("package format --include-book requires book/tools/check_book_examples.py")
    completed = subprocess.run(
        [sys.executable, str(Path("book") / "tools" / "check_book_examples.py")],
        cwd=context.root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise InscriptionError("package book example formatting check failed")


def clean_package(
    root: Path,
    *,
    include_dependencies: bool = False,
    dry_run: bool = False,
) -> tuple[PackageCleanResult, ...]:
    graph = load_package_graph(root)
    contexts = graph.packages if include_dependencies else (graph.root,)
    results: list[PackageCleanResult] = []
    for context in contexts:
        target = context.root / "build"
        removed = _clean_package_build_dir(context, target, dry_run=dry_run)
        results.append(PackageCleanResult(context.manifest.package_name, context.root, target, removed, dry_run))
    return tuple(results)


def _clean_package_build_dir(context: PackageContext, target: Path, *, dry_run: bool) -> bool:
    root = context.root.resolve()
    if target.is_symlink():
        raise InscriptionError("package clean refuses to remove symlink build")
    if not target.exists():
        return False
    try:
        target.resolve(strict=False).relative_to(root)
    except ValueError:
        raise InscriptionError("package clean target build is outside the package root")
    if not target.is_dir():
        raise InscriptionError("package clean expected build to be a directory")
    if dry_run:
        return True
    shutil.rmtree(target)
    return True


def release_package(
    root: Path,
    *,
    output_dir: Path | None = None,
    name: str | None = None,
    include_executable: bool = False,
    include_book: bool = False,
    runtime_checks: bool = False,
    opt_level: str = "none",
    verify: bool = False,
    clean: bool = False,
    dry_run: bool = False,
    archive: bool = False,
    checksum: bool = False,
    save_temps: Path | None = None,
    toolchain: Toolchain | None = None,
) -> PackageReleaseResult:
    graph = checked_package_graph(root, verify=False, toolchain=toolchain)
    context = graph.root
    stem = package_stem(context.manifest)
    release_dir = _release_output_dir(context, output_dir=output_dir, name=name)
    artifacts = _release_artifacts(stem, include_executable=include_executable, include_book=include_book)
    archive_path = _release_archive_path(release_dir) if archive else None
    checksum_path = release_dir / "checksums.sha256" if checksum else None
    archive_checksum_path = (
        archive_path.with_suffix(archive_path.suffix + ".sha256") if archive_path is not None and checksum else None
    )

    if include_book and not (context.root / "book" / "book.toml").exists():
        raise InscriptionError("release with book requires book/book.toml")
    if dry_run:
        return PackageReleaseResult(
            context.manifest.package_name,
            release_dir,
            artifacts,
            archive_path=archive_path,
            checksum_path=checksum_path,
            archive_checksum_path=archive_checksum_path,
            dry_run=True,
        )

    _prepare_release_output_dir(release_dir, clean=clean)
    (release_dir / "lib").mkdir(parents=True, exist_ok=True)
    (release_dir / "include").mkdir(parents=True, exist_ok=True)

    build_package_artifact(
        context.root,
        emit="static-library",
        output=release_dir / "lib" / f"lib{stem}.a",
        runtime_checks=runtime_checks,
        opt_level=opt_level,
        save_temps=_release_save_temps(save_temps, "static-library"),
        verify=verify,
        toolchain=toolchain,
    )
    header = build_package_artifact(
        context.root,
        emit="c-header",
        output=release_dir / "include" / f"{stem}.h",
        runtime_checks=runtime_checks,
        opt_level=opt_level,
        save_temps=_release_save_temps(save_temps, "c-header"),
        verify=verify,
        toolchain=toolchain,
    )
    assert header.text is not None
    (release_dir / "include" / f"{stem}.h").write_text(header.text)
    interface = build_package_artifact(
        context.root,
        emit="interface-json",
        output=release_dir / "interface.json",
        runtime_checks=runtime_checks,
        opt_level=opt_level,
        save_temps=_release_save_temps(save_temps, "interface-json"),
        verify=verify,
        toolchain=toolchain,
    )
    assert interface.text is not None
    (release_dir / "interface.json").write_text(interface.text)

    if include_executable:
        (release_dir / "bin").mkdir(parents=True, exist_ok=True)
        build_package_artifact(
            context.root,
            emit="executable",
            output=release_dir / "bin" / stem,
            runtime_checks=runtime_checks,
            opt_level=opt_level,
            save_temps=_release_save_temps(save_temps, "executable"),
            verify=verify,
            toolchain=toolchain,
        )

    if include_book:
        _build_release_book(context, release_dir / "docs")

    shutil.copyfile(context.manifest_path, release_dir / MANIFEST_NAME)
    (release_dir / "release.json").write_text(
        _release_metadata(
            context.manifest,
            artifacts,
            checksums=checksum,
            archive_path=archive_path,
            release_dir=release_dir,
        )
    )
    if checksum_path is not None:
        _write_release_checksums(release_dir, checksum_path)
    if archive_path is not None:
        _create_release_archive(release_dir, archive_path)
    if archive_path is not None and archive_checksum_path is not None:
        _write_archive_checksum(archive_path, archive_checksum_path)
    return PackageReleaseResult(
        context.manifest.package_name,
        release_dir,
        artifacts,
        archive_path=archive_path,
        checksum_path=checksum_path,
        archive_checksum_path=archive_checksum_path,
    )


def _release_output_dir(context: PackageContext, *, output_dir: Path | None, name: str | None) -> Path:
    if output_dir is not None:
        return output_dir.resolve()
    if name is not None:
        _validate_release_name(name)
    basename = name or _default_release_basename(context.manifest)
    return context.root / "build" / "release" / basename


def _validate_release_name(name: str) -> None:
    if not name:
        raise InscriptionError("release name must not be empty")
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise InscriptionError("release name must not contain path separators")


def _default_release_basename(manifest: PackageManifest) -> str:
    stem = package_stem(manifest)
    if manifest.version is None:
        return stem
    return f"{stem}-{manifest.version}"


def _release_artifacts(stem: str, *, include_executable: bool, include_book: bool) -> tuple[PackageReleaseArtifact, ...]:
    artifacts = [
        PackageReleaseArtifact("static-library", f"lib/lib{stem}.a"),
        PackageReleaseArtifact("c-header", f"include/{stem}.h"),
        PackageReleaseArtifact("interface-json", "interface.json"),
    ]
    if include_executable:
        artifacts.append(PackageReleaseArtifact("executable", f"bin/{stem}"))
    if include_book:
        artifacts.append(PackageReleaseArtifact("book", "docs/index.html"))
    return tuple(artifacts)


def _prepare_release_output_dir(output: Path, *, clean: bool) -> None:
    if output.is_symlink():
        raise InscriptionError("release output path must not be a symlink")
    if output.exists() and not output.is_dir():
        raise InscriptionError("release output path exists and is not a directory")
    if output.exists() and any(output.iterdir()):
        if not clean:
            raise InscriptionError("release output directory already exists; use --clean to replace it")
        resolved = output.resolve()
        if resolved.parent == resolved:
            raise InscriptionError("release output path is not safe to clean")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)


def _release_save_temps(save_temps: Path | None, name: str) -> Path | None:
    if save_temps is None:
        return None
    return save_temps / name


def _release_archive_path(release_dir: Path) -> Path:
    return release_dir.with_name(release_dir.name + ".tar.gz")


def _write_release_checksums(release_dir: Path, checksum_path: Path) -> None:
    lines: list[str] = []
    for path in _release_checksum_files(release_dir):
        relative = path.relative_to(release_dir).as_posix()
        lines.append(f"{_sha256_file(path)}  {relative}")
    try:
        checksum_path.write_text("\n".join(lines) + "\n")
    except OSError as exc:
        raise InscriptionError("failed to write checksum file checksums.sha256") from exc


def _release_checksum_files(release_dir: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in sorted(release_dir.rglob("*"), key=lambda candidate: candidate.relative_to(release_dir).as_posix()):
        if path.is_symlink():
            relative = path.relative_to(release_dir).as_posix()
            raise InscriptionError(f"release checksums cannot include symlink {relative}")
        if not path.is_file():
            continue
        if path.relative_to(release_dir).as_posix() == "checksums.sha256":
            continue
        files.append(path)
    return tuple(files)


def _write_archive_checksum(archive_path: Path, checksum_path: Path) -> None:
    try:
        checksum_path.write_text(f"{_sha256_file(archive_path)}  {archive_path.name}\n")
    except OSError as exc:
        raise InscriptionError(f"failed to write checksum file {checksum_path.name}") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_release_archive(release_dir: Path, archive_path: Path) -> None:
    if archive_path.is_dir():
        raise InscriptionError("release archive path exists and is a directory")
    if archive_path.is_symlink():
        raise InscriptionError("release archive path must not be a symlink")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with archive_path.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gzip_file:
                with tarfile.open(mode="w", fileobj=gzip_file, format=tarfile.USTAR_FORMAT) as archive:
                    _add_release_archive_directory(archive, release_dir.name)
                    for path in _release_archive_paths(release_dir):
                        relative = path.relative_to(release_dir).as_posix()
                        archive_name = f"{release_dir.name}/{relative}"
                        if path.is_dir():
                            _add_release_archive_directory(archive, archive_name)
                        elif path.is_file():
                            _add_release_archive_file(archive, path, archive_name, relative)
        return
    except OSError as exc:
        raise InscriptionError(f"failed to create release archive {archive_path}") from exc
    except tarfile.TarError as exc:
        raise InscriptionError(f"failed to create release archive {archive_path}") from exc


def _release_archive_paths(release_dir: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for path in sorted(release_dir.rglob("*"), key=lambda candidate: candidate.relative_to(release_dir).as_posix()):
        if path.is_symlink():
            relative = path.relative_to(release_dir).as_posix()
            raise InscriptionError(f"release archive cannot include symlink {relative}")
        paths.append(path)
    return tuple(paths)


def _add_release_archive_directory(archive: tarfile.TarFile, name: str) -> None:
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    _normalize_tar_info(info)
    archive.addfile(info)


def _add_release_archive_file(archive: tarfile.TarFile, path: Path, name: str, relative: str) -> None:
    data = path.read_bytes()
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o755 if relative.startswith("bin/") else 0o644
    _normalize_tar_info(info)
    archive.addfile(info, io.BytesIO(data))


def _normalize_tar_info(info: tarfile.TarInfo) -> None:
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""


def _build_release_book(context: PackageContext, output: Path) -> None:
    mdbook = shutil.which("mdbook")
    if mdbook is None:
        raise InscriptionError("release with book requires mdbook, but mdbook was not found")
    if output.exists():
        if output.is_symlink():
            raise InscriptionError("release docs output path must not be a symlink")
        if output.is_dir():
            shutil.rmtree(output)
        else:
            output.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [mdbook, "build", str(context.root / "book"), "--dest-dir", str(output)],
        cwd=context.root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise InscriptionError("release book build failed")


def _release_metadata(
    manifest: PackageManifest,
    artifacts: tuple[PackageReleaseArtifact, ...],
    *,
    checksums: bool,
    archive_path: Path | None,
    release_dir: Path,
) -> str:
    payload = {
        "format": RELEASE_FORMAT,
        "package": {
            "name": manifest.package_name,
            "version": manifest.version,
        },
        "inscription": {
            "version": INSCRIPTION_VERSION,
            "language_version": LANGUAGE_VERSION,
        },
        "artifacts": [{"kind": artifact.kind, "path": artifact.path} for artifact in artifacts],
    }
    if checksums:
        payload["checksums"] = "checksums.sha256"
    if archive_path is not None:
        archive_relative = Path(os.path.relpath(archive_path, release_dir)).as_posix()
        payload["archive"] = {"path": archive_relative}
    return json.dumps(payload, indent=2) + "\n"


def init_package(
    root: Path,
    *,
    name: str | None = None,
    executable: bool = False,
    library: bool = False,
    with_book: bool = False,
    force: bool = False,
) -> PackageInitResult:
    if executable and library:
        raise InscriptionError("--library cannot be used with --executable")
    root = root.resolve()
    if root.exists() and not root.is_dir():
        raise InscriptionError(f"package root {root} is not a directory")
    package_name = _resolve_init_package_name(root, name)
    files = _package_template_files(package_name, executable=executable, with_book=with_book)
    target_paths = tuple(root / relative for relative, _ in files)
    if not force:
        for path in sorted(target_paths, key=lambda item: item.relative_to(root).as_posix()):
            if path.exists():
                raise InscriptionError(f"package init would overwrite {path.relative_to(root).as_posix()}; use --force to overwrite")
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for relative, content in files:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        written.append(target)
    return PackageInitResult(root, package_name, tuple(written))


def new_package(
    path: Path,
    *,
    name: str | None = None,
    executable: bool = False,
    library: bool = False,
    with_book: bool = False,
    force: bool = False,
) -> PackageInitResult:
    path = path.resolve()
    if path.exists():
        if not path.is_dir():
            raise InscriptionError("package new target already exists and is not empty; use --force to overwrite")
        if any(path.iterdir()) and not force:
            raise InscriptionError("package new target already exists and is not empty; use --force to overwrite")
    return init_package(
        path,
        name=name,
        executable=executable,
        library=library,
        with_book=with_book,
        force=force,
    )


def _resolve_init_package_name(root: Path, explicit: str | None) -> str:
    if explicit is not None:
        return _validate_init_package_name(explicit)
    inferred = _infer_package_name(root.name)
    if inferred is None:
        raise InscriptionError("package name could not be inferred; pass --name NAME")
    return inferred


def _validate_init_package_name(name: str) -> str:
    try:
        return validate_module_name(name)
    except InscriptionError as exc:
        raise InscriptionError(f"invalid package name {name}") from exc


def _infer_package_name(path_name: str) -> str | None:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", path_name) if part]
    if not parts:
        return None
    candidate = "".join(part[:1].upper() + part[1:] for part in parts)
    try:
        return _validate_init_package_name(candidate)
    except InscriptionError:
        return None


def _package_template_files(
    package_name: str,
    *,
    executable: bool,
    with_book: bool,
) -> tuple[tuple[Path, str], ...]:
    source_relative = Path("src").joinpath(*package_name.split(".")).with_suffix(".ins")
    files: list[tuple[Path, str]] = [
        (Path(MANIFEST_NAME), _package_manifest_template(package_name)),
        (Path("build.ins"), _build_script_template(executable=executable)),
        (source_relative, _executable_source_template(package_name) if executable else _library_source_template(package_name)),
        (Path("tests") / "basic.ins", _executable_test_template(package_name) if executable else _library_test_template(package_name)),
    ]
    if with_book:
        files.extend(_book_template_files(package_name))
    return tuple(files)


def _package_manifest_template(package_name: str) -> str:
    return (
        f"//! Package manifest for {package_name}.\n\n"
        f"Package {package_name}.\n\n"
        'Version "0.1.0".\n\n'
        'Sources are in "src".\n'
        'Tests are in "tests".\n\n'
        f"Root module is {package_name}.\n\n"
        f"Expose module {package_name}.\n"
    )


def _build_script_template(*, executable: bool) -> str:
    if not executable:
        return (
            "Import Build.\n\n"
            "To build package package: Build.Package.\n"
            "Build.standard package workflow.\n"
        )
    return (
        "Import Build.\n\n"
        "To build package package: Build.Package.\n"
        "Build.standard package workflow.\n"
        "// Add this when you want an executable artifact:\n"
        "// Build.executable for package.\n"
    )


def _library_source_template(package_name: str) -> str:
    return (
        f"Module {package_name}.\n\n"
        "/// Adds two numbers.\n"
        "To add left: i32 and right: i32, giving i32, exported as ins_add.\n"
        "Give left plus right.\n"
    )


def _library_test_template(package_name: str) -> str:
    return (
        f"Import {package_name}.\n\n"
        "Test addition works.\n"
        f"Expect {package_name}.add 20 and 22 is equal to 42.\n"
    )


def _executable_source_template(package_name: str) -> str:
    return (
        f"Module {package_name}.\n\n"
        "To main, giving i32.\n"
        "Give 42.\n"
    )


def _executable_test_template(package_name: str) -> str:
    return (
        f"Import {package_name}.\n\n"
        "Test main value is stable.\n"
        f"Expect {package_name}.main is equal to 42.\n"
    )


def _book_template_files(package_name: str) -> tuple[tuple[Path, str], ...]:
    return (
        (
            Path("book") / "book.toml",
            (
                "[book]\n"
                f'title = "{package_name}"\n'
                f'authors = ["{package_name} contributors"]\n'
                'language = "en"\n'
                'src = "src"\n\n'
                "[output.html]\n"
                'default-theme = "ayu"\n'
                'preferred-dark-theme = "ayu"\n'
            ),
        ),
        (
            Path("book") / "src" / "SUMMARY.md",
            "# Summary\n\n[Introduction](introduction.md)\n",
        ),
        (
            Path("book") / "src" / "introduction.md",
            (
                f"# {package_name}\n\n"
                f"This is the documentation for {package_name}.\n\n"
                "```inscription,check\n"
                "To main, giving i32.\n"
                "Give 7.\n"
                "```\n"
            ),
        ),
        (
            Path("book") / "tools" / "check_book_examples.py",
            (
                "from __future__ import annotations\n\n"
                'print("checked generated package book examples")\n'
            ),
        ),
    )
