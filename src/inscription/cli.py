from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compiler import compile_file
from .diagnostics import InscriptionError
from .runner import (
    EMIT_MODES,
    LOWERING_PASSES,
    ToolchainError,
    build_artifacts,
    resolve_toolchain,
    run_file,
    selected_artifact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="inscription")
    sub = parser.add_subparsers(dest="command", required=True)

    compile_p = sub.add_parser("compile", help="emit compiler artifacts for an Inscription source file")
    compile_p.add_argument("source", type=Path)
    compile_p.add_argument("-o", "--output", type=Path)
    compile_p.add_argument("--emit", default="mlir", help="artifact to emit: mlir, lowered-mlir, llvm-ir, or object")
    compile_p.add_argument("--save-temps", type=Path, help="directory for saved source MLIR, lowered MLIR, LLVM IR, and object intermediates")
    compile_p.add_argument("--verify", action="store_true", help="verify emitted artifacts with the LLVM/MLIR 22 toolchain")
    compile_p.add_argument("--module-root", type=Path, help="root directory for resolving imported modules")
    compile_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for dynamic storage bounds")

    run_p = sub.add_parser("run", help="compile and execute through LLVM 22 lli")
    run_p.add_argument("source", type=Path)
    run_p.add_argument("--module-root", type=Path, help="root directory for resolving imported modules")
    run_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for dynamic storage bounds")
    run_p.add_argument("--save-temps", type=Path, help="directory for saved source MLIR, lowered MLIR, and LLVM IR intermediates")

    highlight_p = sub.add_parser("highlight", help="syntax-highlight an Inscription source file")
    highlight_p.add_argument("source", type=Path)
    highlight_p.add_argument("-o", "--output", type=Path)
    highlight_p.add_argument("--format", choices=("terminal", "html"), default="terminal")
    highlight_p.add_argument("--style", default="default", help="Pygments style name")
    highlight_p.add_argument("--full", action="store_true", help="emit a complete HTML document")

    tools_p = sub.add_parser("check-tools", help="verify LLVM 22 toolchain discovery")
    tools_p.add_argument("--show-pipeline", action="store_true")
    tools_p.add_argument("--require-object", action="store_true", help="require LLVM 22 llc for object emission")

    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            if args.emit not in EMIT_MODES:
                raise InscriptionError(f"invalid emit mode {args.emit}")
            if args.emit == "object" and args.output is None:
                raise InscriptionError("object emission requires -o OUTPUT")
            mlir = compile_file(args.source, module_root=args.module_root, runtime_checks=args.runtime_checks)
            artifacts = build_artifacts(
                mlir,
                emit=args.emit,
                verify=args.verify,
                save_temps=args.save_temps,
                stem=args.source.stem,
            )
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
            toolchain = resolve_toolchain(require_object=args.require_object)
            print(f"mlir-opt={toolchain.mlir_opt}")
            print(f"mlir-translate={toolchain.mlir_translate}")
            print(f"lli={toolchain.lli}")
            if toolchain.llc is None:
                print("llc=unavailable (optional)")
            else:
                print(f"llc={toolchain.llc}")
            if args.show_pipeline:
                print("mlir-opt input.mlir " + " ".join(LOWERING_PASSES) + " -o lowered.mlir")
                print("mlir-translate --mlir-to-llvmir lowered.mlir -o output.ll")
                print("lli output.ll")
                print("llc -filetype=obj output.ll -o output.o")
            return 0
    except (InscriptionError, ToolchainError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(args.command)  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
