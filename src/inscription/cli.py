from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compiler import compile_file
from .diagnostics import InscriptionError
from .runner import LOWERING_PASSES, ToolchainError, resolve_toolchain, run_file, verify_mlir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="inscription")
    sub = parser.add_subparsers(dest="command", required=True)

    compile_p = sub.add_parser("compile", help="emit MLIR for an Inscription source file")
    compile_p.add_argument("source", type=Path)
    compile_p.add_argument("-o", "--output", type=Path)
    compile_p.add_argument("--verify", action="store_true", help="verify emitted MLIR with LLVM 22 mlir-opt")
    compile_p.add_argument("--module-root", type=Path, help="root directory for resolving imported modules")

    run_p = sub.add_parser("run", help="compile and execute through LLVM 22 lli")
    run_p.add_argument("source", type=Path)
    run_p.add_argument("--module-root", type=Path, help="root directory for resolving imported modules")

    highlight_p = sub.add_parser("highlight", help="syntax-highlight an Inscription source file")
    highlight_p.add_argument("source", type=Path)
    highlight_p.add_argument("-o", "--output", type=Path)
    highlight_p.add_argument("--format", choices=("terminal", "html"), default="terminal")
    highlight_p.add_argument("--style", default="default", help="Pygments style name")
    highlight_p.add_argument("--full", action="store_true", help="emit a complete HTML document")

    tools_p = sub.add_parser("check-tools", help="verify LLVM 22 toolchain discovery")
    tools_p.add_argument("--show-pipeline", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            mlir = compile_file(args.source, module_root=args.module_root)
            if args.verify:
                verify_mlir(mlir)
            if args.output:
                args.output.write_text(mlir)
            else:
                sys.stdout.write(mlir)
            return 0
        if args.command == "run":
            result = run_file(args.source, module_root=args.module_root)
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
            toolchain = resolve_toolchain()
            print(f"mlir-opt={toolchain.mlir_opt}")
            print(f"mlir-translate={toolchain.mlir_translate}")
            print(f"lli={toolchain.lli}")
            if args.show_pipeline:
                print("mlir-opt input.mlir " + " ".join(LOWERING_PASSES) + " -o lowered.mlir")
                print("mlir-translate --mlir-to-llvmir lowered.mlir -o output.ll")
                print("lli output.ll")
            return 0
    except (InscriptionError, ToolchainError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(args.command)  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
