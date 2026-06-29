from __future__ import annotations

from .mlir import emit_mlir
from .parser import parse_source


def compile_source(source: str) -> str:
    return emit_mlir(parse_source(source))
