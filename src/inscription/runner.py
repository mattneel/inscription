from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .ast import Program
from .compiler import load_program
from .diagnostics import InscriptionError
from .mlir import emit_mlir
from .semantic import (
    INTEGER_TYPES,
    constant_table,
    enum_table,
    format_type,
    function_table,
    record_table,
    resolve_function_table,
    type_alias_table,
    union_table,
    validate_external_symbols,
    validate_type_aliases,
    validate_union_payloads,
)

LOWERING_PASSES = [
    "--convert-scf-to-cf",
    "--convert-cf-to-llvm",
    "--convert-arith-to-llvm",
    "--expand-strided-metadata",
    "--finalize-memref-to-llvm",
    "--convert-func-to-llvm",
    "--reconcile-unrealized-casts",
]

PIPELINE_EMIT_MODES = {"mlir", "lowered-mlir", "llvm-ir", "object", "executable", "static-library"}
EMIT_MODES = {*PIPELINE_EMIT_MODES, "interface-json", "c-header"}
OPTIMIZATION_PRESETS = {
    "none": (),
    "basic": (
        "--canonicalize",
        "--cse",
    ),
    "aggressive": (
        "--canonicalize",
        "--cse",
        "--sccp",
        "--canonicalize",
        "--cse",
        "--control-flow-sink",
        "--loop-invariant-code-motion",
        "--canonicalize",
        "--cse",
    ),
}


class ToolchainError(RuntimeError):
    pass


@dataclass(frozen=True)
class Toolchain:
    root: Path
    mlir_opt: Path
    mlir_translate: Path
    lli: Path
    llc: Path | None = None
    clang: Path | None = None
    llvm_ar: Path | None = None


@dataclass(frozen=True)
class ArtifactResult:
    mlir: str
    optimized_mlir: str | None = None
    lowered_mlir: str | None = None
    llvm_ir: str | None = None
    object_bytes: bytes | None = None
    executable_path: Path | None = None
    static_library_path: Path | None = None


@dataclass(frozen=True)
class RunResult:
    exit_status: int
    mlir: str
    lowered_mlir: str
    llvm_ir: str


def resolve_toolchain(
    *,
    require_object: bool = False,
    require_executable: bool = False,
    require_static_library: bool = False,
) -> Toolchain:
    root = Path(os.environ.get("MLIR_TOOLCHAIN", "/usr/lib/llvm-22/bin"))
    tools = {name: root / name for name in ("mlir-opt", "mlir-translate", "lli")}
    for name, path in tools.items():
        _require_llvm22_tool(name, path)
    llc = _resolve_optional_llc(
        root,
        require_object=require_object,
        require_executable=require_executable,
        require_static_library=require_static_library,
    )
    clang = _resolve_optional_clang(root, require_executable=require_executable)
    llvm_ar = _resolve_optional_llvm_ar(root, require_static_library=require_static_library)
    return Toolchain(root, tools["mlir-opt"], tools["mlir-translate"], tools["lli"], llc, clang, llvm_ar)


def _require_llvm22_tool(name: str, path: Path) -> None:
    if not path.exists() or not os.access(path, os.X_OK):
        raise ToolchainError(f"required LLVM 22 tool '{name}' not found at {path}")
    version = _tool_version(path)
    if not _reports_llvm22(version):
        raise ToolchainError(f"tool '{path}' does not report LLVM/MLIR 22.x")


def _resolve_optional_llc(
    root: Path,
    *,
    require_object: bool,
    require_executable: bool,
    require_static_library: bool,
) -> Path | None:
    path = root / "llc"
    if require_static_library:
        context = "static library emission"
    elif require_executable:
        context = "executable emission"
    else:
        context = "object emission"
    required = require_object or require_executable or require_static_library
    if not path.exists() or not os.access(path, os.X_OK):
        if required:
            raise ToolchainError(f"{context} requires llc from LLVM 22, but llc was not found")
        return None
    version = _tool_version(path)
    if not _reports_llvm22(version):
        if required:
            major = _llvm_major(version)
            if major is not None:
                raise ToolchainError(f"{context} requires llc from LLVM 22, got LLVM {major}.x")
            raise ToolchainError(f"{context} requires llc from LLVM 22, but llc does not report LLVM 22.x")
        return None
    return path


def _resolve_optional_llvm_ar(root: Path, *, require_static_library: bool) -> Path | None:
    path = root / "llvm-ar"
    if not path.exists() or not os.access(path, os.X_OK):
        if require_static_library:
            raise ToolchainError("static library emission requires llvm-ar from LLVM 22, but llvm-ar was not found")
        return None
    version = _tool_version(path)
    if not _reports_llvm22(version):
        if require_static_library:
            major = _llvm_major(version)
            if major is not None:
                raise ToolchainError(f"static library emission requires llvm-ar from LLVM 22, got LLVM {major}.x")
            raise ToolchainError("static library emission requires llvm-ar from LLVM 22, but llvm-ar does not report LLVM 22.x")
        return None
    return path


def _resolve_optional_clang(root: Path, *, require_executable: bool) -> Path | None:
    candidates = (root / "clang", root / "clang-22")
    invalid_versions: list[str] = []
    for path in candidates:
        if not path.exists() or not os.access(path, os.X_OK):
            continue
        version = _tool_version(path)
        if _reports_llvm22(version):
            return path
        invalid_versions.append(version)
    if not require_executable:
        return None
    if invalid_versions:
        major = _llvm_major(invalid_versions[0])
        if major is not None:
            raise ToolchainError(f"executable emission requires clang from LLVM 22, got LLVM {major}.x")
        raise ToolchainError("executable emission requires clang from LLVM 22, but clang does not report LLVM 22.x")
    raise ToolchainError("executable emission requires clang from LLVM 22, but clang was not found")


def _tool_version(path: Path) -> str:
    version = subprocess.run([str(path), "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if version.returncode != 0:
        return version.stdout
    return version.stdout


def _reports_llvm22(version: str) -> bool:
    return re.search(r"\b22\.\d+", version) is not None


def _llvm_major(version: str) -> str | None:
    match = re.search(r"\b(\d+)\.\d+", version)
    return match.group(1) if match is not None else None


def verify_mlir(mlir: str, toolchain: Toolchain | None = None) -> None:
    toolchain = toolchain or resolve_toolchain()
    with tempfile.TemporaryDirectory(prefix="inscription-verify-") as tmp:
        path = Path(tmp) / "input.mlir"
        path.write_text(mlir)
        _run_checked([str(toolchain.mlir_opt), str(path), "-o", os.devnull], "MLIR verification failed")


def lower_mlir(mlir: str, toolchain: Toolchain | None = None) -> str:
    toolchain = toolchain or resolve_toolchain()
    with tempfile.TemporaryDirectory(prefix="inscription-lower-") as tmp:
        tmp_path = Path(tmp)
        input_mlir = tmp_path / "input.mlir"
        lowered_mlir = tmp_path / "lowered.mlir"
        input_mlir.write_text(mlir)
        _run_checked(
            [str(toolchain.mlir_opt), str(input_mlir), *LOWERING_PASSES, "-o", str(lowered_mlir)],
            "MLIR lowering failed",
        )
        return lowered_mlir.read_text()


def optimize_source_mlir(mlir: str, opt_level: str, toolchain: Toolchain | None = None) -> str:
    if opt_level not in OPTIMIZATION_PRESETS:
        raise InscriptionError(f"invalid optimization level {opt_level}")
    passes = OPTIMIZATION_PRESETS[opt_level]
    if not passes:
        return mlir
    toolchain = toolchain or resolve_toolchain()
    with tempfile.TemporaryDirectory(prefix="inscription-optimize-") as tmp:
        tmp_path = Path(tmp)
        input_mlir = tmp_path / "input.mlir"
        optimized_mlir = tmp_path / "optimized.mlir"
        input_mlir.write_text(mlir)
        _run_checked(
            [str(toolchain.mlir_opt), str(input_mlir), *passes, "-o", str(optimized_mlir)],
            f"source MLIR optimization failed during {opt_level} preset",
        )
        return optimized_mlir.read_text()


def translate_to_llvm_ir(lowered_mlir: str, toolchain: Toolchain | None = None) -> str:
    toolchain = toolchain or resolve_toolchain()
    with tempfile.TemporaryDirectory(prefix="inscription-translate-") as tmp:
        tmp_path = Path(tmp)
        lowered_path = tmp_path / "lowered.mlir"
        llvm_ir = tmp_path / "output.ll"
        lowered_path.write_text(lowered_mlir)
        _run_checked(
            [str(toolchain.mlir_translate), "--mlir-to-llvmir", str(lowered_path), "-o", str(llvm_ir)],
            "MLIR translation failed",
        )
        return llvm_ir.read_text()


def compile_object(llvm_ir: str, toolchain: Toolchain | None = None) -> bytes:
    toolchain = toolchain or resolve_toolchain(require_object=True)
    if toolchain.llc is None:
        raise ToolchainError("object emission requires llc from LLVM 22, but llc was not found")
    with tempfile.TemporaryDirectory(prefix="inscription-object-") as tmp:
        tmp_path = Path(tmp)
        llvm_path = tmp_path / "input.ll"
        object_path = tmp_path / "output.o"
        llvm_path.write_text(llvm_ir)
        _run_checked(
            [str(toolchain.llc), "-relocation-model=pic", "-filetype=obj", str(llvm_path), "-o", str(object_path)],
            "object emission failed",
        )
        return object_path.read_bytes()


def strip_llvm_function(llvm_ir: str, symbol: str) -> str:
    pattern = re.compile(rf"^define\b.*@{re.escape(symbol)}\(")
    output: list[str] = []
    skipping = False
    brace_depth = 0
    for line in llvm_ir.splitlines(keepends=True):
        if not skipping and pattern.search(line):
            skipping = True
            brace_depth = line.count("{") - line.count("}")
            if brace_depth <= 0:
                skipping = False
            continue
        if skipping:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                skipping = False
            continue
        output.append(line)
    return "".join(output)


def link_executable(object_bytes: bytes, output_path: Path, link_objects: tuple[Path, ...], toolchain: Toolchain | None = None) -> None:
    toolchain = toolchain or resolve_toolchain(require_executable=True)
    if toolchain.clang is None:
        raise ToolchainError("executable emission requires clang from LLVM 22, but clang was not found")
    for path in link_objects:
        if not path.exists():
            raise InscriptionError(f"link object {path} does not exist")
    with tempfile.TemporaryDirectory(prefix="inscription-link-") as tmp:
        object_path = Path(tmp) / "input.o"
        object_path.write_bytes(object_bytes)
        _run_checked(
            [str(toolchain.clang), str(object_path), *(str(path) for path in link_objects), "-o", str(output_path)],
            "executable link failed",
        )


def create_static_library(
    object_bytes: bytes,
    output_path: Path,
    archive_objects: tuple[Path, ...],
    toolchain: Toolchain | None = None,
) -> None:
    toolchain = toolchain or resolve_toolchain(require_static_library=True)
    if toolchain.llc is None:
        raise ToolchainError("static library emission requires llc from LLVM 22, but llc was not found")
    if toolchain.llvm_ar is None:
        raise ToolchainError("static library emission requires llvm-ar from LLVM 22, but llvm-ar was not found")
    for path in archive_objects:
        if not path.exists():
            raise InscriptionError(f"archive object {path} does not exist")
    if output_path.exists():
        output_path.unlink()
    with tempfile.TemporaryDirectory(prefix="inscription-archive-") as tmp:
        object_path = Path(tmp) / "inscription.o"
        object_path.write_bytes(object_bytes)
        _run_checked(
            [
                str(toolchain.llvm_ar),
                "rcsD",
                str(output_path),
                str(object_path),
                *(str(path) for path in archive_objects),
            ],
            "static library emission failed",
        )


def build_artifacts(
    mlir: str,
    *,
    emit: str = "mlir",
    verify: bool = False,
    save_temps: Path | None = None,
    stem: str = "input",
    toolchain: Toolchain | None = None,
    opt_level: str = "none",
    executable_output: Path | None = None,
    link_objects: tuple[Path, ...] = (),
    static_library_output: Path | None = None,
    archive_objects: tuple[Path, ...] = (),
    strip_main_for_static_library: bool = False,
) -> ArtifactResult:
    if emit not in EMIT_MODES:
        raise InscriptionError(f"invalid emit mode {emit}")
    if emit not in PIPELINE_EMIT_MODES:
        raise InscriptionError(f"emit mode {emit} is handled outside the MLIR artifact pipeline")
    if emit == "executable" and executable_output is None:
        raise InscriptionError("executable emission requires -o OUTPUT")
    if emit == "static-library" and static_library_output is None:
        raise InscriptionError("static library emission requires -o OUTPUT")
    if opt_level not in OPTIMIZATION_PRESETS:
        raise InscriptionError(f"invalid optimization level {opt_level}")
    needs_optimized = opt_level != "none" and (emit != "mlir" or verify or save_temps is not None)
    needs_toolchain = emit != "mlir" or verify or needs_optimized
    if emit == "executable":
        toolchain = toolchain or resolve_toolchain(require_executable=True)
    elif emit == "static-library":
        toolchain = toolchain or resolve_toolchain(require_static_library=True)
    elif emit == "object":
        toolchain = toolchain or resolve_toolchain(require_object=True)
    elif needs_toolchain:
        toolchain = toolchain or resolve_toolchain()

    optimized: str | None = None
    lowered: str | None = None
    llvm_ir: str | None = None
    object_bytes: bytes | None = None
    lowering_input = mlir

    if verify:
        assert toolchain is not None
        verify_mlir(mlir, toolchain)

    if needs_optimized:
        assert toolchain is not None
        optimized = optimize_source_mlir(mlir, opt_level, toolchain)
        lowering_input = optimized
        if verify:
            verify_mlir(optimized, toolchain)

    if emit != "mlir" or verify:
        assert toolchain is not None
        lowered = lower_mlir(lowering_input, toolchain)
        if verify and emit in {"lowered-mlir", "llvm-ir", "object", "executable", "static-library"}:
            verify_mlir(lowered, toolchain)

    if emit in {"llvm-ir", "object", "executable", "static-library"}:
        assert lowered is not None
        assert toolchain is not None
        llvm_ir = translate_to_llvm_ir(lowered, toolchain)
        if emit == "static-library" and strip_main_for_static_library:
            llvm_ir = strip_llvm_function(llvm_ir, "main")

    if emit in {"object", "executable", "static-library"}:
        assert llvm_ir is not None
        assert toolchain is not None
        object_bytes = compile_object(llvm_ir, toolchain)

    result = ArtifactResult(
        mlir,
        optimized,
        lowered,
        llvm_ir,
        object_bytes,
        executable_output if emit == "executable" else None,
        static_library_output if emit == "static-library" else None,
    )
    if save_temps is not None:
        _save_artifacts(result, save_temps, stem)
    if emit == "executable":
        assert object_bytes is not None
        assert executable_output is not None
        link_executable(object_bytes, executable_output, link_objects, toolchain)
    if emit == "static-library":
        assert object_bytes is not None
        assert static_library_output is not None
        create_static_library(object_bytes, static_library_output, archive_objects, toolchain)
    return result


def selected_artifact(result: ArtifactResult, emit: str) -> str | bytes:
    if emit == "mlir":
        return result.mlir
    if emit == "lowered-mlir":
        assert result.lowered_mlir is not None
        return result.lowered_mlir
    if emit == "llvm-ir":
        assert result.llvm_ir is not None
        return result.llvm_ir
    if emit == "object":
        assert result.object_bytes is not None
        return result.object_bytes
    if emit == "executable":
        raise InscriptionError("executable emission writes directly to -o OUTPUT")
    if emit == "static-library":
        raise InscriptionError("static library emission writes directly to -o OUTPUT")
    if emit in {"interface-json", "c-header"}:
        raise InscriptionError(f"emit mode {emit} is handled outside the MLIR artifact pipeline")
    raise InscriptionError(f"invalid emit mode {emit}")


def _save_artifacts(result: ArtifactResult, directory: Path, stem: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.mlir").write_text(result.mlir)
    if result.optimized_mlir is not None:
        (directory / f"{stem}.optimized.mlir").write_text(result.optimized_mlir)
    if result.lowered_mlir is not None:
        (directory / f"{stem}.lowered.mlir").write_text(result.lowered_mlir)
    if result.llvm_ir is not None:
        (directory / f"{stem}.ll").write_text(result.llvm_ir)
    if result.object_bytes is not None:
        (directory / f"{stem}.o").write_bytes(result.object_bytes)


def run_source(
    source: str,
    toolchain: Toolchain | None = None,
    *,
    source_path: Path | None = None,
    module_root: Path | None = None,
    runtime_checks: bool = False,
    save_temps: Path | None = None,
    opt_level: str = "none",
) -> RunResult:
    program = load_program(source, source_path=source_path, module_root=module_root)
    validate_runnable_main(program)
    toolchain = toolchain or resolve_toolchain()
    mlir = emit_mlir(program, runtime_checks=runtime_checks)
    stem = source_path.stem if source_path is not None else "input"
    artifacts = build_artifacts(
        mlir,
        emit="llvm-ir",
        verify=True,
        save_temps=save_temps,
        stem=stem,
        toolchain=toolchain,
        opt_level=opt_level,
    )
    assert artifacts.lowered_mlir is not None
    assert artifacts.llvm_ir is not None
    with tempfile.TemporaryDirectory(prefix="inscription-run-") as tmp:
        llvm_ir = Path(tmp) / "output.ll"
        llvm_ir.write_text(artifacts.llvm_ir)
        executed = subprocess.run([str(toolchain.lli), str(llvm_ir)], check=False)
        return RunResult(executed.returncode, artifacts.mlir, artifacts.lowered_mlir, artifacts.llvm_ir)



def run_file(
    source_path: Path,
    toolchain: Toolchain | None = None,
    *,
    module_root: Path | None = None,
    runtime_checks: bool = False,
    save_temps: Path | None = None,
    opt_level: str = "none",
) -> RunResult:
    source_path = source_path.resolve()
    return run_source(
        source_path.read_text(),
        toolchain,
        source_path=source_path,
        module_root=module_root,
        runtime_checks=runtime_checks,
        save_temps=save_temps,
        opt_level=opt_level,
    )


def validate_runnable_main(program: Program) -> None:
    _validate_main(program, require_no_hole_main=False)


def validate_executable_main(program: Program) -> None:
    _validate_main(program, require_no_hole_main=True)


def _validate_main(program: Program, *, require_no_hole_main: bool) -> None:
    type_alias_table(program)
    enum_table(program)
    unions = union_table(program)
    records = record_table(program)
    validate_union_payloads(unions, records)
    validate_type_aliases(records)
    functions = function_table(program)
    constants = constant_table(program, records, functions)
    functions = resolve_function_table(functions, records, constants)
    validate_external_symbols(functions)
    main = functions.get("main")
    if main is None:
        if require_no_hole_main:
            raise InscriptionError("program must define a no-hole main to emit an executable")
        return
    if main.params:
        if require_no_hole_main:
            raise InscriptionError("program must define a no-hole main to emit an executable", main.line)
        return
    if main.return_type not in INTEGER_TYPES:
        raise InscriptionError(f"program main must return an integer scalar, got {format_type(main.return_type)}", main.line)


def _run_checked(command: list[str], message: str) -> None:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ToolchainError(f"{message}: {detail}")
