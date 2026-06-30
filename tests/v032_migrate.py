"""Internal one-off v0.32 migration helper for historical test snippets.

This module is not a user-facing compatibility layer or formatter. The
supported canonical formatter is `inscription format`.
"""

from __future__ import annotations

import re
from pathlib import Path


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_colon(text: str) -> str:
    return text[:-1].strip() if text.endswith(":") else text.strip()


def _cap_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def _convert_expr_line(text: str) -> str:
    if text.startswith("let "):
        return "Let " + text[4:] + "."
    if text.startswith("require "):
        return "Require " + text[8:] + "."
    if text.startswith("check "):
        return "Check " + text[6:] + "."
    if text.startswith("write "):
        return "Write " + text[6:] + "."
    return text + "."


def _collect_block(lines: list[str], index: int, parent_indent: int) -> tuple[list[str], int]:
    out: list[str] = []
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        if _indent_of(lines[index]) <= parent_indent:
            break
        out.append(lines[index])
        index += 1
    return out, index


def _find_value_start(body: list[str]) -> int:
    end = len(body)
    while end and not body[end - 1].strip():
        end -= 1
    body = body[:end]
    if not body:
        return 0

    # Final match expressions are a header followed by arm lines. Detect them
    # before ordinary guarded value blocks so the otherwise arm stays attached
    # to the match instead of becoming a separate Give sentence.
    last_index = end - 1
    last_indent = _indent_of(body[last_index])
    index = last_index - 1
    while index >= 0:
        text = body[index].strip()
        indent = _indent_of(body[index])
        if indent < last_indent:
            if text.startswith("match ") and text.endswith(":"):
                arm_texts = [line.strip() for line in body[index + 1 : end] if line.strip()]
                if any(" gives " in arm or arm.startswith("otherwise gives ") for arm in arm_texts):
                    return index
            break
        index -= 1

    last = body[-1]
    base = _indent_of(last)
    if last.strip().startswith("otherwise "):
        index = end - 2
        while index >= 0 and _indent_of(body[index]) == base and " when " in body[index].strip():
            index -= 1
        if index < end - 2:
            return index + 1
    return end - 1


def _convert_value(lines: list[str], out: list[str], indent: int) -> None:
    lines = [line for line in lines if line.strip()]
    if not lines:
        return
    if len(lines) == 1:
        out.append(" " * indent + "Give " + lines[0].strip() + ".")
        return
    first = lines[0].strip()
    if first.startswith("match ") and first.endswith(":"):
        out.append(" " * indent + "Give " + first)
        for line in lines[1:]:
            out.append(" " * indent + "  " + line.strip() + ".")
        out.append(" " * indent + ".")
        return
    out.append(" " * indent + "Give " + "; ".join(line.strip() for line in lines) + ".")


def _convert_steps(lines: list[str], out: list[str], base_indent: int) -> None:
    index = 0
    while index < len(lines):
        raw = lines[index]
        if not raw.strip():
            index += 1
            continue
        indent = _indent_of(raw)
        text = raw.strip()
        if text.startswith("if ") and text.endswith(":"):
            condition = _strip_colon(text)[3:]
            then_block, after_then = _collect_block(lines, index + 1, indent)
            probe = after_then
            while probe < len(lines) and not lines[probe].strip():
                probe += 1
            has_otherwise = probe < len(lines) and _indent_of(lines[probe]) == indent and lines[probe].strip() == "otherwise:"
            out.append(" " * indent + f"When {condition}:")
            _convert_steps(then_block, out, indent + 2)
            if has_otherwise:
                else_block, after_else = _collect_block(lines, probe + 1, indent)
                out.append(" " * indent + "Otherwise:")
                _convert_steps(else_block, out, indent + 2)
                index = after_else
            else:
                index = probe
            out.append(" " * indent + ".")
            continue
        if (text.startswith("while ") or text.startswith("for ")) and text.endswith(":"):
            keyword = "While" if text.startswith("while ") else "For"
            rest = _strip_colon(text)[6:] if keyword == "While" else _strip_colon(text)[4:]
            out.append(" " * indent + f"{keyword} {rest}:")
            block, next_index = _collect_block(lines, index + 1, indent)
            _convert_steps(block, out, indent + 2)
            out.append(" " * indent + ".")
            index = next_index
            continue
        if text.startswith("match ") and text.endswith(":"):
            out.append(" " * indent + "Match " + _strip_colon(text)[6:] + ":")
            arm_index = index + 1
            while arm_index < len(lines):
                if not lines[arm_index].strip():
                    arm_index += 1
                    continue
                if _indent_of(lines[arm_index]) <= indent:
                    break
                arm_text = lines[arm_index].strip()
                arm_indent = _indent_of(lines[arm_index])
                if arm_text.endswith(":"):
                    out.append(" " * arm_indent + _strip_colon(arm_text) + ":")
                    block, next_arm = _collect_block(lines, arm_index + 1, arm_indent)
                    _convert_steps(block, out, arm_indent + 2)
                    arm_index = next_arm
                else:
                    out.append(" " * arm_indent + arm_text + ".")
                    arm_index += 1
            out.append(" " * indent + ".")
            index = arm_index
            continue
        if text.endswith(":"):
            if text.startswith("let "):
                header = "Let " + _strip_colon(text)[4:] + ":"
            elif text.startswith("require "):
                header = "Require " + _strip_colon(text)[8:] + ":"
            elif text.startswith("check "):
                header = "Check " + _strip_colon(text)[6:] + ":"
            else:
                header = _cap_first(_strip_colon(text)) + ":"
            out.append(" " * indent + header)
            block, next_index = _collect_block(lines, index + 1, indent)
            for line in block:
                if line.strip():
                    out.append(" " * _indent_of(line) + line.strip() + ".")
            out.append(" " * indent + ".")
            index = next_index
            continue
        out.append(" " * indent + _convert_expr_line(text))
        index += 1


def _convert_phrase(header: str, body: list[str], out: list[str]) -> None:
    text = _strip_colon(header.strip())
    is_gives = False
    if text.startswith("export "):
        rest = text[len("export "):]
        match = re.fullmatch(r"(.+?) gives (.+) as ([A-Za-z_][A-Za-z0-9_.]*)", rest)
        if match is not None:
            out.append(f"To {match.group(1)}, giving {match.group(2)}, exported as {match.group(3)}.")
            is_gives = True
        else:
            match = re.fullmatch(r"(.+?) does as ([A-Za-z_][A-Za-z0-9_.]*)", rest)
            if match is None:
                raise ValueError("bad export header")
            out.append(f"To {match.group(1)}, exported as {match.group(2)}.")
    else:
        match = re.fullmatch(r"(.+?) gives (.+)", text)
        if match is not None:
            out.append(f"To {match.group(1)}, giving {match.group(2)}.")
            is_gives = True
        else:
            match = re.fullmatch(r"(.+?) does", text)
            if match is None:
                raise ValueError("bad phrase header")
            out.append(f"To {match.group(1)}.")
    if is_gives:
        value_start = _find_value_start(body)
        _convert_steps(body[:value_start], out, 2)
        _convert_value(body[value_start:], out, 2)
    else:
        _convert_steps(body, out, 2)
    out.append("")


def convert_source(source: str) -> str:
    lines = source.splitlines()
    out: list[str] = []
    index = 0
    while index < len(lines):
        raw = lines[index]
        if not raw.strip():
            index += 1
            continue
        if _indent_of(raw) != 0:
            raise ValueError("unexpected indented top-level line")
        text = raw.strip()
        if text.startswith("Module ") or text.startswith("To ") or text.startswith("Record ") or text.startswith("Enum ") or text.startswith("Union ") or text.startswith("External ") or text.startswith("Type "):
            raise ValueError("already v0.32")
        if text.startswith("module "):
            out.extend(["Module " + text[7:] + ".", ""])
            index += 1
            continue
        if text.startswith("import "):
            out.append("Import " + text[7:] + ".")
            index += 1
            continue
        if text.startswith("type "):
            out.extend(["Type " + text[5:] + ".", ""])
            index += 1
            continue
        if text.startswith("constant "):
            if text.endswith(":"):
                block, next_index = _collect_block(lines, index + 1, 0)
                out.append("Constant " + _strip_colon(text)[9:] + ":")
                for line in block:
                    if line.strip():
                        out.append("  " + line.strip() + ".")
                out.extend([".", ""])
                index = next_index
                continue
            out.extend(["Constant " + text[9:] + ".", ""])
            index += 1
            continue
        if text.startswith("check "):
            out.extend(["Check " + text[6:] + ".", ""])
            index += 1
            continue
        if text.startswith("record ") or text.startswith("layout record ") or text.startswith("packed layout record "):
            kind = "Record"
            rest = text[7:-1]
            if text.startswith("layout record "):
                kind = "Layout record"
                rest = text[len("layout record "):-1]
            if text.startswith("packed layout record "):
                kind = "Packed layout record"
                rest = text[len("packed layout record "):-1]
            block, next_index = _collect_block(lines, index + 1, 0)
            fields = "; ".join(line.strip() for line in block if line.strip())
            out.extend([f"{kind} {rest} has {fields}.", ""])
            index = next_index
            continue
        if text.startswith("enum "):
            match = re.fullmatch(r"enum ([A-Za-z][A-Za-z0-9_]*):\s*(.+):", text)
            if match is None:
                raise ValueError("bad enum")
            block, next_index = _collect_block(lines, index + 1, 0)
            out.extend([f"Enum {match.group(1)} backed by {match.group(2)} has {'; '.join(line.strip() for line in block if line.strip())}.", ""])
            index = next_index
            continue
        if text.startswith("union "):
            name = text[len("union "):-1]
            block, next_index = _collect_block(lines, index + 1, 0)
            out.extend([f"Union {name} has {'; '.join(line.strip() for line in block if line.strip())}.", ""])
            index = next_index
            continue
        if text.startswith("extern "):
            rest = text[len("extern "):]
            match = re.fullmatch(r"(.+?) gives (.+) as ([A-Za-z_][A-Za-z0-9_.]*)", rest)
            if match is not None:
                out.append(f"External {match.group(1)}, giving {match.group(2)}, as {match.group(3)}.")
            else:
                match = re.fullmatch(r"(.+?) does as ([A-Za-z_][A-Za-z0-9_.]*)", rest)
                if match is None:
                    raise ValueError("bad extern")
                out.append(f"External {match.group(1)}, as {match.group(2)}.")
            out.append("")
            index += 1
            continue
        if text.startswith("export ") or text.endswith(":"):
            body, next_index = _collect_block(lines, index + 1, 0)
            _convert_phrase(text, body, out)
            index = next_index
            continue
        raise ValueError("unhandled top-level line")
    return "\n".join(out).rstrip() + "\n"


def maybe_convert_source(source: str) -> str:
    try:
        return convert_source(source)
    except Exception:
        return source


def maybe_convert_path(path: Path) -> None:
    if path.suffix != ".ins" or not path.exists():
        return
    source = path.read_text()
    converted = maybe_convert_source(source)
    if converted != source:
        path.write_text(converted)
