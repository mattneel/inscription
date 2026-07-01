from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .buildscript import build_step_display, load_build_plan, run_build_script
from .package import PackageTestSummary
from .compiler import compile_file, load_program
from .diagnostics import (
    Diagnostic,
    InscriptionError,
    SourceSpan,
    diagnostic_to_payload,
    render_diagnostic,
    render_diagnostics_json,
    render_exception,
)
from .diagnostic_codes import (
    diagnostic_catalog_json,
    diagnostic_code_for_message,
    explain_diagnostic_code,
    lookup_diagnostic_code,
    sorted_diagnostic_codes,
)
from .doctor import run_doctor
from .formatter import format_file
from .interface import emit_c_header, emit_interface_json, load_interface_context
from .package import (
    build_package_artifact,
    check_package,
    clean_package,
    format_package,
    init_package,
    list_package_tests,
    new_package,
    release_package,
    run_package_tests,
)
from .mlir import emit_mlir
from .source_index import build_package_source_index, build_source_index
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
from .tester import TestRunSummary, list_tests, run_tests
from .version import INSCRIPTION_VERSION, REQUIRED_LLVM_MAJOR, version_lines, version_payload


def _add_optimization_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("--opt-level", help="optimization preset: none, basic, or aggressive")
    command.add_argument("-O0", dest="opt_aliases", action="append_const", const="none", help="alias for --opt-level none")
    command.add_argument("-O1", dest="opt_aliases", action="append_const", const="basic", help="alias for --opt-level basic")
    command.add_argument("-O2", dest="opt_aliases", action="append_const", const="aggressive", help="alias for --opt-level aggressive")


def _add_diagnostic_format_arg(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--diagnostic-format",
        choices=("text", "json"),
        default="text",
        help="diagnostic output format for failures: text or json",
    )


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


def _resolve_build_positionals(values: list[str]) -> tuple[Path, str | None]:
    if len(values) > 2:
        raise InscriptionError("build accepts at most PACKAGE_ROOT and STEP")
    if not values:
        return Path("."), None
    if len(values) == 2:
        return Path(values[0]), values[1]
    only = values[0]
    candidate = Path(only)
    if (candidate / "package.ins").exists() or candidate.is_dir():
        return candidate, None
    return Path("."), only


def _display_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _attach_cli_source_context(args: argparse.Namespace, exc: InscriptionError) -> InscriptionError:
    if exc.source is not None or exc.line is None:
        return exc
    source_path = getattr(args, "source", None)
    if not isinstance(source_path, Path) or not source_path.exists() or not source_path.is_file():
        return exc
    try:
        return exc.attach_source(source_path.read_text(), source_path)
    except OSError:
        return exc


def _render_toolchain_error(exc: ToolchainError) -> str:
    return render_diagnostic(_toolchain_diagnostic(exc))


def _toolchain_diagnostic(exc: ToolchainError) -> Diagnostic:
    message = str(exc)
    if "not found" in message:
        code = "INS-TOOL-0001"
    elif "does not report" in message:
        code = "INS-TOOL-0002"
    else:
        code = None
    return Diagnostic(message, code=code)


def _diagnostic_format(args: argparse.Namespace) -> str:
    return getattr(args, "diagnostic_format", "text")


def _explain_list_text() -> str:
    entries = sorted_diagnostic_codes()
    width = max(len(entry.code) for entry in entries)
    return "".join(f"{entry.code:<{width}}  {entry.title}\n" for entry in entries)


def _test_failure_diagnostic(result) -> Diagnostic:
    source_path = getattr(result, "source_path", None)
    line = _first_expect_line(result.test) or result.test.line
    path = source_path.as_posix() if isinstance(source_path, Path) else None
    return Diagnostic("expect failed", code="INS-TEST-0001", span=SourceSpan(path, line))


def _print_test_failure_diagnostic(result) -> None:
    source_path = getattr(result, "source_path", None)
    source = None
    if isinstance(source_path, Path) and source_path.exists():
        try:
            source = source_path.read_text()
        except OSError:
            source = None
    print(render_diagnostic(_test_failure_diagnostic(result), source=source))


def _test_summary_json(summary: PackageTestSummary | TestRunSummary) -> str:
    diagnostics = [_test_failure_diagnostic(result) for result in summary.results if not result.passed]
    tests: list[dict[str, object]] = []
    for result in summary.results:
        entry: dict[str, object] = {
            "name": result.display_name,
            "status": "ok" if result.passed else "failed",
        }
        if not result.passed:
            entry["diagnostics"] = [diagnostic_to_payload(_test_failure_diagnostic(result))]
        tests.append(entry)
    payload = {
        "ok": False,
        "summary": {
            "passed": summary.passed,
            "failed": summary.failed,
        },
        "tests": tests,
        "diagnostics": [diagnostic_to_payload(diagnostic) for diagnostic in diagnostics],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _first_expect_line(test) -> int | None:
    for stmt in getattr(test, "body", ()):  # direct Expect statements cover current source tests.
        if stmt.__class__.__name__ == "ExpectStmt":
            return getattr(stmt, "line", None)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="inscription")
    parser.add_argument("--version", action="store_true", help="print the Inscription tool version and exit")
    sub = parser.add_subparsers(dest="command", required=False)

    compile_p = sub.add_parser("compile", help="emit compiler artifacts for an Inscription source file")
    compile_p.add_argument("source", type=Path)
    compile_p.add_argument("-o", "--output", type=Path)
    compile_p.add_argument(
        "--emit",
        default="mlir",
        help=(
            "artifact to emit: mlir, lowered-mlir, llvm-ir, object, executable, "
            "static-library, interface-json, or c-header"
        ),
    )
    compile_p.add_argument(
        "--save-temps",
        type=Path,
        help="directory for saved source MLIR, optimized MLIR when enabled, lowered MLIR, LLVM IR, and object intermediates",
    )
    compile_p.add_argument("--link-object", action="append", type=Path, default=[], help="additional object file to link for executable emission")
    compile_p.add_argument(
        "--archive-object",
        action="append",
        type=Path,
        default=[],
        help="additional object file to include in static-library emission",
    )
    compile_p.add_argument("--verify", action="store_true", help="verify emitted artifacts with the LLVM/MLIR 22 toolchain")
    compile_p.add_argument("--module-root", type=Path, help="root directory for resolving imported modules")
    compile_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for dynamic storage bounds")
    _add_optimization_args(compile_p)
    _add_diagnostic_format_arg(compile_p)

    run_p = sub.add_parser("run", help=f"compile and execute through LLVM {REQUIRED_LLVM_MAJOR} lli")
    run_p.add_argument("source", type=Path)
    run_p.add_argument("--module-root", type=Path, help="root directory for resolving imported modules")
    run_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for dynamic storage bounds")
    run_p.add_argument(
        "--save-temps",
        type=Path,
        help="directory for saved source MLIR, optimized MLIR when enabled, lowered MLIR, and LLVM IR intermediates",
    )
    _add_optimization_args(run_p)
    _add_diagnostic_format_arg(run_p)

    test_p = sub.add_parser("test", help="compile and run source-level Inscription tests")
    test_p.add_argument("source", type=Path)
    test_p.add_argument("--module-root", type=Path, help="root directory for resolving imported modules")
    test_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for dynamic storage bounds")
    test_p.add_argument("--save-temps", type=Path, help="directory for per-test source MLIR, lowered MLIR, and LLVM IR intermediates")
    test_p.add_argument("--filter", help="run only tests whose display name contains TEXT")
    test_p.add_argument("--list", action="store_true", help="list discovered tests without running them")
    _add_optimization_args(test_p)
    _add_diagnostic_format_arg(test_p)

    symbols_p = sub.add_parser("symbols", help="emit a deterministic source symbol/reference index")
    symbols_p.add_argument("source", type=Path, help="Inscription source file to index, or a package root with --package")
    symbols_p.add_argument("--format", choices=("json",), default="json", help="symbol index output format")
    symbols_p.add_argument("--include-references", action="store_true", help="include references in the JSON index (default in v0.65)")
    symbols_p.add_argument("--module-root", type=Path, help="root directory for resolving imported modules")
    symbols_p.add_argument("--package", action="store_true", help="treat SOURCE as a package root and index package symbols")
    symbols_p.add_argument("--pretty", action="store_true", help="pretty-print JSON with two-space indentation")
    _add_diagnostic_format_arg(symbols_p)

    version_p = sub.add_parser("version", help="print deterministic version metadata")
    version_p.add_argument("--json", action="store_true", help="emit version metadata as JSON")

    explain_p = sub.add_parser("explain", help="explain a stable diagnostic code")
    explain_p.add_argument("code", nargs="?", help="diagnostic code to explain, for example INS-SEM-0001")
    explain_p.add_argument("--list", action="store_true", help="list known diagnostic codes")
    explain_p.add_argument("--json", action="store_true", help="emit diagnostic catalog or entry as JSON")

    doctor_p = sub.add_parser("doctor", help="run deterministic environment and package health checks")
    doctor_p.add_argument("root", nargs="?", type=Path, default=Path("."), help="package root to inspect when package.ins is present")
    doctor_p.add_argument("--json", action="store_true", help="emit doctor results as JSON")
    doctor_p.add_argument("--no-package", action="store_true", help="skip package health checks")
    doctor_p.add_argument("--require-object", action="store_true", help=f"require LLVM {REQUIRED_LLVM_MAJOR} llc for object emission")
    doctor_p.add_argument("--require-executable", action="store_true", help=f"require LLVM {REQUIRED_LLVM_MAJOR} llc and clang for executable emission")
    doctor_p.add_argument("--require-static-library", action="store_true", help=f"require LLVM {REQUIRED_LLVM_MAJOR} llc and llvm-ar for static-library emission")
    doctor_p.add_argument("--require-book", action="store_true", help="require mdBook for documentation build steps")
    doctor_p.add_argument("--check-pages-workflow", action="store_true", help="check the local GitHub Pages mdBook workflow files")

    package_p = sub.add_parser("package", help="work with package.ins manifests")
    package_sub = package_p.add_subparsers(dest="package_command", required=True)
    package_init_p = package_sub.add_parser("init", help="initialize a package skeleton in an existing directory")
    package_init_p.add_argument("root", nargs="?", type=Path, default=Path("."), help="package root to initialize")
    package_init_p.add_argument("--name", help="package/module name; defaults to an inferred name from ROOT")
    package_init_p.add_argument("--executable", action="store_true", help="generate an executable-oriented package source")
    package_init_p.add_argument("--library", action="store_true", help="generate the default library-oriented package source")
    package_init_p.add_argument("--with-book", action="store_true", help="also generate a minimal mdBook skeleton")
    package_init_p.add_argument("--force", action="store_true", help="overwrite generated skeleton files if they already exist")
    package_new_p = package_sub.add_parser("new", help="create a new package directory and initialize it")
    package_new_p.add_argument("path", type=Path, help="new package directory")
    package_new_p.add_argument("--name", help="package/module name; defaults to an inferred name from PATH")
    package_new_p.add_argument("--executable", action="store_true", help="generate an executable-oriented package source")
    package_new_p.add_argument("--library", action="store_true", help="generate the default library-oriented package source")
    package_new_p.add_argument("--with-book", action="store_true", help="also generate a minimal mdBook skeleton")
    package_new_p.add_argument("--force", action="store_true", help="allow an existing nonempty target and overwrite generated skeleton files")
    package_check_p = package_sub.add_parser("check", help="validate a package manifest and source layout")
    package_check_p.add_argument("root", nargs="?", type=Path, default=Path("."), help="package root containing package.ins")
    package_check_p.add_argument("--verify", action="store_true", help="also verify package source MLIR with LLVM/MLIR tools")
    _add_diagnostic_format_arg(package_check_p)
    package_test_p = package_sub.add_parser("test", help="discover and run package tests")
    package_test_p.add_argument("root", nargs="?", type=Path, default=Path("."), help="package root containing package.ins")
    package_test_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for dynamic storage bounds")
    package_test_p.add_argument("--save-temps", type=Path, help="directory for per-test source MLIR, lowered MLIR, and LLVM IR intermediates")
    package_test_p.add_argument("--filter", help="run only tests whose display name contains TEXT")
    package_test_p.add_argument("--list", action="store_true", help="list discovered package tests without running them")
    package_test_p.add_argument("--include-dependencies", action="store_true", help="also run tests from local path dependencies")
    _add_optimization_args(package_test_p)
    _add_diagnostic_format_arg(package_test_p)
    package_format_p = package_sub.add_parser("format", help="check or rewrite package Inscription formatting")
    package_format_p.add_argument("root", nargs="?", type=Path, default=Path("."), help="package root containing package.ins")
    package_format_p.add_argument("--check", action="store_true", help="exit 0 only when package files are already formatted")
    package_format_p.add_argument("--in-place", action="store_true", help="overwrite package files with canonical formatting")
    package_format_p.add_argument("--include-dependencies", action="store_true", help="also format/check local path dependencies")
    package_format_p.add_argument("--include-book", action="store_true", help="also run the package book example checker when present")
    _add_diagnostic_format_arg(package_format_p)
    package_clean_p = package_sub.add_parser("clean", help="remove generated package build artifacts")
    package_clean_p.add_argument("root", nargs="?", type=Path, default=Path("."), help="package root containing package.ins")
    package_clean_p.add_argument("--include-dependencies", action="store_true", help="also clean local path dependency packages")
    package_clean_p.add_argument("--dry-run", action="store_true", help="print what would be removed without deleting files")
    _add_diagnostic_format_arg(package_clean_p)
    package_release_p = package_sub.add_parser("release", help="create a deterministic package release bundle")
    package_release_p.add_argument("root", nargs="?", type=Path, default=Path("."), help="package root containing package.ins")
    package_release_p.add_argument("-o", "--output-dir", type=Path, help="release output directory")
    package_release_p.add_argument("--name", help="release directory basename when -o is not supplied")
    package_release_p.add_argument("--include-executable", action="store_true", help="include root executable artifact in bin/")
    package_release_p.add_argument("--include-book", action="store_true", help="include mdBook output in docs/")
    package_release_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for generated code artifacts")
    package_release_p.add_argument("--verify", action="store_true", help="verify emitted artifacts with the LLVM/MLIR 22 toolchain")
    package_release_p.add_argument("--clean", action="store_true", help="replace an existing release output directory")
    package_release_p.add_argument("--dry-run", action="store_true", help="print planned release contents without writing")
    package_release_p.add_argument("--archive", action="store_true", help="also create a deterministic .tar.gz release archive")
    package_release_p.add_argument("--checksum", action="store_true", help="write deterministic SHA-256 checksum manifests")
    _add_optimization_args(package_release_p)
    _add_diagnostic_format_arg(package_release_p)
    package_build_p = package_sub.add_parser("build", help="build package artifacts")
    package_build_p.add_argument("root", nargs="?", type=Path, default=Path("."), help="package root containing package.ins")
    package_build_p.add_argument(
        "--emit",
        default="static-library",
        help=(
            "artifact to emit: mlir, lowered-mlir, llvm-ir, object, executable, "
            "static-library, interface-json, or c-header (default: static-library)"
        ),
    )
    package_build_p.add_argument("-o", "--output", type=Path)
    package_build_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for dynamic storage bounds")
    package_build_p.add_argument(
        "--save-temps",
        type=Path,
        help="directory for saved source MLIR, optimized MLIR when enabled, lowered MLIR, LLVM IR, and object intermediates",
    )
    package_build_p.add_argument("--link-object", action="append", type=Path, default=[], help="additional object file to link for executable emission")
    package_build_p.add_argument(
        "--archive-object",
        action="append",
        type=Path,
        default=[],
        help="additional object file to include in static-library emission",
    )
    package_build_p.add_argument("--verify", action="store_true", help="verify emitted artifacts with the LLVM/MLIR 22 toolchain")
    _add_optimization_args(package_build_p)
    _add_diagnostic_format_arg(package_build_p)
    package_symbols_p = package_sub.add_parser("symbols", help="emit a deterministic package symbol/reference index")
    package_symbols_p.add_argument("root", nargs="?", type=Path, default=Path("."), help="package root containing package.ins")
    package_symbols_p.add_argument("--format", choices=("json",), default="json", help="symbol index output format")
    package_symbols_p.add_argument("--include-dependencies", action="store_true", help="also include local path dependency symbols")
    package_symbols_p.add_argument("--pretty", action="store_true", help="pretty-print JSON with two-space indentation")
    _add_diagnostic_format_arg(package_symbols_p)

    build_p = sub.add_parser("build", help="interpret build.ins and run package workflow/artifact/documentation steps")
    build_p.add_argument("build_args", nargs="*", help="optional PACKAGE_ROOT and optional STEP name")
    build_p.add_argument("--runtime-checks", action="store_true", help="emit runtime assertions for dynamic storage bounds")
    build_p.add_argument(
        "--save-temps",
        type=Path,
        help="directory for per-step compiler/test intermediates; documentation steps write to build/<step>",
    )
    build_p.add_argument("--list", action="store_true", help="list build.ins steps without building")
    build_p.add_argument("--verify", action="store_true", help="verify emitted artifacts with the LLVM/MLIR 22 toolchain")
    _add_optimization_args(build_p)
    _add_diagnostic_format_arg(build_p)

    format_p = sub.add_parser("format", help="format an Inscription source file")
    format_p.add_argument("source", type=Path)
    format_p.add_argument("-o", "--output", type=Path)
    format_p.add_argument("--check", action="store_true", help="exit 0 only when the source is already formatted")
    format_p.add_argument("--in-place", action="store_true", help="overwrite the source file with formatted source")
    _add_diagnostic_format_arg(format_p)

    highlight_p = sub.add_parser("highlight", help="syntax-highlight an Inscription source file")
    highlight_p.add_argument("source", type=Path)
    highlight_p.add_argument("-o", "--output", type=Path)
    highlight_p.add_argument("--format", choices=("terminal", "html"), default="terminal")
    highlight_p.add_argument("--style", default="default", help="Pygments style name")
    highlight_p.add_argument("--full", action="store_true", help="emit a complete HTML document")

    tools_p = sub.add_parser("check-tools", help=f"verify LLVM {REQUIRED_LLVM_MAJOR} toolchain discovery")
    tools_p.add_argument("--show-pipeline", action="store_true", help="show optimization presets and the MLIR lowering pipeline")
    tools_p.add_argument("--require-object", action="store_true", help=f"require LLVM {REQUIRED_LLVM_MAJOR} llc for object emission")
    tools_p.add_argument("--require-executable", action="store_true", help=f"require LLVM {REQUIRED_LLVM_MAJOR} llc and clang for executable emission")
    tools_p.add_argument("--require-static-library", action="store_true", help=f"require LLVM {REQUIRED_LLVM_MAJOR} llc and llvm-ar for static library emission")

    args = parser.parse_args(argv)
    if args.version:
        print(f"inscription {INSCRIPTION_VERSION}")
        return 0
    if args.command is None:
        parser.error("the following arguments are required: command")
    try:
        if args.command == "version":
            if args.json:
                print(json.dumps(version_payload(), indent=2))
            else:
                print("\n".join(version_lines()))
            return 0
        if args.command == "explain":
            if args.list:
                if args.json:
                    sys.stdout.write(diagnostic_catalog_json())
                else:
                    sys.stdout.write(_explain_list_text())
                return 0
            if args.code is None:
                raise InscriptionError("explain requires CODE or --list")
            entry = lookup_diagnostic_code(args.code)
            if entry is None:
                raise InscriptionError(f"unknown diagnostic code {args.code.upper()}")
            if args.json:
                print(json.dumps(entry.__dict__, indent=2, ensure_ascii=False))
            else:
                sys.stdout.write(explain_diagnostic_code(entry))
            return 0
        if args.command == "symbols":
            if args.package:
                index = build_package_source_index(args.source, include_dependencies=False)
            else:
                index = build_source_index(args.source, module_root=args.module_root)
            sys.stdout.write(index.json_text(pretty=args.pretty, include_references=True))
            return 0
        if args.command == "doctor":
            result = run_doctor(
                args.root,
                no_package=args.no_package,
                require_object=args.require_object,
                require_executable=args.require_executable,
                require_static_library=args.require_static_library,
                require_book=args.require_book,
                check_pages_workflow=args.check_pages_workflow,
            )
            if args.json:
                sys.stdout.write(result.json_text())
            else:
                sys.stdout.write(result.text())
            return 0 if result.ok else 2
        if args.command == "compile":
            if args.emit not in EMIT_MODES:
                raise InscriptionError(f"invalid emit mode {args.emit}")
            if args.emit == "object" and args.output is None:
                raise InscriptionError("object emission requires -o OUTPUT")
            if args.emit == "executable" and args.output is None:
                raise InscriptionError("executable emission requires -o OUTPUT")
            if args.emit == "static-library" and args.output is None:
                raise InscriptionError("static library emission requires -o OUTPUT")
            if args.link_object and args.emit != "executable":
                raise InscriptionError("--link-object is supported only with --emit executable")
            if args.archive_object and args.emit != "static-library":
                raise InscriptionError("--archive-object is only valid with --emit static-library")
            link_objects = tuple(args.link_object)
            for path in link_objects:
                if not path.exists():
                    raise InscriptionError(f"link object {path} does not exist")
            archive_objects = tuple(args.archive_object)
            for path in archive_objects:
                if not path.exists():
                    raise InscriptionError(f"archive object {path} does not exist")
            opt_level = _resolve_opt_level(args)
            if args.emit in {"interface-json", "c-header"}:
                context = load_interface_context(args.source, module_root=args.module_root)
                if args.verify:
                    mlir = emit_mlir(context.compilation.program, runtime_checks=args.runtime_checks)
                    build_artifacts(
                        mlir,
                        emit="mlir",
                        verify=True,
                        save_temps=args.save_temps,
                        stem=args.source.stem,
                        opt_level=opt_level,
                    )
                output = emit_interface_json(context) if args.emit == "interface-json" else emit_c_header(context)
                if args.output:
                    args.output.write_text(output)
                else:
                    sys.stdout.write(output)
                return 0
            strip_main_for_static_library = False
            if args.emit in {"executable", "static-library"}:
                source_path = args.source.resolve()
                program = load_program(source_path.read_text(), source_path=source_path, module_root=args.module_root)
                if args.emit == "executable":
                    validate_executable_main(program)
                else:
                    strip_main_for_static_library = any(fn.implementation == "export" for fn in program.functions)
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
                static_library_output=args.output if args.emit == "static-library" else None,
                archive_objects=archive_objects,
                strip_main_for_static_library=strip_main_for_static_library,
            )
            if args.emit in {"executable", "static-library"}:
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
        if args.command == "test":
            opt_level = _resolve_opt_level(args)
            if args.list:
                tests = list_tests(args.source, module_root=args.module_root, filter_text=args.filter)
                if not tests:
                    if args.filter is None:
                        print("no tests found")
                    else:
                        print(f"no tests matched filter `{args.filter}`")
                    return 0
                for display in tests:
                    print(f"test {display}")
                return 0
            summary = run_tests(
                args.source,
                module_root=args.module_root,
                runtime_checks=args.runtime_checks,
                opt_level=opt_level,
                save_temps=args.save_temps,
                filter_text=args.filter,
            )
            if isinstance(summary, str):
                print(summary)
                return 0
            if summary.failed and _diagnostic_format(args) == "json":
                sys.stderr.write(_test_summary_json(summary))
                return summary.exit_status
            for result in summary.results:
                status = "ok" if result.passed else "FAILED"
                print(f"test {result.display_name} ... {status}")
                if not result.passed:
                    _print_test_failure_diagnostic(result)
            print()
            if summary.failed:
                print(f"test result: FAILED. {summary.passed} passed; {summary.failed} failed.")
            else:
                print(f"test result: ok. {summary.passed} passed; 0 failed.")
            return summary.exit_status
        if args.command == "package":
            if args.package_command == "init":
                result = init_package(
                    args.root,
                    name=args.name,
                    executable=args.executable,
                    library=args.library,
                    with_book=args.with_book,
                    force=args.force,
                )
                print(f"package {result.package_name}: initialized")
                return 0
            if args.package_command == "new":
                result = new_package(
                    args.path,
                    name=args.name,
                    executable=args.executable,
                    library=args.library,
                    with_book=args.with_book,
                    force=args.force,
                )
                print(f"package {result.package_name}: created")
                return 0
            if args.package_command == "check":
                context = check_package(args.root, verify=args.verify)
                print(f"package {context.manifest.package_name}: ok")
                return 0
            if args.package_command == "test":
                if args.list:
                    tests = list_package_tests(
                        args.root,
                        filter_text=args.filter,
                        include_dependencies=args.include_dependencies,
                    )
                    if isinstance(tests, str):
                        print(tests)
                        return 0
                    for display in tests:
                        print(f"test {display}")
                    return 0
                summary = run_package_tests(
                    args.root,
                    filter_text=args.filter,
                    include_dependencies=args.include_dependencies,
                    runtime_checks=args.runtime_checks,
                    opt_level=_resolve_opt_level(args),
                    save_temps=args.save_temps,
                )
                if isinstance(summary, str):
                    print(summary)
                    return 0
                if summary.failed and _diagnostic_format(args) == "json":
                    sys.stderr.write(_test_summary_json(summary))
                    return summary.exit_status
                for result in summary.results:
                    status = "ok" if result.passed else "FAILED"
                    print(f"test {result.display_name} ... {status}")
                    if not result.passed:
                        _print_test_failure_diagnostic(result)
                print()
                if summary.failed:
                    print(f"test result: FAILED. {summary.passed} passed; {summary.failed} failed.")
                else:
                    print(f"test result: ok. {summary.passed} passed; 0 failed.")
                return summary.exit_status
            if args.package_command == "format":
                result = format_package(
                    args.root,
                    check=args.check,
                    in_place=args.in_place,
                    include_dependencies=args.include_dependencies,
                    include_book=args.include_book,
                )
                if args.check:
                    print(f"package {result.package_name}: format ok")
                else:
                    print(f"package {result.package_name}: formatted")
                return 0
            if args.package_command == "clean":
                results = clean_package(
                    args.root,
                    include_dependencies=args.include_dependencies,
                    dry_run=args.dry_run,
                )
                for result in results:
                    action = "would remove" if result.dry_run else "removed"
                    if not result.removed:
                        action = "nothing to clean"
                    if args.include_dependencies:
                        if result.removed:
                            print(f"package {result.package_name}: {action} build")
                        else:
                            print(f"package {result.package_name}: {action}")
                    else:
                        if result.removed:
                            print(f"package clean: {action} build")
                        else:
                            print(f"package clean: {action}")
                return 0
            if args.package_command == "release":
                result = release_package(
                    args.root,
                    output_dir=args.output_dir,
                    name=args.name,
                    include_executable=args.include_executable,
                    include_book=args.include_book,
                    runtime_checks=args.runtime_checks,
                    opt_level=_resolve_opt_level(args),
                    verify=args.verify,
                    clean=args.clean,
                    dry_run=args.dry_run,
                    archive=args.archive,
                    checksum=args.checksum,
                )
                root = args.root.resolve()
                output = _display_relative(result.output_dir, root)
                if args.dry_run:
                    print(f"release output: {output}")
                    for artifact in result.artifacts:
                        if artifact.kind == "static-library":
                            print(f"would build static library: {artifact.path}")
                        elif artifact.kind == "c-header":
                            print(f"would build C header: {artifact.path}")
                        elif artifact.kind == "interface-json":
                            print(f"would build interface JSON: {artifact.path}")
                        elif artifact.kind == "executable":
                            print(f"would build executable: {artifact.path}")
                        elif artifact.kind == "book":
                            print("would build book: docs/")
                    print("would copy package manifest: package.ins")
                    print("would write release metadata: release.json")
                    if result.checksum_path is not None:
                        print(f"would write release checksums: {_display_relative(result.checksum_path, root)}")
                    if result.archive_path is not None:
                        print(f"would create release archive: {_display_relative(result.archive_path, root)}")
                    if result.archive_checksum_path is not None:
                        print(f"would write archive checksum: {_display_relative(result.archive_checksum_path, root)}")
                else:
                    print(f"package {result.package_name}: released to {output}")
                return 0
            if args.package_command == "symbols":
                index = build_package_source_index(args.root, include_dependencies=args.include_dependencies)
                sys.stdout.write(index.json_text(pretty=args.pretty, include_references=True))
                return 0
            if args.package_command == "build":
                result = build_package_artifact(
                    args.root,
                    emit=args.emit,
                    output=args.output,
                    runtime_checks=args.runtime_checks,
                    opt_level=_resolve_opt_level(args),
                    save_temps=args.save_temps,
                    link_objects=tuple(args.link_object),
                    archive_objects=tuple(args.archive_object),
                    verify=args.verify,
                )
                if result.data is not None:
                    assert result.output_path is not None
                    result.output_path.write_bytes(result.data)
                elif result.text is not None:
                    if result.output_path is not None:
                        result.output_path.write_text(result.text)
                    else:
                        sys.stdout.write(result.text)
                return 0
        if args.command == "build":
            root, step_name = _resolve_build_positionals(args.build_args)
            if args.list:
                script = load_build_plan(root)
                for step in script.steps:
                    print(f"build step {step.name}: {build_step_display(step)}")
                if script.default_step is not None:
                    print(f"build default: {script.default_step}")
                return 0
            results = run_build_script(
                root,
                step_name=step_name,
                runtime_checks=args.runtime_checks,
                opt_level=_resolve_opt_level(args),
                save_temps=args.save_temps,
                verify=args.verify,
            )
            if _diagnostic_format(args) == "json":
                for result in results:
                    if result.failed:
                        if isinstance(result.test_summary, PackageTestSummary):
                            sys.stderr.write(_test_summary_json(result.test_summary))
                        else:
                            diagnostic = Diagnostic(f"build step {result.step.name} failed", code="INS-BUILD-0004")
                            sys.stderr.write(render_diagnostics_json((diagnostic,)))
                        return 1
            exit_status = 0
            for result in results:
                if result.failed:
                    print(f"build step {result.step.name} ... FAILED")
                    if isinstance(result.test_summary, PackageTestSummary):
                        for test_result in result.test_summary.results:
                            status = "ok" if test_result.passed else "FAILED"
                            print(f"test {test_result.display_name} ... {status}")
                            if not test_result.passed:
                                _print_test_failure_diagnostic(test_result)
                        print()
                        print(
                            f"test result: FAILED. {result.test_summary.passed} passed; "
                            f"{result.test_summary.failed} failed."
                        )
                    exit_status = 1
                    continue
                print(f"build step {result.step.name} ... ok")
                if isinstance(result.test_summary, str):
                    print(result.test_summary)
                elif isinstance(result.test_summary, PackageTestSummary):
                    print(f"test result: ok. {result.test_summary.passed} passed; 0 failed.")
                elif result.output_path is not None:
                    print(f"built {result.step.name}: {_display_relative(result.output_path, root)}")
            return exit_status
        if args.command == "format":
            if args.in_place and args.output is not None:
                raise InscriptionError("--in-place cannot be used with -o")
            if args.check and args.in_place:
                raise InscriptionError("--check cannot be used with --in-place")
            if args.check and args.output is not None:
                raise InscriptionError("--check cannot be used with -o")
            original = args.source.read_text()
            formatted = format_file(args.source)
            if args.check:
                if formatted != original:
                    raise InscriptionError(f"formatting check failed: {args.source} is not formatted")
                return 0
            if args.in_place:
                args.source.write_text(formatted)
            elif args.output is not None:
                args.output.write_text(formatted)
            else:
                sys.stdout.write(formatted)
            return 0
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
            toolchain = resolve_toolchain(
                require_object=args.require_object,
                require_executable=args.require_executable,
                require_static_library=args.require_static_library,
            )
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
            if toolchain.llvm_ar is None:
                print("llvm-ar=unavailable (optional)")
            else:
                print(f"llvm-ar={toolchain.llvm_ar}")
            if args.show_pipeline:
                print("optimization presets:")
                for name, passes in OPTIMIZATION_PRESETS.items():
                    print(f"  {name}: {_format_preset(passes)}")
                print("mlir-opt input.mlir " + " ".join(LOWERING_PASSES) + " -o lowered.mlir")
                print("mlir-translate --mlir-to-llvmir lowered.mlir -o output.ll")
                print("lli output.ll")
                print("object emission: llc -relocation-model=pic -filetype=obj output.ll -o output.o")
                print("executable emission: clang output.o -o executable")
                print("static library emission: llvm-ar rcsD output.a output.o")
            return 0
    except (InscriptionError, ToolchainError, OSError) as exc:
        diagnostic_format = _diagnostic_format(args)
        if isinstance(exc, InscriptionError):
            _attach_cli_source_context(args, exc)
            if diagnostic_format == "json":
                sys.stderr.write(render_diagnostics_json((exc.to_diagnostic(),)))
            else:
                print(render_exception(exc), file=sys.stderr)
        elif isinstance(exc, ToolchainError):
            diagnostic = _toolchain_diagnostic(exc)
            if diagnostic_format == "json":
                sys.stderr.write(render_diagnostics_json((diagnostic,)))
            else:
                print(render_diagnostic(diagnostic), file=sys.stderr)
        else:
            diagnostic = Diagnostic(str(exc), code=diagnostic_code_for_message(str(exc)))
            if diagnostic_format == "json":
                sys.stderr.write(render_diagnostics_json((diagnostic,)))
            else:
                print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(args.command)  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
