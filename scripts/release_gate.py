"""MA-CLI release gate.

This gate intentionally fails closed. It is not a test-count vanity metric.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TEXT = ("TODO", "FIXME", "NotImplemented", "future implementation", "placeholder", "mock-only")
EXCLUDED = {".git", ".venv", "venv", "__pycache__", "ma_cli.egg-info"}
SELF = Path(__file__).resolve()


def production_files() -> list[Path]:
    return [p for p in ROOT.rglob("*.py") if p.resolve() != SELF and not any(part in EXCLUDED for part in p.parts)]


def scan_forbidden() -> list[str]:
    failures: list[str] = []
    for path in production_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in FORBIDDEN_TEXT:
            if token.lower() in text.lower():
                failures.append(f"{path.relative_to(ROOT)} contains forbidden marker: {token}")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            failures.append(f"{path.relative_to(ROOT)} syntax error: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Pass):
                failures.append(f"{path.relative_to(ROOT)} contains production 'pass' statement at line {node.lineno}")
    return failures


def run_tests() -> tuple[int, str]:
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    failures = scan_forbidden()
    test_code, test_output = run_tests()
    if test_code != 0:
        failures.append("automated test suite failed")
    status = "PASS" if not failures else "FAIL"
    evidence = {
        "gate": "MA-CLI-10-10",
        "status": status,
        "forbidden_marker_failures": failures,
        "pytest_exit_code": test_code,
        "pytest_output": test_output[-12000:],
        "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True).stdout.strip(),
    }
    report = ROOT / ".ma-cli-release-evidence.json"
    report.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
