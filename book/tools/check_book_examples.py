#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from inscription.compiler import compile_file
from inscription.diagnostics import InscriptionError
from inscription.formatter import format_source
from inscription.runner import ToolchainError, resolve_toolchain

FENCE_RE = re.compile(
    r"(?P<comment><!--\s*inscription:\s*(?P<comment_mode>[a-z-]+)\s*-->\s*)?"
    r"```(?P<info>inscription|ins)(?P<attrs>[^\n`]*)\n(?P<code>.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)


@dataclass(frozen=True)
class Example:
    path: Path
    line: int
    mode: str
    code: str


class BookExampleError(RuntimeError):
    pass


def _mode_from_attrs(attrs: str, comment_mode: str | None) -> str:
    if comment_mode:
        return comment_mode
    tokens = {token.strip().lower() for token in re.split(r"[\s,]+", attrs.strip()) if token.strip()}
    for candidate in ("no-check", "check", "format"):
        if candidate in tokens:
            return candidate
    return "format"


def _source_text(code: str) -> str:
    return code if code.endswith("\n") else code + "\n"


def iter_examples(root: Path) -> list[Example]:
    examples: list[Example] = []
    for path in sorted((root / "book" / "src").rglob("*.md")):
        text = path.read_text()
        for match in FENCE_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            mode = _mode_from_attrs(match.group("attrs"), match.group("comment_mode"))
            examples.append(Example(path=path, line=line, mode=mode, code=_source_text(match.group("code"))))
    return examples


def _toolchain_available() -> bool:
    try:
        resolve_toolchain()
    except ToolchainError:
        return False
    return True


def _check_format(example: Example) -> None:
    formatted = format_source(example.code)
    if formatted != example.code:
        raise BookExampleError(f"{example.path}:{example.line}: Inscription example is not formatter-clean")


def _check_compile(example: Example, *, verify_mlir: bool) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "example.ins"
        source.write_text(example.code)
        if verify_mlir:
            proc = subprocess.run(
                [sys.executable, "-m", "inscription", "compile", str(source), "--verify"],
                cwd=REPO_ROOT,
                env={**os.environ, "PYTHONPATH": str(SRC)},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                raise BookExampleError(
                    f"{example.path}:{example.line}: compile --verify failed:\n{proc.stderr or proc.stdout}"
                )
        else:
            try:
                compile_file(source)
            except InscriptionError as exc:
                raise BookExampleError(f"{example.path}:{example.line}: compile failed: {exc}") from exc


def check_examples(root: Path = REPO_ROOT) -> tuple[int, int, bool]:
    examples = iter_examples(root)
    verify_mlir = _toolchain_available()
    checked = 0
    formatted = 0
    for example in examples:
        if example.mode == "no-check":
            continue
        if example.mode not in {"format", "check"}:
            raise BookExampleError(f"{example.path}:{example.line}: unknown Inscription example mode {example.mode!r}")
        _check_format(example)
        formatted += 1
        if example.mode == "check":
            _check_compile(example, verify_mlir=verify_mlir)
            checked += 1
    return formatted, checked, verify_mlir


def main() -> int:
    try:
        formatted, checked, verify_mlir = check_examples(REPO_ROOT)
    except BookExampleError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    mode = "compile --verify" if verify_mlir else "semantic compile only; LLVM/MLIR 22 tools not found"
    print(f"checked {formatted} formatted Inscription examples; compiled {checked} full programs ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
