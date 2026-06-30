#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from inscription.highlighting import HighlightError, highlight_source
except ModuleNotFoundError as exc:  # pragma: no cover - exercised by script error path
    print(f"Inscription mdBook preprocessor could not import the local package: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc

FENCE_RE = re.compile(r"```(?P<info>[^\n`]*)\n(?P<code>.*?)\n```", re.DOTALL)


class PreprocessorError(RuntimeError):
    pass


def _is_inscription_info(info: str) -> bool:
    head = info.strip().split(None, 1)[0] if info.strip() else ""
    language = head.split(",", 1)[0].strip().lower()
    return language in {"inscription", "ins"}


def _highlight_block(code: str) -> str:
    try:
        highlighted = highlight_source(code, output_format="html", style="default", full=False)
    except HighlightError as exc:
        raise PreprocessorError(
            "Inscription mdBook preprocessor requires Pygments; install docs dependencies with "
            "`python -m pip install -e \".[docs]\"`"
        ) from exc
    return f'<div class="inscription-code" role="region" aria-label="Inscription code">\n{highlighted}</div>'


def transform_markdown(markdown: str, highlighter: Callable[[str], str] = _highlight_block) -> str:
    def replace(match: re.Match[str]) -> str:
        info = match.group("info")
        code = match.group("code")
        if not _is_inscription_info(info):
            return match.group(0)
        try:
            return highlighter(code)
        except PreprocessorError:
            raise
        except Exception as exc:  # pragma: no cover - defensive error normalization
            raise PreprocessorError(f"failed to highlight Inscription code block: {exc}") from exc

    return FENCE_RE.sub(replace, markdown)


def transform_book(book: dict[str, Any], highlighter: Callable[[str], str] = _highlight_block) -> dict[str, Any]:
    def visit_sections(sections: list[dict[str, Any]]) -> None:
        for section in sections:
            chapter = section.get("Chapter")
            if not chapter:
                continue
            chapter["content"] = transform_markdown(chapter.get("content", ""), highlighter=highlighter)
            visit_sections(chapter.get("sub_items", []))

    visit_sections(book.get("sections", []))
    return book


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "supports":
        renderer = argv[1] if len(argv) > 1 else "html"
        return 0 if renderer == "html" else 1
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, list) or len(payload) != 2:
            raise PreprocessorError("mdBook preprocessor input must be [context, book]")
        _context, book = payload
        json.dump(transform_book(book), sys.stdout)
        sys.stdout.write("\n")
        return 0
    except PreprocessorError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"invalid mdBook preprocessor JSON: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
