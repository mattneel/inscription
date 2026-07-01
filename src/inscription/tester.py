from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .ast import Program, TestDecl
from .compiler import load_program
from .mlir import emit_test_mlir
from .runner import ArtifactResult, Toolchain, build_artifacts, resolve_toolchain
from .semantic import analyze


@dataclass(frozen=True)
class TestRunItem:
    test: TestDecl
    display_name: str
    passed: bool
    artifacts: ArtifactResult | None = None


@dataclass(frozen=True)
class TestRunSummary:
    passed: int
    failed: int
    results: tuple[TestRunItem, ...]

    @property
    def exit_status(self) -> int:
        return 0 if self.failed == 0 else 1


def load_test_program(
    source_path: Path,
    *,
    module_root: Path | None = None,
    module_path_resolver: Callable[[str, tuple[str, ...]], Path] | None = None,
) -> Program:
    source_path = source_path.resolve()
    return load_program(
        source_path.read_text(),
        source_path=source_path,
        module_root=module_root,
        module_path_resolver=module_path_resolver,
    )


def test_display_name(test: TestDecl, program: Program) -> str:
    if "." in test.name:
        module_name, _local = test.name.rsplit(".", 1)
        return f"{module_name}::{test.display_name}"
    module_name = program.module_name or "root"
    return f"{module_name}::{test.display_name}"


def test_slug(display_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", display_name).strip("_").lower()
    return slug or "test"


def _prefix_display(display: str, display_prefix: str | None) -> str:
    if display_prefix is None:
        return display
    return f"{display_prefix}::{display}"


def filtered_tests(program: Program, filter_text: str | None, *, display_prefix: str | None = None) -> list[tuple[TestDecl, str]]:
    pairs = [(test, _prefix_display(test_display_name(test, program), display_prefix)) for test in program.tests]
    if filter_text is None:
        return pairs
    return [(test, display) for test, display in pairs if filter_text in display]


def list_tests(
    source_path: Path,
    *,
    module_root: Path | None = None,
    module_path_resolver: Callable[[str, tuple[str, ...]], Path] | None = None,
    filter_text: str | None = None,
    display_prefix: str | None = None,
) -> tuple[str, ...]:
    program = load_test_program(source_path, module_root=module_root, module_path_resolver=module_path_resolver)
    analyze(program)
    return tuple(display for _test, display in filtered_tests(program, filter_text, display_prefix=display_prefix))


def run_tests(
    source_path: Path,
    *,
    module_root: Path | None = None,
    module_path_resolver: Callable[[str, tuple[str, ...]], Path] | None = None,
    runtime_checks: bool = False,
    opt_level: str = "none",
    save_temps: Path | None = None,
    filter_text: str | None = None,
    toolchain: Toolchain | None = None,
    display_prefix: str | None = None,
) -> TestRunSummary | str:
    source_path = source_path.resolve()
    program = load_test_program(source_path, module_root=module_root, module_path_resolver=module_path_resolver)
    analyze(program)
    all_tests = [(test, _prefix_display(test_display_name(test, program), display_prefix)) for test in program.tests]
    if not all_tests:
        return "no tests found"
    selected = [(test, display) for test, display in all_tests if filter_text is None or filter_text in display]
    if not selected:
        assert filter_text is not None
        return f"no tests matched filter `{filter_text}`"
    toolchain = toolchain or resolve_toolchain()
    results: list[TestRunItem] = []
    passed = 0
    failed = 0
    for test, display in selected:
        mlir = emit_test_mlir(program, test, runtime_checks=runtime_checks)
        artifacts = build_artifacts(
            mlir,
            emit="llvm-ir",
            verify=True,
            save_temps=save_temps,
            stem=f"{source_path.stem}.{test_slug(display)}",
            toolchain=toolchain,
            opt_level=opt_level,
        )
        assert artifacts.llvm_ir is not None
        with tempfile.TemporaryDirectory(prefix="inscription-test-") as tmp:
            llvm_ir = Path(tmp) / "test.ll"
            llvm_ir.write_text(artifacts.llvm_ir)
            executed = subprocess.run(
                [str(toolchain.lli), str(llvm_ir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        ok = executed.returncode == 0
        if ok:
            passed += 1
        else:
            failed += 1
        results.append(TestRunItem(test, display, ok, artifacts))
    return TestRunSummary(passed, failed, tuple(results))
