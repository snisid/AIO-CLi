"""Run report generator. Writes evidence, never invents a production PASS."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ReportEngine:
    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.output_dir = self.workspace / ".ma-cli" / "reports"

    def render(self, result: Any) -> str:
        success = bool(getattr(result, "success", False))
        task_id = str(getattr(result, "task_id", getattr(result, "id", "unknown")))
        agent = getattr(result, "agent", None)
        error = getattr(result, "error", None)
        output = getattr(result, "output", "") or ""
        metadata = getattr(result, "metadata", {}) or {}
        status = "PASS" if success else "FAIL"
        lines = [
            "# MA-CLI Run Report",
            "",
            f"- generated_at: {datetime.now(UTC).isoformat()}",
            f"- task_id: {task_id}",
            f"- agent: {agent or 'n/a'}",
            f"- status: {status}",
            "",
            "## Output",
            "",
            "```",
            output[:8000] or "(empty)",
            "```",
            "",
        ]
        if error:
            lines.extend(["## Error", "", error, ""])
        if metadata:
            lines.extend(["## Metadata", "", "```json", json.dumps(metadata, indent=2, default=str)[:8000], "```", ""])
        lines.extend([
            "## Production verification",
            "",
            "This report is local evidence. It is not a PRODUCTION VERIFIED PASS.",
            "",
        ])
        return "\n".join(lines)

    def write(self, result: Any, name: str | None = None) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = self.output_dir / f"{name or 'run'}-{stamp}.md"
        path.write_text(self.render(result), encoding="utf-8")
        return path


def get_report_engine(workspace: Path | None = None) -> ReportEngine:
    return ReportEngine(workspace)
