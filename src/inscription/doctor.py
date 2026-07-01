from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .buildscript import BUILD_SCRIPT_NAME, load_build_plan
from .diagnostics import InscriptionError
from .package import MANIFEST_NAME, checked_package_graph
from .runner import _llvm_major, _reports_llvm22, _tool_version
from .version import INSCRIPTION_VERSION, REQUIRED_LLVM_MAJOR


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str | None = None
    path: Path | None = None
    version: str | None = None
    required: bool = False

    @property
    def failed(self) -> bool:
        if self.status == "ok":
            return False
        if not self.required and self.status in {"missing", "wrong-version", "skipped", "not-found"}:
            return False
        if self.status in {"skipped", "not-found"}:
            return False
        return True

    def text(self) -> str:
        suffix = ""
        if self.status == "ok":
            if self.path is not None:
                suffix = f" ({self.path})"
            elif self.detail is not None:
                suffix = f" ({self.detail})"
            if not self.required and self.name in _OPTIONAL_TOOL_NAMES:
                suffix += " optional"
            return f"{self.name}: ok{suffix}"
        if self.status == "missing" and not self.required:
            return f"{self.name}: missing optional"
        if self.status == "wrong-version" and not self.required:
            return f"{self.name}: wrong-version optional"
        display_status = "not found" if self.status == "not-found" else self.status
        if self.detail:
            return f"{self.name}: {display_status} ({self.detail})"
        return f"{self.name}: {display_status}"

    def to_json(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": self.name,
            "status": self.status,
        }
        if self.detail is not None:
            payload["detail"] = self.detail
        if self.path is not None:
            payload["path"] = str(self.path)
        if self.version is not None:
            payload["version"] = self.version
        if self.name in _TOOL_NAMES:
            payload["required"] = self.required
        return payload


@dataclass(frozen=True)
class DoctorResult:
    checks: tuple[DoctorCheck, ...]
    package: dict[str, object]

    @property
    def ok(self) -> bool:
        return not any(check.failed for check in self.checks)

    def to_json(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "checks": [check.to_json() for check in self.checks],
            "package": self.package,
        }

    def json_text(self) -> str:
        return json.dumps(self.to_json(), indent=2) + "\n"

    def text(self) -> str:
        return "\n".join(check.text() for check in self.checks) + "\n"


_TOOL_NAMES = frozenset({"mlir-opt", "mlir-translate", "lli", "llc", "clang", "llvm-ar", "mdbook"})
_OPTIONAL_TOOL_NAMES = frozenset({"llc", "clang", "llvm-ar", "mdbook"})


def run_doctor(
    package_root: Path,
    *,
    no_package: bool = False,
    require_object: bool = False,
    require_executable: bool = False,
    require_static_library: bool = False,
    require_book: bool = False,
    check_pages_workflow: bool = False,
) -> DoctorResult:
    root = package_root.resolve()
    checks: list[DoctorCheck] = []
    package_status: dict[str, object]

    checks.append(DoctorCheck("version", "ok", INSCRIPTION_VERSION, required=True))
    checks.append(_python_check())
    checks.append(_core_import_check())
    checks.extend(
        _tool_checks(
            require_object=require_object,
            require_executable=require_executable,
            require_static_library=require_static_library,
            require_book=require_book,
        )
    )

    if no_package:
        package_status = {"status": "skipped", "root": _relative_to_cwd(root)}
        checks.append(DoctorCheck("package", "skipped"))
    elif (root / MANIFEST_NAME).exists():
        package_checks, package_status = _package_checks(root)
        checks.extend(package_checks)
    else:
        package_status = {"status": "not-found", "root": _relative_to_cwd(root)}
        checks.append(DoctorCheck("package", "not-found"))

    if check_pages_workflow:
        checks.extend(_pages_workflow_checks(Path.cwd()))

    return DoctorResult(tuple(checks), package_status)


def _python_check() -> DoctorCheck:
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info < (3, 11):
        return DoctorCheck("python", "failed", f"{version}; requires 3.11 or newer", required=True)
    return DoctorCheck("python", "ok", version, required=True)


def _core_import_check() -> DoctorCheck:
    try:
        importlib.import_module("inscription")
    except Exception as exc:  # pragma: no cover - defensive health check
        return DoctorCheck("core import", "failed", str(exc), required=True)
    return DoctorCheck("core import", "ok", required=True)


def _tool_checks(
    *,
    require_object: bool,
    require_executable: bool,
    require_static_library: bool,
    require_book: bool,
) -> tuple[DoctorCheck, ...]:
    root = Path(os.environ.get("MLIR_TOOLCHAIN", f"/usr/lib/llvm-{REQUIRED_LLVM_MAJOR}/bin"))
    checks = [
        _llvm_tool_check("mlir-opt", (root / "mlir-opt",), required=True),
        _llvm_tool_check("mlir-translate", (root / "mlir-translate",), required=True),
        _llvm_tool_check("lli", (root / "lli",), required=True),
        _llvm_tool_check(
            "llc",
            (root / "llc",),
            required=require_object or require_executable or require_static_library,
        ),
        _llvm_tool_check("clang", (root / "clang", root / f"clang-{REQUIRED_LLVM_MAJOR}"), required=require_executable),
        _llvm_tool_check("llvm-ar", (root / "llvm-ar",), required=require_static_library),
        _path_tool_check("mdbook", required=require_book),
    ]
    return tuple(checks)


def _llvm_tool_check(name: str, candidates: tuple[Path, ...], *, required: bool) -> DoctorCheck:
    for path in candidates:
        if not path.exists() or not os.access(path, os.X_OK):
            continue
        version = _tool_version(path)
        if _reports_llvm22(version):
            return DoctorCheck(name, "ok", path=path, version=f"{REQUIRED_LLVM_MAJOR}.x", required=required)
        major = _llvm_major(version)
        detail = f"got LLVM {major}.x" if major is not None else f"does not report LLVM {REQUIRED_LLVM_MAJOR}.x"
        return DoctorCheck(name, "wrong-version", detail, path=path, required=required)
    detail = f"not found at {candidates[0]}" if len(candidates) == 1 else "not found"
    return DoctorCheck(name, "missing", detail, required=required)


def _path_tool_check(name: str, *, required: bool) -> DoctorCheck:
    found = shutil.which(name)
    if found is None:
        return DoctorCheck(name, "missing", required=required)
    return DoctorCheck(name, "ok", path=Path(found), required=required)


def _package_checks(root: Path) -> tuple[tuple[DoctorCheck, ...], dict[str, object]]:
    checks: list[DoctorCheck] = []
    try:
        graph = checked_package_graph(root, verify=False)
    except InscriptionError as exc:
        package_status = {"status": "failed", "root": _relative_to_cwd(root), "detail": str(exc)}
        return (DoctorCheck("package", "failed", str(exc), required=True),), package_status

    context = graph.root
    manifest = context.manifest
    checks.append(DoctorCheck("package", "ok", manifest.package_name, required=True))
    checks.append(DoctorCheck("package sources", "ok", manifest.sources, required=True))
    if manifest.tests is not None:
        checks.append(DoctorCheck("package tests", "ok", manifest.tests, required=True))
    else:
        checks.append(DoctorCheck("package tests", "not-found"))
    dependency_count = len(graph.dependencies_by_name.get(manifest.package_name, ()))
    checks.append(DoctorCheck("package dependencies", "ok", str(dependency_count), required=True))

    build_path = root / BUILD_SCRIPT_NAME
    if build_path.exists():
        try:
            plan = load_build_plan(root)
        except InscriptionError as exc:
            checks.append(DoctorCheck("build script", "failed", str(exc), required=True))
        else:
            checks.append(DoctorCheck("build script", "ok", f"{len(plan.steps)} steps", required=True))
    else:
        checks.append(DoctorCheck("build script", "not-found"))

    package_status = {
        "status": "ok",
        "name": manifest.package_name,
        "root": _relative_to_cwd(root),
    }
    return tuple(checks), package_status


def _pages_workflow_checks(root: Path) -> tuple[DoctorCheck, ...]:
    checks: list[DoctorCheck] = []
    workflow = root / ".github" / "workflows" / "book.yml"
    if not workflow.exists():
        checks.append(DoctorCheck("pages workflow", "failed", ".github/workflows/book.yml missing", required=True))
    else:
        text = workflow.read_text()
        missing = [needle for needle in ("configure-pages", "upload-pages-artifact", "deploy-pages") if needle not in text]
        if missing:
            checks.append(DoctorCheck("pages workflow", "failed", "missing " + ", ".join(missing), required=True))
        else:
            checks.append(DoctorCheck("pages workflow", "ok", ".github/workflows/book.yml", required=True))
    book = root / "book" / "book.toml"
    if book.exists():
        checks.append(DoctorCheck("book", "ok", "book/book.toml", required=True))
    else:
        checks.append(DoctorCheck("book", "failed", "book/book.toml missing", required=True))
    return tuple(checks)


def _relative_to_cwd(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix() or "."
    except ValueError:
        return str(path)
