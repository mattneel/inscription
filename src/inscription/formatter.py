from __future__ import annotations

import re
from pathlib import Path

from .parser import (
    _find_top_level_char,
    _is_phrase_boundary_sentence,
    _split_match_step_arms,
    _split_punctuation_sentences,
    _split_semicolons,
    normalize_punctuation_source,
)

_TOP_LEVEL_PREFIXES = (
    "Module ",
    "Import ",
    "Type ",
    "Constant ",
    "Check ",
    "Record ",
    "Layout record ",
    "Packed layout record ",
    "Enum ",
    "Union ",
    "External ",
    "To ",
)

_KEYWORD_CASE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), replacement)
    for pattern, replacement in (
        (r"^module\b", "Module"),
        (r"^import\b", "Import"),
        (r"^type\b", "Type"),
        (r"^constant\b", "Constant"),
        (r"^check\b", "Check"),
        (r"^record\b", "Record"),
        (r"^layout record\b", "Layout record"),
        (r"^packed layout record\b", "Packed layout record"),
        (r"^enum\b", "Enum"),
        (r"^union\b", "Union"),
        (r"^external\b", "External"),
        (r"^extern\b", "External"),
        (r"^to\b", "To"),
        (r"^let\b", "Let"),
        (r"^require\b", "Require"),
        (r"^write\b", "Write"),
        (r"^give\b", "Give"),
        (r"^when\b", "When"),
        (r"^otherwise\b", "Otherwise"),
        (r"^while\b", "While"),
        (r"^for\b", "For"),
        (r"^match\b", "Match"),
    )
)


def format_file(path: Path) -> str:
    return format_source(path.read_text())


def format_source(source: str) -> str:
    """Return deterministic canonical v0.32-v0.34 punctuation source.

    The formatter validates the punctuation sentence structure by running the
    source through the parser's punctuation normalizer, then pretty-prints the
    sentence stream. It intentionally avoids semantic analysis and LLVM/MLIR
    tooling so imported modules or host toolchains are not required.
    """

    normalize_punctuation_source(source)
    sentences = _split_punctuation_sentences(source)
    formatted_sentences = [_format_sentence(sentence.text) for sentence in sentences]
    out: list[str] = []
    in_phrase = False
    previous_was_import = False
    for sentence in formatted_sentences:
        first_line = sentence.splitlines()[0]
        top_level = _is_top_level_first_line(first_line)
        phrase_boundary = _is_phrase_boundary_first_line(first_line)
        if top_level and (not in_phrase or phrase_boundary):
            if out:
                if first_line.startswith("Import ") and previous_was_import:
                    pass
                else:
                    _ensure_blank_line(out)
            in_phrase = first_line.startswith("To ")
            previous_was_import = first_line.startswith("Import ")
        else:
            previous_was_import = False
        out.extend(sentence.splitlines())
        if first_line.startswith("To "):
            in_phrase = True
        elif phrase_boundary and not first_line.startswith("To "):
            in_phrase = False
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def _ensure_blank_line(lines: list[str]) -> None:
    if lines and lines[-1] != "":
        lines.append("")


def _is_top_level_first_line(line: str) -> bool:
    return line.startswith(_TOP_LEVEL_PREFIXES)


def _is_phrase_boundary_first_line(line: str) -> bool:
    return _is_phrase_boundary_sentence(line)


def _format_sentence(text: str) -> str:
    text = _canonical_keyword_case(text.strip())
    text = _clean_outer_punctuation_spacing(text)
    if text.startswith("Record ") or text.startswith("Layout record ") or text.startswith("Packed layout record "):
        return _format_semicolon_declaration(text)
    if text.startswith("Enum ") or text.startswith("Union "):
        return _format_semicolon_declaration(text)
    if text.startswith(("For ", "While ", "When ")):
        control = _format_control_with_nested_match(text)
        if control is not None:
            return control
    if text.startswith("Match "):
        return _format_match_step_sentence(text)
    if not text.startswith(("To ", "External ", "Import ", "Module ", "Record ", "Layout record ", "Packed layout record ", "Enum ", "Union ", "Type ")):
        match_index = _find_keyword(text, "match")
        if match_index != -1:
            maybe = _format_match_expression_sentence(text, match_index)
            if maybe is not None:
                return maybe
    return _format_simple_sentence(text)


def _canonical_keyword_case(text: str) -> str:
    for pattern, replacement in _KEYWORD_CASE_REPLACEMENTS:
        if pattern.match(text):
            return pattern.sub(replacement, text, count=1)
    return text


def _clean_outer_punctuation_spacing(text: str) -> str:
    """Normalize spaces around punctuation outside strings.

    This intentionally stays conservative: it removes spaces before commas,
    colons, and semicolons, and ensures one following space for commas and
    semicolons when they are used inside a line. Periods are added by the
    formatter and are therefore not handled here.
    """

    out: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            out.append(char)
            in_string = True
            index += 1
            continue
        if char in ",;:":
            while out and out[-1] == " ":
                out.pop()
            out.append(char)
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
            if char in ",;" and index < len(text):
                out.append(" ")
            elif char == ":" and index < len(text) and text[index] not in " ;":
                out.append(" ")
            continue
        out.append(char)
        index += 1
    return "".join(out).strip()


def _format_control_with_nested_match(text: str) -> str | None:
    colon = _find_top_level_char(text, ":")
    comma = _find_top_level_char(text, ",")
    if colon == -1 and comma == -1:
        return None
    separator = colon if colon != -1 and (comma == -1 or colon < comma) else comma
    head = text[:separator].strip()
    body = text[separator + 1 :].strip()
    if not body.startswith("Match "):
        return None
    if _contains_then_marker(body):
        return None
    return f"{head}:\n{_format_match_step_sentence(body)}"



def _contains_then_marker(text: str) -> bool:
    parts = _split_semicolons(text)
    return any(part.strip() == "then" or part.strip().startswith("then ") for part in parts[1:])


def _format_simple_sentence(text: str) -> str:
    if text.endswith("."):
        return text
    return f"{text}."


def _format_semicolon_declaration(text: str) -> str:
    head, clauses = _split_colonless_clause_list(text)
    if clauses is None:
        return _format_simple_sentence(text)
    return f"{head} {'; '.join(_clean_outer_punctuation_spacing(clause) for clause in clauses)}."


def _split_colonless_clause_list(text: str) -> tuple[str, list[str] | None]:
    markers = (" has ",)
    for marker in markers:
        index = text.find(marker)
        if index != -1:
            head = text[: index + len(marker)].strip()
            clauses_text = text[index + len(marker) :].strip()
            if not clauses_text:
                return text, None
            return head, _split_semicolons(clauses_text)
    return text, None


def _format_match_expression_sentence(text: str, match_index: int) -> str | None:
    colon = _find_top_level_char(text[match_index:], ":")
    if colon == -1:
        return None
    colon_index = match_index + colon
    header = _clean_outer_punctuation_spacing(text[: colon_index + 1].strip())
    arms_text = text[colon_index + 1 :].strip()
    if not arms_text:
        return f"{header}."
    arms = [_clean_outer_punctuation_spacing(arm) for arm in _split_semicolons(arms_text)]
    if not arms:
        return f"{header}."
    lines = [header]
    for arm in arms[:-1]:
        lines.append(f"{arm};")
    lines.append(f"{arms[-1]}.")
    return "\n".join(lines)


def _format_match_step_sentence(text: str) -> str:
    rest = text[len("Match ") :].strip()
    colon = _find_top_level_char(rest, ":")
    if colon == -1:
        return _format_simple_sentence(text)
    scrutinee = _clean_outer_punctuation_spacing(rest[:colon].strip())
    arms_text = rest[colon + 1 :].strip()
    arms = [_clean_outer_punctuation_spacing(arm) for arm in _split_match_step_arms(arms_text)]
    lines = [f"Match {scrutinee}:"]
    if not arms:
        lines[0] += "."
        return "\n".join(lines)
    for arm in arms[:-1]:
        lines.append(f"{arm};")
    lines.append(f"{arms[-1]}.")
    return "\n".join(lines)


def _find_keyword(text: str, keyword: str) -> int:
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if text.startswith(keyword, index):
            before = text[index - 1] if index > 0 else " "
            after = text[index + len(keyword)] if index + len(keyword) < len(text) else " "
            if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                return index
        index += 1
    return -1
