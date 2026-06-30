from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compiler import compile_file, load_program
from .diagnostics import InscriptionError
from .mlir import emit_mlir
from .runner import (
    EMIT_MODES,
    LOWERING_PASSES,
    OPTIMIZATION_PRESETS,
    ToolchainError,
    build_artifacts,
    resolve_toolchain,
    run_file,
    selected_artifact,
    validate_executable_main,
)


def _add_optimization_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("--opt-level", help="optimization preset: none, basic, or aggressive")
    command.add_argument("-O0", dest="opt_aliases", action="append_const", const="none", help="alias for --opt-level none")
    command.add_argument("-O1", dest="opt_aliases", action="append_const", const="basic", help="alias for --opt-level basic")
    command.add_argument("-O2", dest="opt_aliases", action="append_const", const="aggressive", help="alias for --opt-level aggressive")


def _resolve_opt_level(args: argparse.Namespace) -> str:
    levels: list[str] = []
    if getattr(args, "opt_level", None) is not None:
        if args.opt_level not in OPTIMIZATION_PRESETS:
            raise InscriptionError(f"invalid optimization level {args.opt_level}")
        levels.append(args.opt_level)
    levels.extend(getattr(args, "opt_aliases", None) or [])
    if not levels:
        return "none"
    first = levels[0]
    for level in levels[1:]:
        if level != first:
            raise InscriptionError(f"conflicting optimization levels: {first} and {level}")
    return first


def _format_preset(passes: tuple[str, ...]) -> str:
    if not passes:
        return "<none>"
    return ", ".join(pass_name.removeprefix("--") for pass_name in passes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="inscription")
    sub = parser.add_subparsers(dest="command", required=True)

    compile_p = sub.add_parser("compile", help="emit compiler artifacts for an Inscription source file")
    compile_p.add_argument("source", type=Path)
    compile_p.add_argument("-o", "--output", type=Path)
    compile_p.add_argument("--emit", default="mlir", help="artifact to emit: mlir, lowered-mlir, llvm-ir, object, or executable")
    compile_p.add_argument(
        "--save-temps",
        type=Path,
        help="directory for saved source MLIR, optimized MLIR when enabled, lowered MLIR, LLVM IR, and object intermediates",
    )
    compile_p.add_argument("--link-object", action="append", type=Path, default=[], help="additional object file to link for executable emission")
    compile_p.add_argument("--verify", action="store_true", help="verify emitted artifacts with the LLVM/MLIR 22 toolchain")
    compile_p.add_argument("--module-root", type=Path, help="root directory for resolving imported modules")
    compile_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for dynamic storage bounds")
    _add_optimization_args(compile_p)

    run_p = sub.add_parser("run", help="compile and execute through LLVM 22 lli")
    run_p.add_argument("source", type=Path)
    run_p.add_argument("--module-root", type=Path, help="root directory for resolving imported modules")
    run_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for dynamic storage bounds")
    run_p.add_argument(
        "--save-temps",
        type=Path,
        help="directory for saved source MLIR, optimized MLIR when enabled, lowered MLIR, and LLVM IR intermediates",
    )
    _add_optimization_args(run_p)

    highlight_p = sub.add_parser("highlight", help="syntax-highlight an Inscription source file")
    highlight_p.add_argument("source", type=Path)
    highlight_p.add_argument("-o", "--output", type=Path)
    highlight_p.add_argument("--format", choices=("terminal", "html"), default="terminal")
    highlight_p.add_argument("--style", default="default", help="Pygments style name")
    highlight_p.add_argument("--full", action="store_true", help="emit a complete HTML document")

    tools_p = sub.add_parser("check-tools", help="verify LLVM 22 toolchain discovery")
    tools_p.add_argument("--show-pipeline", action="store_true", help="show optimization presets and the MLIR lowering pipeline")
    tools_p.add_argument("--require-object", action="store_true", help="require LLVM 22 llc for object emission")
    tools_p.add_argument("--require-executable", action="store_true", help="require LLVM 22 llc and clang for executable emission")

    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            if args.emit not in EMIT_MODES:
                raise InscriptionError(f"invalid emit mode {args.emit}")
            if args.emit == "object" and args.output is None:
                raise InscriptionError("object emission requires -o OUTPUT")
            if args.emit == "executable" and args.output is None:
                raise InscriptionError("executable emission requires -o OUTPUT")
            if args.link_object and args.emit != "executable":
                raise InscriptionError("--link-object is supported only with --emit executable")
            link_objects = tuple(args.link_object)
            for path in link_objects:
                if not path.exists():
                    raise InscriptionError(f"link object {path} does not exist")
            opt_level = _resolve_opt_level(args)
            if args.emit == "executable":
                source_path = args.source.resolve()
                program = load_program(source_path.read_text(), source_path=source_path, module_root=args.module_root)
                validate_executable_main(program)
                mlir = emit_mlir(program, runtime_checks=args.runtime_checks)
            else:
                mlir = compile_file(args.source, module_root=args.module_root, runtime_checks=args.runtime_checks)
            artifacts = build_artifacts(
                mlir,
                emit=args.emit,
                verify=args.verify,
                save_temps=args.save_temps,
                stem=args.source.stem,
                opt_level=opt_level,
                executable_output=args.output if args.emit == "executable" else None,
                link_objects=link_objects,
            )
            if args.emit == "executable":
                return 0
            output = selected_artifact(artifacts, args.emit)
            if isinstance(output, bytes):
                assert args.output is not None
                args.output.write_bytes(output)
            elif args.output:
                args.output.write_text(output)
            else:
                sys.stdout.write(output)
            return 0
        if args.command == "run":
            result = run_file(
                args.source,
                module_root=args.module_root,
                runtime_checks=args.runtime_checks,
                save_temps=args.save_temps,
                opt_level=_resolve_opt_level(args),
            )
            return result.exit_status
        if args.command == "highlight":
            from .highlighting import HighlightError, highlight_source

            if args.full and args.format != "html":
                parser.error("--full is only supported with --format html")
            try:
                highlighted = highlight_source(
                    args.source.read_text(),
                    output_format=args.format,
                    style=args.style,
                    full=args.full,
                )
            except HighlightError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            if args.output:
                args.output.write_text(highlighted)
            else:
                sys.stdout.write(highlighted)
            return 0
        if args.command == "check-tools":
            toolchain = resolve_toolchain(require_object=args.require_object, require_executable=args.require_executable)
            print(f"mlir-opt={toolchain.mlir_opt}")
            print(f"mlir-translate={toolchain.mlir_translate}")
            print(f"lli={toolchain.lli}")
            if toolchain.llc is None:
                print("llc=unavailable (optional)")
            else:
                print(f"llc={toolchain.llc}")
            if toolchain.clang is None:
                print("clang=unavailable (optional)")
            else:
                print(f"clang={toolchain.clang}")
            if args.show_pipeline:
                print("optimization presets:")
                for name, passes in OPTIMIZATION_PRESETS.items():
                    print(f"  {name}: {_format_preset(passes)}")
                print("mlir-opt input.mlir " + " ".join(LOWERING_PASSES) + " -o lowered.mlir")
                print("mlir-translate --mlir-to-llvmir lowered.mlir -o output.ll")
                print("lli output.ll")
                print("object emission: llc -relocation-model=pic -filetype=obj output.ll -o output.o")
                print("executable emission: clang output.o -o executable")
            return 0
    except (InscriptionError, ToolchainError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(args.command)  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
