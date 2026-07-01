from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .diagnostics import InscriptionError
from .package import (
    PackageBuildResult,
    PackageContext,
    PackageTestSummary,
    build_package_artifact,
    check_package,
    clean_package,
    format_package,
    load_package_context,
    release_package,
    run_package_tests,
)
from .parser import (
    SourceComment,
    _split_punctuation_sentences_no_comments,
    collect_source_comments,
)

BUILD_SCRIPT_NAME = "build.ins"
_BUILD_STEP_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_STANDARD_WORKFLOW_PHRASE = "Build.standard package workflow"
_BUILD_CALLS: dict[str, str] = {
    "Build.clean package named": "package-clean",
    "Build.release archive package named": "package-release-archive",
    "Build.release package named": "package-release",
    "Build.format check named": "package-format-check",
    "Build.format package named": "package-format-in-place",
    "Build.check package named": "package-check",
    "Build.tests including dependencies named": "package-tests-with-dependencies",
    "Build.tests named": "package-tests",
    "Build.book checked named": "book-check",
    "Build.book named": "book",
    "Build.static library named": "static-library",
    "Build.executable named": "executable",
    "Build.c header named": "c-header",
    "Build.interface json named": "interface-json",
    "Build.llvm ir named": "llvm-ir",
    "Build.object named": "object",
    "Build.mlir named": "mlir",
    "Build.lowered mlir named": "lowered-mlir",
}
_PACKAGE_DEFAULT_CALLS: dict[str, tuple[str, str]] = {
    "Build.clean package": ("clean", "package-clean"),
    "Build.release archive package": ("archive", "package-release-archive"),
    "Build.release package": ("bundle", "package-release"),
    "Build.static library for package": ("library", "static-library"),
    "Build.executable for package": ("app", "executable"),
    "Build.c header for package": ("header", "c-header"),
    "Build.interface json for package": ("interface", "interface-json"),
    "Build.llvm ir for package": ("llvm-ir", "llvm-ir"),
    "Build.object for package": ("object", "object"),
    "Build.mlir for package": ("mlir", "mlir"),
    "Build.lowered mlir for package": ("lowered-mlir", "lowered-mlir"),
    "Build.book checked for package": ("book-check", "book-check"),
    "Build.book for package": ("book", "book"),
}
_OUTPUT_SUFFIXES: dict[str, tuple[str, str]] = {
    "static-library": ("lib", ".a"),
    "executable": ("", ""),
    "c-header": ("", ".h"),
    "interface-json": ("", ".json"),
    "llvm-ir": ("", ".ll"),
    "object": ("", ".o"),
    "mlir": ("", ".mlir"),
    "lowered-mlir": ("", ".lowered.mlir"),
}
_ARTIFACT_EMITS = frozenset(_OUTPUT_SUFFIXES)
_STEP_DISPLAY: dict[str, str] = {
    "package-clean": "clean package",
    "package-release-archive": "release archive",
    "package-release": "release package",
    "package-format-check": "format check",
    "package-format-in-place": "format package",
    "package-check": "check package",
    "package-tests": "tests",
    "package-tests-with-dependencies": "tests including dependencies",
    "book": "book",
    "book-check": "book checked",
}


@dataclass(frozen=True)
class BuildStep:
    name: str
    emit: str
    line: int
    dependencies: tuple[str, ...] = ()
    package_default: bool = False


@dataclass(frozen=True)
class BuildScript:
    path: Path
    steps: tuple[BuildStep, ...]
    comments: tuple[SourceComment, ...] = ()
    default_step: str | None = None


@dataclass(frozen=True)
class BuildExecutionResult:
    step: BuildStep
    output_path: Path | None = None
    package_result: PackageBuildResult | None = None
    package_context: PackageContext | None = None
    test_summary: PackageTestSummary | str | None = None
    failed: bool = False

    @property
    def exit_status(self) -> int:
        if self.failed:
            return 1
        if isinstance(self.test_summary, PackageTestSummary):
            return self.test_summary.exit_status
        return 0


def load_build_script(package_root: Path) -> BuildScript:
    root = package_root.resolve()
    path = root / BUILD_SCRIPT_NAME
    if not path.exists():
        raise InscriptionError(f"build script not found at {BUILD_SCRIPT_NAME}")
    source = path.read_text()
    try:
        return parse_build_script(source, path=path)
    except InscriptionError as exc:
        raise exc.attach_source(source, path) from exc


def parse_build_script(source: str, *, path: Path | None = None) -> BuildScript:
    comments = collect_source_comments(source)
    sentences = _split_punctuation_sentences_no_comments(comments.source)
    if not sentences:
        raise InscriptionError("build script must import Build")

    imports: list[str] = []
    build_sentence_index: int | None = None
    build_line: int | None = None
    build_text: str | None = None
    for index, sentence in enumerate(sentences):
        text = sentence.text
        if text.startswith("Import "):
            module = text[len("Import ") :].strip()
            if module != "Build":
                raise InscriptionError("build scripts may only import Build in v0.50", sentence.line)
            imports.append(module)
            continue
        if text.startswith("External "):
            raise InscriptionError("build scripts do not support external phrase declarations", sentence.line)
        if text.startswith("Test "):
            raise InscriptionError("build scripts do not support test declarations", sentence.line)
        if text.startswith("Module "):
            raise InscriptionError("build scripts do not support module declarations", sentence.line)
        if text.startswith("To "):
            if build_sentence_index is None:
                build_sentence_index = index
                build_line = sentence.line
                build_text = text
                continue
            raise InscriptionError("build scripts do not support additional phrase declarations in v0.50", sentence.line)
        if _is_source_top_level(text):
            raise InscriptionError("build scripts support only Import Build and the build phrase in v0.50", sentence.line)
        if build_sentence_index is None:
            raise InscriptionError("build script must define `To build package package: Build.Package.`", sentence.line)

    if "Build" not in imports:
        first_line = sentences[0].line if sentences else None
        raise InscriptionError("build scripts must import Build", first_line)
    if build_sentence_index is None or build_line is None or build_text is None:
        raise InscriptionError("build script must define `To build package package: Build.Package.`")
    _validate_build_phrase(build_text, build_line)

    steps: list[BuildStep] = []
    seen: set[str] = set()
    default_step: str | None = None
    package_root = path.parent if path is not None else None
    body_sentences = sentences[build_sentence_index + 1 :]
    for sentence in body_sentences:
        text = sentence.text
        if text.startswith("To "):
            raise InscriptionError("build scripts do not support additional phrase declarations in v0.50", sentence.line)
        if text.startswith("External "):
            raise InscriptionError("build scripts do not support external phrase declarations", sentence.line)
        if text.startswith("Test "):
            raise InscriptionError("build scripts do not support test declarations", sentence.line)
        if text.startswith("Import "):
            raise InscriptionError("build scripts may only import Build in v0.50", sentence.line)
        if text.startswith("Let "):
            # v0.50 accepts pure setup statements syntactically, but artifact names
            # intentionally remain string literals in Build API calls.
            continue
        if text == _STANDARD_WORKFLOW_PHRASE:
            for standard_step in _standard_workflow_steps(sentence.line, package_root=package_root):
                _append_build_step(steps, seen, standard_step, sentence.line)
            if default_step is not None:
                raise InscriptionError("build script declares default step more than once", sentence.line)
            default_step = "ci"
            continue
        default_name = _parse_default_step(text, sentence.line)
        if default_name is not None:
            if default_step is not None:
                raise InscriptionError("build script declares default step more than once", sentence.line)
            default_step = default_name
            continue
        step = _parse_build_call(text, sentence.line)
        if step is None:
            raise InscriptionError("build script body supports only Build artifact requests in v0.50", sentence.line)
        _append_build_step(steps, seen, step, sentence.line)
    script = BuildScript(path or Path(BUILD_SCRIPT_NAME), tuple(steps), comments.comments, default_step)
    _validate_build_script_graph(script)
    return script


def _append_build_step(steps: list[BuildStep], seen: set[str], step: BuildStep, line: int) -> None:
    if step.name in seen:
        raise InscriptionError(f"build step {step.name} is already defined", line)
    seen.add(step.name)
    steps.append(step)


def _standard_workflow_steps(line: int, *, package_root: Path | None) -> tuple[BuildStep, ...]:
    steps = [
        BuildStep("format", "package-format-check", line),
        BuildStep("check", "package-check", line),
        BuildStep("tests", "package-tests", line),
        BuildStep("library", "static-library", line, package_default=True),
        BuildStep("header", "c-header", line, package_default=True),
        BuildStep("interface", "interface-json", line, package_default=True),
    ]
    ci_dependencies = ["format", "check", "tests"]
    if _standard_workflow_has_book(package_root):
        steps.append(BuildStep("book-check", "book-check", line, package_default=True))
        ci_dependencies.append("book-check")
    steps.append(BuildStep("ci", "group", line, tuple(ci_dependencies)))
    steps.append(BuildStep("release", "group", line, ("ci", "library", "header", "interface")))
    return tuple(steps)


def _standard_workflow_has_book(package_root: Path | None) -> bool:
    return package_root is not None and (package_root / "book" / "book.toml").exists()


def _is_source_top_level(text: str) -> bool:
    return text.startswith(
        (
            "Module ",
            "Type ",
            "Constant ",
            "Check ",
            "Record ",
            "Layout record ",
            "Packed layout record ",
            "Enum ",
            "Union ",
            "External ",
            "Test ",
            "Depend ",
            "Package ",
            "Version ",
            "Sources ",
            "Root ",
            "Expose ",
        )
    )


def _validate_build_phrase(text: str, line: int) -> None:
    if "," in text and "giving" in text:
        raise InscriptionError("build phrase must not return a value", line)
    if text != "To build package package: Build.Package":
        if text.startswith("To build package ") and text.endswith(": Build.Package"):
            raise InscriptionError("build phrase parameter must be named package in v0.55", line)
        if text.startswith("To build package"):
            raise InscriptionError("build phrase parameter must have type Build.Package", line)
        raise InscriptionError("build script must define `To build package package: Build.Package.`", line)


def _parse_build_call(text: str, line: int) -> BuildStep | None:
    group = _parse_group_step(text, line)
    if group is not None:
        return group
    for phrase, (name, emit) in _PACKAGE_DEFAULT_CALLS.items():
        if text == phrase:
            return BuildStep(name, emit, line, package_default=True)
    for prefix, emit in _BUILD_CALLS.items():
        if not text.startswith(prefix + " "):
            continue
        literal = text[len(prefix) :].strip()
        if not (literal.startswith('"') and literal.endswith('"')):
            raise InscriptionError("build artifact names must be string literals in v0.50", line)
        name = _parse_build_string(literal, line)
        _validate_step_name(name, line)
        return BuildStep(name, emit, line)
    if text.startswith("Build.") and " for " in text:
        raise InscriptionError("package-aware build steps must use `for package`", line)
    if text.startswith("Build.") and " named " in text:
        raise InscriptionError(f"unknown Build API phrase `{_build_phrase_signature(text)}`", line)
    if text.startswith("Build.") and text.endswith(" workflow"):
        raise InscriptionError(f"unknown Build API phrase `{text}`", line)
    if text.startswith("Build."):
        raise InscriptionError("malformed Build artifact request", line)
    return None


def _parse_group_step(text: str, line: int) -> BuildStep | None:
    prefix = "Build.group named "
    if not text.startswith(prefix):
        return None
    rest = text[len(prefix) :].strip()
    marker = " with steps"
    marker_index = rest.find(marker)
    if marker_index < 0:
        raise InscriptionError("malformed Build group request", line)
    name_token = rest[:marker_index].strip()
    if not (name_token.startswith('"') and name_token.endswith('"')):
        raise InscriptionError("build artifact names must be string literals in v0.50", line)
    name = _parse_build_string(name_token, line)
    _validate_step_name(name, line)
    dependencies_text = rest[marker_index + len(marker) :].strip()
    if not dependencies_text:
        raise InscriptionError(f"build group {name} must include at least one step", line)
    dependencies = _parse_group_dependencies(name, dependencies_text, line)
    return BuildStep(name, "group", line, dependencies)


def _parse_group_dependencies(group_name: str, text: str, line: int) -> tuple[str, ...]:
    dependencies: list[str] = []
    seen: set[str] = set()
    for token in text.split(" and "):
        token = token.strip()
        if not (token.startswith('"') and token.endswith('"')):
            raise InscriptionError("build group step names must be string literals in v0.52", line)
        name = _parse_build_string(token, line)
        _validate_step_name(name, line)
        if name in seen:
            raise InscriptionError(f"build group {group_name} includes step {name} more than once", line)
        seen.add(name)
        dependencies.append(name)
    return tuple(dependencies)


def _parse_default_step(text: str, line: int) -> str | None:
    prefix = "Build.default step is "
    if not text.startswith(prefix):
        return None
    token = text[len(prefix) :].strip()
    if not (token.startswith('"') and token.endswith('"')):
        raise InscriptionError("default build step name must be a string literal in v0.52", line)
    name = _parse_build_string(token, line)
    _validate_step_name(name, line)
    return name


def _validate_build_script_graph(script: BuildScript) -> None:
    by_name = {step.name: step for step in script.steps}
    for step in script.steps:
        if step.emit != "group":
            continue
        for dependency in step.dependencies:
            if dependency not in by_name:
                raise InscriptionError(f"build group {step.name} references unknown step {dependency}", step.line)
    if script.default_step is not None and script.default_step not in by_name:
        raise InscriptionError(f"default build step {script.default_step} is not defined")
    _check_dependency_cycles(by_name)


def _check_dependency_cycles(by_name: dict[str, BuildStep]) -> None:
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            start = visiting.index(name)
            cycle = [*visiting[start:], name]
            raise InscriptionError(f"build step dependency cycle detected: {' -> '.join(cycle)}")
        visiting.append(name)
        step = by_name[name]
        for dependency in step.dependencies:
            visit(dependency)
        visiting.pop()
        visited.add(name)

    for step_name in by_name:
        visit(step_name)


def _build_phrase_signature(text: str) -> str:
    before_literal = text.split('"', 1)[0].strip()
    if before_literal.endswith(" named"):
        return before_literal + " _"
    return before_literal


def _parse_build_string(token: str, line: int) -> str:
    if re.fullmatch(r'"(?:\\.|[^"\\])*"', token) is None:
        raise InscriptionError("expected build string literal", line)
    body = token[1:-1]
    out: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char != "\\":
            if char == "\x00":
                raise InscriptionError("build strings may not contain NUL", line)
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
            raise InscriptionError(f"invalid build string escape \\{escaped}", line)
        index += 2
    return "".join(out)


def _validate_step_name(name: str, line: int) -> None:
    if not name:
        raise InscriptionError("build step name must not be empty", line)
    if "/" in name or "\\" in name:
        raise InscriptionError("build step name must not contain path separators", line)
    if _BUILD_STEP_NAME_RE.fullmatch(name) is None:
        raise InscriptionError("build step name must use ASCII letters, digits, `_`, or `-`, and start with a letter or `_`", line)


def output_path_for_step(package_root: Path, step: BuildStep) -> Path:
    if step.emit not in _ARTIFACT_EMITS:
        raise InscriptionError(f"build step {step.name} does not produce an artifact")
    prefix, suffix = _OUTPUT_SUFFIXES[step.emit]
    basename = _package_final_name(package_root) if step.package_default else step.name
    return package_root / "build" / f"{prefix}{basename}{suffix}"


def _package_final_name(package_root: Path) -> str:
    context = load_package_context(package_root)
    return context.manifest.package_name.split(".")[-1]


def build_step_display(step: BuildStep) -> str:
    if step.emit == "group":
        return "group -> " + ", ".join(step.dependencies)
    return _STEP_DISPLAY.get(step.emit, step.emit)


def load_build_plan(package_root: Path) -> BuildScript:
    load_package_context(package_root)
    script = load_build_script(package_root)
    if not script.steps:
        raise InscriptionError("build script did not declare any build steps")
    return script


def list_build_steps(package_root: Path) -> tuple[BuildStep, ...]:
    return load_build_plan(package_root).steps


def run_build_script(
    package_root: Path,
    *,
    step_name: str | None = None,
    runtime_checks: bool = False,
    opt_level: str = "none",
    save_temps: Path | None = None,
    verify: bool = False,
) -> tuple[BuildExecutionResult, ...]:
    root = package_root.resolve()
    script = load_build_plan(root)
    if not script.steps:
        raise InscriptionError("build script did not declare any build steps")
    by_name = {step.name: step for step in script.steps}
    selected = _selected_build_roots(script, step_name=step_name)
    executed: set[str] = set()
    if step_name is not None:
        if step_name not in by_name:
            raise InscriptionError(f"build step {step_name} is not defined")
    results: list[BuildExecutionResult] = []
    for step in selected:
        failed = _run_step(
            step,
            by_name=by_name,
            root=root,
            runtime_checks=runtime_checks,
            opt_level=opt_level,
            save_temps=save_temps,
            verify=verify,
            executed=executed,
            results=results,
        )
        if failed:
            break
    return tuple(results)


def _selected_build_roots(script: BuildScript, *, step_name: str | None) -> tuple[BuildStep, ...]:
    by_name = {step.name: step for step in script.steps}
    if step_name is not None:
        if step_name not in by_name:
            raise InscriptionError(f"build step {step_name} is not defined")
        return (by_name[step_name],)
    if script.default_step is not None:
        return (by_name[script.default_step],)
    return tuple(step for step in script.steps if step.emit != "group")


def _run_step(
    step: BuildStep,
    *,
    by_name: dict[str, BuildStep],
    root: Path,
    runtime_checks: bool,
    opt_level: str,
    save_temps: Path | None,
    verify: bool,
    executed: set[str],
    results: list[BuildExecutionResult],
) -> bool:
    if step.name in executed:
        return False
    if step.emit == "group":
        for dependency_name in step.dependencies:
            failed = _run_step(
                by_name[dependency_name],
                by_name=by_name,
                root=root,
                runtime_checks=runtime_checks,
                opt_level=opt_level,
                save_temps=save_temps,
                verify=verify,
                executed=executed,
                results=results,
            )
            if failed:
                results.append(BuildExecutionResult(step, failed=True))
                return True
        executed.add(step.name)
        results.append(BuildExecutionResult(step))
        return False

    step_save_temps = save_temps / step.name if save_temps is not None else None
    if step.emit == "package-check":
        context = check_package(root, verify=verify)
        executed.add(step.name)
        results.append(BuildExecutionResult(step, package_context=context))
        return False
    if step.emit in {"package-format-check", "package-format-in-place"}:
        try:
            format_package(
                root,
                check=step.emit == "package-format-check",
                in_place=step.emit == "package-format-in-place",
            )
        except InscriptionError as exc:
            raise InscriptionError(f"build step {step.name} ... FAILED\n{exc}", step.line) from exc
        executed.add(step.name)
        results.append(BuildExecutionResult(step))
        return False
    if step.emit == "package-clean":
        clean_package(root)
        executed.add(step.name)
        results.append(BuildExecutionResult(step))
        return False
    if step.emit == "package-release":
        release = release_package(
            root,
            runtime_checks=runtime_checks,
            opt_level=opt_level,
            verify=verify,
            save_temps=step_save_temps,
            clean=True,
        )
        executed.add(step.name)
        results.append(BuildExecutionResult(step, release.output_dir))
        return False
    if step.emit == "package-release-archive":
        release = release_package(
            root,
            runtime_checks=runtime_checks,
            opt_level=opt_level,
            verify=verify,
            save_temps=step_save_temps,
            clean=True,
            archive=True,
            checksum=True,
        )
        executed.add(step.name)
        results.append(BuildExecutionResult(step, release.archive_path or release.output_dir))
        return False
    if step.emit in {"package-tests", "package-tests-with-dependencies"}:
        summary = run_package_tests(
            root,
            include_dependencies=step.emit == "package-tests-with-dependencies",
            runtime_checks=runtime_checks,
            opt_level=opt_level,
            save_temps=step_save_temps,
        )
        failed = isinstance(summary, PackageTestSummary) and summary.failed > 0
        if not failed:
            executed.add(step.name)
        results.append(BuildExecutionResult(step, test_summary=summary, failed=failed))
        return failed
    if step.emit in {"book", "book-check"}:
        output = build_book_step(root, step, checked=step.emit == "book-check")
        executed.add(step.name)
        results.append(BuildExecutionResult(step, output))
        return False

    output = output_path_for_step(root, step)
    output.parent.mkdir(parents=True, exist_ok=True)
    result = build_package_artifact(
        root,
        emit=step.emit,
        output=output,
        runtime_checks=runtime_checks,
        opt_level=opt_level,
        save_temps=step_save_temps,
        verify=verify,
    )
    if result.data is not None:
        output.write_bytes(result.data)
    elif result.text is not None:
        output.write_text(result.text)
    executed.add(step.name)
    results.append(BuildExecutionResult(step, output, result))
    return False


def build_book_step(package_root: Path, step: BuildStep, *, checked: bool) -> Path:
    book_root = package_root / "book"
    book_toml = book_root / "book.toml"
    if not book_toml.exists():
        raise InscriptionError(f"book step {step.name} requires book/book.toml", step.line)
    if checked:
        checker = book_root / "tools" / "check_book_examples.py"
        if not checker.exists():
            raise InscriptionError(
                f"book check step {step.name} requires book/tools/check_book_examples.py",
                step.line,
            )
        _run_book_checker(package_root, step, checker)
    mdbook = shutil.which("mdbook")
    if mdbook is None:
        raise InscriptionError("book step requires mdbook, but mdbook was not found", step.line)
    output = package_root / "build" / step.name
    if output.exists():
        if output.is_dir():
            shutil.rmtree(output)
        else:
            output.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)
    relative_output = Path("build") / step.name
    completed = subprocess.run(
        [mdbook, "build", "book", "--dest-dir", str(relative_output)],
        cwd=package_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise InscriptionError(f"book step {step.name} failed", step.line)
    return output


def _run_book_checker(package_root: Path, step: BuildStep, checker: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path("book") / "tools" / "check_book_examples.py")],
        cwd=package_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise InscriptionError(f"book check step {step.name} failed", step.line)
