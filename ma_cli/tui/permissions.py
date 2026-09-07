"""Interactive permission prompts for high-risk tools."""
from __future__ import annotations

import sys

from .render import permission_prompt


def tty_grant(tool: str, summary: str) -> str:
    if not sys.stdin.isatty():
        return "n"
    print(permission_prompt(tool, summary))
    try:
        return input("allow> ").strip() or "n"
    except (EOFError, KeyboardInterrupt):
        return "n"
