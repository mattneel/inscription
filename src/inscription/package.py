from __future__ import annotations

import re
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

MANIFEST_NAME = "package.ins"
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')


@dataclass(frozen=True)
class ManifestCommentInfo:
    source: str
    comments: tuple[SourceComment, ...]
    module_documentation: str | None
    comments_by_line: dict[int, tuple[SourceComment, ...]]


@dataclass(frozen=True)
class PackageManifest:
    package_name: str
    sources: str
    root_module: str
    version: str | None = None
    tests: str | None = None
    exposed_modules: tuple[str, ...] = ()
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
    raise InscriptionError("package manifests support only Package, Version, Sources, Tests, Root module, and Expose module declarations", line)


def check_package(root: Path, *, verify: bool = False, toolchain: Toolchain | None = None) -> PackageContext:
    context = load_package_context(root)
    _validate_package_context(context, verify=verify, toolchain=toolchain)
    return context


def _validate_package_context(context: PackageContext, *, verify: bool, toolchain: Toolchain | None) -> None:
    sources_dir = context.sources_dir
    if not sources_dir.is_dir():
        raise InscriptionError(f"package sources directory `{context.manifest.sources}` does not exist")
    tests_dir = context.tests_dir
    if context.manifest.tests is not None and (tests_dir is None or not tests_dir.is_dir()):
        raise InscriptionError(f"package tests directory `{context.manifest.tests}` does not exist")
    checked_modules: set[str] = set()
    _check_module(context, context.manifest.root_module, kind="root", verify=verify, toolchain=toolchain)
    checked_modules.add(context.manifest.root_module)
    for module in context.manifest.exposed_modules:
        if module in checked_modules:
            continue
        _check_module(context, module, kind="exposed", verify=verify, toolchain=toolchain)
        checked_modules.add(module)


def _check_module(
    context: PackageContext,
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
    program = load_program(path.read_text(), source_path=path, module_root=context.sources_dir)
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


def package_metadata(manifest: PackageManifest) -> dict[str, object]:
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


def load_package_compilation(context: PackageContext) -> LoadedCompilation:
    imports = "".join(f"Import {module}.\n" for module in package_import_modules(context.manifest))
    return load_compilation(imports, source_path=context.manifest_path, module_root=context.sources_dir)


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

    context = check_package(root, verify=False, toolchain=toolchain)
    stem = package_stem(context.manifest)
    output_path = output
    if emit == "static-library" and output_path is None:
        output_path = context.root / "build" / f"lib{stem}.a"
        output_path.parent.mkdir(parents=True, exist_ok=True)

    if emit in {"interface-json", "c-header"}:
        compilation = load_package_compilation(context)
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
                package_metadata=package_metadata(context.manifest),
                include_root_module=False,
                root_module=context.manifest.root_module,
            )
        else:
            text = emit_c_header(interface_context)
        return PackageBuildResult(context.manifest.package_name, emit, output_path, text=text)

    if emit == "executable":
        root_path = module_path(context.sources_dir, context.manifest.root_module)
        program = load_program(root_path.read_text(), source_path=root_path, module_root=context.sources_dir)
        validate_executable_main(program)
        strip_main_for_static_library = False
    else:
        compilation = load_package_compilation(context)
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


def list_package_tests(root: Path, *, filter_text: str | None = None) -> tuple[str, ...] | str:
    context = check_package(root, verify=False)
    files = package_test_files(context)
    if not files:
        return "no tests found"
    displays: list[str] = []
    for path in files:
        prefix = _package_test_prefix(path, context.root)
        displays.extend(list_tests(path, module_root=context.sources_dir, filter_text=filter_text, display_prefix=prefix))
    if not displays:
        if filter_text is None:
            return "no tests found"
        return f"no tests matched filter `{filter_text}`"
    return tuple(displays)


def run_package_tests(
    root: Path,
    *,
    filter_text: str | None = None,
    runtime_checks: bool = False,
    opt_level: str = "none",
    save_temps: Path | None = None,
    toolchain: Toolchain | None = None,
) -> PackageTestSummary | str:
    context = check_package(root, verify=False)
    files = package_test_files(context)
    if not files:
        return "no tests found"
    all_results: list[TestRunItem] = []
    passed = 0
    failed = 0
    matched_any = False
    for path in files:
        prefix = _package_test_prefix(path, context.root)
        summary = run_tests(
            path,
            module_root=context.sources_dir,
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
    return PackageTestSummary(context.manifest.package_name, passed, failed, tuple(all_results))


def _package_test_prefix(path: Path, package_root: Path) -> str:
    return _relative_for_message(path.resolve(), package_root.resolve())
