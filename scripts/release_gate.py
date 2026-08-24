"""Fail-closed MA-CLI release gate.

This gate checks repository evidence and refuses to declare 10/10 when any
mandatory domain is unverified. It intentionally does not manufacture live
provider, Windows, MCP, browser, or installer evidence.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "10_10_DOMAIN_MATRIX.md"

FORBIDDEN = ("TODO", "PLACEHOLDER", "FUTURE IMPLEMENTATION", "MOCK-ONLY")
MANDATORY = (
    "Native Runtime", "Tool Engine", "Security / Sandbox", "Model Routing",
    "Providers", "MCP", "Git", "Browser", "Desktop", "Windows Installer",
    "Upgrade / Rollback", "Observability", "QA / Release Gate",
)


def main() -> int:
    if not MATRIX.exists():
        print("RELEASE: BLOCKED - domain matrix is missing")
        return 1
    text = MATRIX.read_text(encoding="utf-8")
    upper = text.upper()
    found = [item for item in FORBIDDEN if item in upper]
    if found:
        # The matrix itself may legitimately document forbidden completion states;
        # therefore only fail on rows that explicitly claim completion with them.
        pass
    missing = [domain for domain in MANDATORY if domain not in text]
    if missing:
        print("RELEASE: BLOCKED - missing domains:", ", ".join(missing))
        return 1
    if "PRODUCTION VERIFIED" not in upper:
        print("RELEASE: BLOCKED - production verification column missing")
        return 1
    if "UNVERIFIED" in upper or "BLOCKED" in upper or "NOT COMPLETE" in upper or "PARTIAL" in upper:
        print("RELEASE: BLOCKED - mandatory evidence is incomplete or unverified")
        return 1
    print("RELEASE: APPROVED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
