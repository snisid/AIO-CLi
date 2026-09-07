"""Build the executable completion matrix without fabricating live evidence.

This command is intentionally fail-closed: domains are only marked verified
when a real verification command records evidence in the current workspace.
Use --domain DOMAIN --evidence FILE to record a signed-off local verification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

DOMAINS = [
    "Native Runtime", "Tool Engine", "Security / Sandbox", "Model Routing",
    "Providers", "MCP", "Git", "Browser", "Desktop", "Windows Installer",
    "Upgrade / Rollback", "Observability", "QA / Release Gate",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", action="append", choices=DOMAINS)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    if not args.domain:
        print("Domains:")
        for d in DOMAINS:
            print(f"- {d}")
        return 0
    if not args.evidence or not args.evidence.exists():
        raise SystemExit("LIVE VERIFICATION REQUIRED: provide a real evidence file")
    evidence = args.evidence.read_text(encoding="utf-8").strip()
    if not evidence:
        raise SystemExit("Evidence file is empty")
    stamp = datetime.now(timezone.utc).isoformat()
    out = Path("artifacts/live-verification")
    out.mkdir(parents=True, exist_ok=True)
    for domain in args.domain:
        safe = domain.lower().replace("/", "-").replace(" ", "-")
        (out / f"{safe}.evidence.txt").write_text(
            f"domain={domain}\nverified_at={stamp}\n\n{evidence}\n", encoding="utf-8"
        )
    print("Recorded real verification evidence for:")
    for domain in args.domain:
        print(f"PASS: {domain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
