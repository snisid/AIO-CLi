"""Fail-closed release gate.

Default mode checks repository implementation evidence for CI. Set
AIO_CLI_PRODUCTION_GATE=1 in the actual target environment to require every
production verification row in the matrix to be PASS.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "10_10_DOMAIN_MATRIX.md"
FORBIDDEN = ("FUTURE IMPLEMENTATION", "MOCK-ONLY", "WILL BE FULLY IMPLEMENTED", "PHASE 13+")
MANDATORY = (
    "Native Runtime", "Tool Engine", "Security / Sandbox", "Model Routing", "Providers",
    "MCP", "Git", "Browser", "Desktop", "Windows Installer", "Upgrade / Rollback",
    "Observability", "QA / Release Gate",
)


def main() -> int:
    if not MATRIX.exists():
        print("RELEASE: BLOCKED - domain matrix missing")
        return 1
    text = MATRIX.read_text(encoding="utf-8")
    missing = [item for item in MANDATORY if item not in text]
    if missing:
        print("RELEASE: BLOCKED - missing domains:", ", ".join(missing))
        return 1
    violations: list[str] = []
    for path in ROOT.glob("ma_cli/**/*.py"):
        source = path.read_text(encoding="utf-8", errors="ignore").upper()
        for marker in FORBIDDEN:
            if marker in source:
                violations.append(f"{path.relative_to(ROOT)}: {marker}")
    if violations:
        print("RELEASE: BLOCKED - dead placeholder paths found")
        for item in violations:
            print("  -", item)
        return 1
    if os.getenv("AIO_CLI_PRODUCTION_GATE") != "1":
        print("RELEASE: STATIC APPROVED (live production verification not asserted)")
        return 0
    failures: list[str] = []
    for row in text.splitlines():
        if not row.startswith("|") or "---" in row:
            continue
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) >= 8 and cells[0] != "Domain" and cells[7].upper() != "PASS":
            failures.append(f"{cells[0]}={cells[7]}")
    if failures:
        print("RELEASE: BLOCKED - production verification incomplete")
        for item in failures:
            print("  -", item)
        return 1
    print("RELEASE: PRODUCTION APPROVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
