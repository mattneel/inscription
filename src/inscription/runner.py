from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .compiler import compile_file, compile_source

LOWERING_PASSES = [
    "--convert-scf-to-cf",
    "--convert-cf-to-llvm",
    "--convert-arith-to-llvm",
    "--expand-strided-metadata",
    "--finalize-memref-to-llvm",
    "--convert-func-to-llvm",
    "--reconcile-unrealized-casts",
]


class ToolchainError(RuntimeError):
    pass


@dataclass(frozen=True)
class Toolchain:
    root: Path
    mlir_opt: Path
    mlir_translate: Path
    lli: Path


@dataclass(frozen=True)
class RunResult:
    exit_status: int
    mlir: str
    lowered_mlir: str
    llvm_ir: str


def resolve_toolchain() -> Toolchain:
    root = Path(os.environ.get("MLIR_TOOLCHAIN", "/usr/lib/llvm-22/bin"))
    tools = {name: root / name for name in ("mlir-opt", "mlir-translate", "lli")}
    for name, path in tools.items():
        if not path.exists() or not os.access(path, os.X_OK):
            raise ToolchainError(f"required LLVM 22 tool '{name}' not found at {path}")
        version = subprocess.run([str(path), "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        if version.returncode != 0 or not re.search(r"\b22\.\d+", version.stdout):
            raise ToolchainError(f"tool '{path}' does not report LLVM/MLIR 22.x")
    return Toolchain(root, tools["mlir-opt"], tools["mlir-translate"], tools["lli"])


def verify_mlir(mlir: str, toolchain: Toolchain | None = None) -> None:
    toolchain = toolchain or resolve_toolchain()
    with tempfile.TemporaryDirectory(prefix="inscription-verify-") as tmp:
        path = Path(tmp) / "input.mlir"
        path.write_text(mlir)
        _run_checked([str(toolchain.mlir_opt), str(path), "-o", os.devnull], "MLIR verification failed")


def run_source(
    source: str,
    toolchain: Toolchain | None = None,
    *,
    source_path: Path | None = None,
    module_root: Path | None = None,
    runtime_checks: bool = False,
) -> RunResult:
    toolchain = toolchain or resolve_toolchain()
    mlir = compile_source(source, source_path=source_path, module_root=module_root, runtime_checks=runtime_checks)
    with tempfile.TemporaryDirectory(prefix="inscription-run-") as tmp:
        tmp_path = Path(tmp)
        input_mlir = tmp_path / "input.mlir"
        lowered_mlir = tmp_path / "lowered.mlir"
        llvm_ir = tmp_path / "output.ll"
        input_mlir.write_text(mlir)
        _run_checked([str(toolchain.mlir_opt), str(input_mlir), "-o", os.devnull], "MLIR verification failed")
        _run_checked(
            [str(toolchain.mlir_opt), str(input_mlir), *LOWERING_PASSES, "-o", str(lowered_mlir)],
            "MLIR lowering failed",
        )
        _run_checked(
            [str(toolchain.mlir_translate), "--mlir-to-llvmir", str(lowered_mlir), "-o", str(llvm_ir)],
            "MLIR translation failed",
        )
        executed = subprocess.run([str(toolchain.lli), str(llvm_ir)], check=False)
        return RunResult(executed.returncode, mlir, lowered_mlir.read_text(), llvm_ir.read_text())



def run_file(
    source_path: Path,
    toolchain: Toolchain | None = None,
    *,
    module_root: Path | None = None,
    runtime_checks: bool = False,
) -> RunResult:
    toolchain = toolchain or resolve_toolchain()
    mlir = compile_file(source_path, module_root=module_root, runtime_checks=runtime_checks)
    with tempfile.TemporaryDirectory(prefix="inscription-run-") as tmp:
        tmp_path = Path(tmp)
        input_mlir = tmp_path / "input.mlir"
        lowered_mlir = tmp_path / "lowered.mlir"
        llvm_ir = tmp_path / "output.ll"
        input_mlir.write_text(mlir)
        _run_checked([str(toolchain.mlir_opt), str(input_mlir), "-o", os.devnull], "MLIR verification failed")
        _run_checked(
            [str(toolchain.mlir_opt), str(input_mlir), *LOWERING_PASSES, "-o", str(lowered_mlir)],
            "MLIR lowering failed",
        )
        _run_checked(
            [str(toolchain.mlir_translate), "--mlir-to-llvmir", str(lowered_mlir), "-o", str(llvm_ir)],
            "MLIR translation failed",
        )
        executed = subprocess.run([str(toolchain.lli), str(llvm_ir)], check=False)
        return RunResult(executed.returncode, mlir, lowered_mlir.read_text(), llvm_ir.read_text())


def _run_checked(command: list[str], message: str) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ToolchainError(f"{message}: {detail}")
