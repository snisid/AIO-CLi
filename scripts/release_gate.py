"""Fail-closed MA-CLI release gate.

This gate checks repository evidence and refuses to declare 10/10 when any
mandatory domain is unverified. It intentionally does not manufacture live
provider, Windows, MCP, browser, or installer evidence.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "10_10_DOMAIN_MATRIX.md"

FORBIDDEN = ("TODO", "PLACEHOLDER", "FUTURE IMPLEMENTATION", "MOCK-ONLY")
MANDATORY = (
    "Native Runtime", "Tool Engine", "Security / Sandbox", "Model Routing",
    "Providers", "MCP", "Git", "Browser", "Desktop", "Windows Installer",
    "Upgrade / Rollback", "Observability", "QA / Release Gate",
)
INCOMPLETE = (
    "IMPLEMENTATION REQUIRED", "INTEGRATION REQUIRED", "TEST REQUIRED",
    "SECURITY REQUIRED", "IN PROGRESS", "NOT COMPLETE", "PARTIAL",
    "PENDING LIVE", "PENDING WINDOWS LIVE", "UNVERIFIED", "SKIPPED", "BLOCKED",
)


def _production_cells(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("|") or "Domain" in line or set(line.replace("|", "").strip()) <= {"-"}:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 8:
            continue
        rows.append((cells[0], cells[7]))
    return rows


def main() -> int:
    if not MATRIX.exists():
        print("RELEASE: BLOCKED - domain matrix is missing")
        return 1
    text = MATRIX.read_text(encoding="utf-8")
    upper = text.upper()
    missing = [domain for domain in MANDATORY if domain not in text]
    if missing:
        print("RELEASE: BLOCKED - missing domains:", ", ".join(missing))
        return 1
    if "PRODUCTION VERIFIED" not in upper:
        print("RELEASE: BLOCKED - production verification column missing")
        return 1
    hits = [token for token in INCOMPLETE if token in upper]
    if hits:
        print("RELEASE: BLOCKED - mandatory evidence is incomplete or unverified:", ", ".join(hits))
        return 1
    pending = [name for name, cell in _production_cells(text) if cell.upper() != "PASS"]
    if pending:
        print("RELEASE: BLOCKED - production verification is not PASS for:", ", ".join(pending))
        return 1
    print("RELEASE: APPROVED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
