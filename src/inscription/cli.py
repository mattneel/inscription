from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compiler import compile_source
from .diagnostics import InscriptionError
from .runner import LOWERING_PASSES, ToolchainError, resolve_toolchain, run_source, verify_mlir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="inscription")
    sub = parser.add_subparsers(dest="command", required=True)

    compile_p = sub.add_parser("compile", help="emit MLIR for an Inscription source file")
    compile_p.add_argument("source", type=Path)
    compile_p.add_argument("-o", "--output", type=Path)
    compile_p.add_argument("--verify", action="store_true", help="verify emitted MLIR with LLVM 22 mlir-opt")

    run_p = sub.add_parser("run", help="compile and execute through LLVM 22 lli")
    run_p.add_argument("source", type=Path)

    tools_p = sub.add_parser("check-tools", help="verify LLVM 22 toolchain discovery")
    tools_p.add_argument("--show-pipeline", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            mlir = compile_source(args.source.read_text())
            if args.verify:
                verify_mlir(mlir)
            if args.output:
                args.output.write_text(mlir)
            else:
                sys.stdout.write(mlir)
            return 0
        if args.command == "run":
            result = run_source(args.source.read_text())
            return result.exit_status
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
