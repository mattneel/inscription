from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .diagnostics import InscriptionError
from .package import PackageBuildResult, build_package_artifact, load_package_context
from .parser import (
    SourceComment,
    _split_punctuation_sentences_no_comments,
    collect_source_comments,
)

BUILD_SCRIPT_NAME = "build.ins"
_BUILD_STEP_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_BUILD_CALLS: dict[str, str] = {
    "Build.static library named": "static-library",
    "Build.executable named": "executable",
    "Build.c header named": "c-header",
    "Build.interface json named": "interface-json",
    "Build.llvm ir named": "llvm-ir",
    "Build.object named": "object",
    "Build.mlir named": "mlir",
    "Build.lowered mlir named": "lowered-mlir",
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


@dataclass(frozen=True)
class BuildStep:
    name: str
    emit: str
    line: int


@dataclass(frozen=True)
class BuildScript:
    path: Path
    steps: tuple[BuildStep, ...]
    comments: tuple[SourceComment, ...] = ()


@dataclass(frozen=True)
class BuildExecutionResult:
    step: BuildStep
    output_path: Path
    package_result: PackageBuildResult


def load_build_script(package_root: Path) -> BuildScript:
    root = package_root.resolve()
    path = root / BUILD_SCRIPT_NAME
    if not path.exists():
        raise InscriptionError(f"build script not found at {BUILD_SCRIPT_NAME}")
    return parse_build_script(path.read_text(), path=path)


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
        step = _parse_build_call(text, sentence.line)
        if step is None:
            raise InscriptionError("build script body supports only Build artifact requests in v0.50", sentence.line)
        if step.name in seen:
            raise InscriptionError(f"build step {step.name} is already defined", sentence.line)
        seen.add(step.name)
        steps.append(step)
    return BuildScript(path or Path(BUILD_SCRIPT_NAME), tuple(steps), comments.comments)


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
        if text.startswith("To build package"):
            raise InscriptionError("build phrase parameter must have type Build.Package", line)
        raise InscriptionError("build script must define `To build package package: Build.Package.`", line)


def _parse_build_call(text: str, line: int) -> BuildStep | None:
    for prefix, emit in _BUILD_CALLS.items():
        if not text.startswith(prefix + " "):
            continue
        literal = text[len(prefix) :].strip()
        if not (literal.startswith('"') and literal.endswith('"')):
            raise InscriptionError("build artifact names must be string literals in v0.50", line)
        name = _parse_build_string(literal, line)
        _validate_step_name(name, line)
        return BuildStep(name, emit, line)
    if text.startswith("Build.") and " named " in text:
        raise InscriptionError("unknown Build artifact request in v0.50", line)
    if text.startswith("Build."):
        raise InscriptionError("malformed Build artifact request", line)
    return None


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
    prefix, suffix = _OUTPUT_SUFFIXES[step.emit]
    return package_root / "build" / f"{prefix}{step.name}{suffix}"


def list_build_steps(package_root: Path) -> tuple[BuildStep, ...]:
    load_package_context(package_root)
    script = load_build_script(package_root)
    if not script.steps:
        raise InscriptionError("build script did not declare any build steps")
    return script.steps


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
    script = load_build_script(root)
    if not script.steps:
        raise InscriptionError("build script did not declare any build steps")
    selected = script.steps
    if step_name is not None:
        selected = tuple(step for step in script.steps if step.name == step_name)
        if not selected:
            raise InscriptionError(f"build step {step_name} is not defined")
    results: list[BuildExecutionResult] = []
    for step in selected:
        output = output_path_for_step(root, step)
        output.parent.mkdir(parents=True, exist_ok=True)
        step_save_temps = save_temps / step.name if save_temps is not None else None
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
        results.append(BuildExecutionResult(step, output, result))
    return tuple(results)
