"""Claude Code-style terminal rendering. Rich is optional; ASCII always works."""
from __future__ import annotations

import os
import shutil
from typing import Any


def _width() -> int:
    try:
        return max(60, min(shutil.get_terminal_size((80, 24)).columns, 100))
    except OSError:
        return 80


def _unicode() -> bool:
    encoding = (os.getenv("LANG") or "") + (os.getenv("LC_ALL") or "")
    return "UTF" in encoding.upper() or True


def box(title: str, body: str = "", ok: bool | None = None, width: int | None = None) -> str:
    width = width or _width()
    if _unicode():
        tl, tr, bl, br, h, v = "╭", "╮", "╰", "╯", "─", "│"
        mark = "●" if ok is True else ("✗" if ok is False else "⏺")
    else:
        tl, tr, bl, br, h, v = "+", "+", "+", "+", "-", "|"
        mark = "*" if ok is True else ("x" if ok is False else "o")
    inner = max(20, width - 2)
    label = f"{mark} {title}".strip()
    if len(label) > inner - 2:
        label = label[: inner - 5] + "..."
    pad = inner - 1 - len(label)
    top = f"{tl}{h} {label} {h * max(1, pad - 1)}{tr}"
    lines = [top]
    content = (body or "").rstrip("\n").splitlines() or ([] if not body else [""])
    for raw in content[:40]:
        text = raw.replace("\t", "  ")
        if len(text) > inner - 2:
            text = text[: inner - 5] + "..."
        lines.append(f"{v} {text.ljust(inner - 2)} {v}")
    if len(content) > 40:
        extra = f"... {len(content) - 40} more lines"
        lines.append(f"{v} {extra.ljust(inner - 2)} {v}")
    lines.append(f"{bl}{h * inner}{br}")
    return "\n".join(lines)


def header(cwd: str, branch: str | None, model: str | None, mode: str) -> str:
    bits = ["MA-CLI", cwd]
    if branch:
        bits.append(branch)
    bits.append(model or "no model")
    bits.append(mode)
    return box("session", " · ".join(bits))


def user_bubble(text: str) -> str:
    return f"> {text.strip()}"


def assistant_text(text: str) -> str:
    return (text or "").rstrip()


def render_tool(name: str, detail: str, ok: bool | None = None) -> str:
    return box(name, detail.strip() if detail else "", ok=ok)


def render_evidence(evidence: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for item in evidence or []:
        stage = str(item.get("stage") or "step")
        if stage in {"test", "final_validation", "repair_validation"}:
            output = str(item.get("output") or "")
            failures = item.get("failures") or []
            body = output[-1200:] if output else ("\n".join(str(f) for f in failures) or "no output")
            chunks.append(render_tool(f"Test · {stage}", body, ok=bool(item.get("passed"))))
            continue
        if stage == "security":
            chunks.append(render_tool(
                "Security",
                str(item.get("reason") or ""),
                ok=bool(item.get("allowed", True)),
            ))
            continue
        for call in item.get("tool_calls") or []:
            tool = str(call.get("tool") or call.get("name") or "tool")
            result = call.get("result")
            detail = result if isinstance(result, str) else str(result)
            chunks.append(render_tool(tool, detail[:1200]))
        output = str(item.get("output") or "").strip()
        if output:
            chunks.append(assistant_text(output))
    return "\n".join(chunk for chunk in chunks if chunk)


def shortcuts() -> str:
    return "  /help  /status  /mode  /review  /diff  /clear  /exit"


def permission_prompt(tool: str, summary: str) -> str:
    return box("permission", f"{tool}\n{summary}\nAllow? y / n / always")
