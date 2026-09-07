"""Interactive coding session modeled on Claude Code's terminal interface."""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .render import assistant_text, box, header, render_evidence, shortcuts, user_bubble

GrantFn = Callable[[str, str], str]
InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

SLASH = {
    "/help": "Show slash commands",
    "/status": "Workspace, model, mode, and session id",
    "/mode": "Switch mode: default | plan | ask",
    "/model": "Show or set the attached model id",
    "/clear": "Clear conversation (keeps session)",
    "/compact": "Compress older turns into a summary",
    "/review": "Run code + security review on the workspace",
    "/diff": "Show git diff",
    "/git": "Show git status",
    "/context": "Show assembled workspace context",
    "/memory": "Show project instructions (MA.md / AGENTS.md)",
    "/init": "Write MA.md project instructions",
    "/todo": "List or add session todos: /todo add <text>",
    "/export": "Export transcript to .ma-cli/sessions/",
    "/permissions": "Show always-allow list",
    "/config": "Show runtime configuration",
    "/agents": "List registered agents",
    "/mcp": "List registered MCP servers",
    "/doctor": "Run doctor checks",
    "/cost": "Show local usage counters (not billed)",
    "/resume": "Print session id for ma-cli --resume",
    "/exit": "Leave the session",
}

PROJECT_FILES = ("MA.md", "AGENTS.md", "CLAUDE.md")


@dataclass
class Turn:
    role: str
    content: str
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionApp:
    workspace: Path
    mode: str = "default"
    model_id: str | None = None
    input_fn: InputFn | None = None
    output_fn: OutputFn | None = None
    grant_fn: GrantFn | None = None
    run_fn: Callable[[str], Any] | None = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[Turn] = field(default_factory=list)
    todos: list[dict[str, str]] = field(default_factory=list)
    always_allow: set[str] = field(default_factory=set)
    usage: dict[str, int] = field(default_factory=lambda: {"turns": 0, "tools": 0})

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace).resolve()
        self.session_dir = self.workspace / ".ma-cli" / "sessions"
        if self.mode not in {"default", "plan", "ask"}:
            self.mode = "default"

    def out(self, text: str) -> None:
        if self.output_fn is not None:
            self.output_fn(text)
        else:
            print(text)

    def prompt_str(self) -> str:
        return "plan> " if self.mode == "plan" else "ask> " if self.mode == "ask" else "> "

    def git_branch(self) -> str | None:
        try:
            from ..git_engine.engine import GitEngine
            engine = GitEngine(self.workspace)
            if not engine.available():
                return None
            return engine.current_branch()
        except Exception:  # noqa: BLE001 - missing git is a display-only gap
            return None

    def resolved_model(self) -> str | None:
        if self.model_id:
            return self.model_id
        try:
            from ..runtime.model_adapter import attach_default_model
            attached = attach_default_model()
            if attached is not None:
                self.model_id = attached.model_id
                return self.model_id
        except Exception:  # noqa: BLE001 - unattached model is valid
            return None
        return None

    def banner(self) -> str:
        text = header(str(self.workspace), self.git_branch(), self.resolved_model(), self.mode)
        memory = self.project_memory_names()
        extra = f"instructions: {', '.join(memory)}" if memory else "no MA.md / AGENTS.md yet — /init"
        return f"{text}\n{extra}\n{shortcuts()}"

    def project_memory_names(self) -> list[str]:
        return [name for name in PROJECT_FILES if (self.workspace / name).is_file()]

    def load_project_memory(self) -> str:
        parts: list[str] = []
        for name in PROJECT_FILES:
            path = self.workspace / name
            if path.is_file():
                parts.append(f"# {name}\n{path.read_text(encoding='utf-8')[:4000]}")
        return "\n\n".join(parts)

    def transcript_path(self) -> Path:
        return self.session_dir / f"{self.session_id}.jsonl"

    def persist(self, turn: Turn) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        with self.transcript_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "role": turn.role,
                "content": turn.content,
                "at": turn.at,
                "metadata": turn.metadata,
            }, default=str) + "\n")

    def load_transcript(self, session_id: str) -> None:
        self.session_id = session_id
        path = self.session_dir / f"{session_id}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"session not found: {session_id}")
        self.messages = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            self.messages.append(Turn(
                role=str(data.get("role", "user")),
                content=str(data.get("content", "")),
                at=str(data.get("at") or ""),
                metadata=data.get("metadata") or {},
            ))

    def load_latest(self) -> bool:
        if not self.session_dir.exists():
            return False
        files = sorted(self.session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return False
        self.load_transcript(files[0].stem)
        return True

    def ask_permission(self, tool: str, summary: str) -> bool:
        if tool in self.always_allow:
            return True
        if self.grant_fn is None:
            return False
        answer = (self.grant_fn(tool, summary) or "").strip().lower()
        if answer in {"a", "always"}:
            self.always_allow.add(tool)
            return True
        return answer in {"y", "yes"}

    def handle(self, line: str) -> bool:
        text = (line or "").strip()
        if not text:
            return True
        if text in {"/exit", "/quit", "exit", "quit"}:
            self.out("bye")
            return False
        if text == "?":
            self.out(shortcuts())
            return True
        if text.startswith("/"):
            self.out(self._slash(text))
            return True
        self.out(user_bubble(text))
        reply = self._turn(text)
        self.out(reply)
        return True

    def _slash(self, text: str) -> str:
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        handlers = {
            "/help": self._help,
            "/status": self._status,
            "/mode": lambda: self._set_mode(arg),
            "/model": lambda: self._set_model(arg),
            "/clear": self._clear,
            "/compact": self._compact,
            "/review": self._review,
            "/diff": self._diff,
            "/git": self._git,
            "/context": self._context,
            "/memory": lambda: self.load_project_memory() or "(no project instruction files)",
            "/init": self._init_memory,
            "/todo": lambda: self._todo(arg),
            "/export": self._export,
            "/permissions": lambda: "always allow: " + (", ".join(sorted(self.always_allow)) or "(none)"),
            "/config": self._config,
            "/agents": self._agents,
            "/mcp": self._mcp,
            "/doctor": self._doctor,
            "/cost": lambda: json.dumps(self.usage, indent=2),
            "/resume": lambda: self.session_id,
        }
        handler = handlers.get(cmd)
        if handler is None:
            return f"unknown command {cmd}. /help for the list."
        return handler()

    def _help(self) -> str:
        rows = [f"{name:14} {desc}" for name, desc in SLASH.items()]
        return box("commands", "\n".join(rows))

    def _status(self) -> str:
        return box("status", "\n".join([
            f"session  {self.session_id}",
            f"workspace  {self.workspace}",
            f"branch  {self.git_branch() or '(none)'}",
            f"model  {self.resolved_model() or '(unattached)'}",
            f"mode  {self.mode}",
            f"turns  {len(self.messages)}",
            f"todos  {len(self.todos)}",
        ]))

    def _set_mode(self, arg: str) -> str:
        if not arg:
            return f"mode is {self.mode}. Use /mode default|plan|ask"
        if arg not in {"default", "plan", "ask"}:
            return "mode must be default, plan, or ask"
        self.mode = arg
        return f"mode → {self.mode}"

    def _set_model(self, arg: str) -> str:
        if not arg:
            return self.resolved_model() or "no model attached"
        if arg == "auto":
            return "refusing model_id=auto; pass a concrete id"
        self.model_id = arg
        return f"model → {self.model_id}"

    def _clear(self) -> str:
        self.messages.clear()
        return "conversation cleared"

    def _compact(self) -> str:
        if len(self.messages) <= 4:
            return "nothing to compact"
        kept = self.messages[-4:]
        dropped = self.messages[:-4]
        summary = f"compacted {len(dropped)} earlier turns"
        self.messages = [Turn("system", summary), *kept]
        return summary

    def _review(self) -> str:
        from ..review.engine import ReviewEngine
        engine = ReviewEngine(self.workspace)
        code = engine.review_workspace()
        security = engine.security_review()
        body = [
            f"code  passed={code.passed} score={code.score:.2f}",
            *([f"  - {issue}" for issue in code.issues[:20]] or ["  (no code issues)"]),
            f"security  passed={security.passed} score={security.score:.2f}",
            *([f"  - {issue}" for issue in security.issues[:20]] or ["  (no security issues)"]),
        ]
        return box("review", "\n".join(body), ok=code.passed and security.passed)

    def _diff(self) -> str:
        from ..git_engine.engine import GitEngine
        result = GitEngine(self.workspace).diff()
        return box("git diff", result.stdout or result.stderr or "(empty)")

    def _git(self) -> str:
        from ..git_engine.engine import GitEngine
        result = GitEngine(self.workspace).status()
        return box("git status", result.stdout or result.stderr or "(empty)")

    def _context(self) -> str:
        from ..context.engine import ContextEngine
        bundle = ContextEngine(self.workspace).collect()
        names = "\n".join(item["path"] for item in bundle.files) or "(empty)"
        return box("context", f"tokens={bundle.tokens} truncated={bundle.truncated}\n{names}")

    def _init_memory(self) -> str:
        path = self.workspace / "MA.md"
        if path.exists():
            return f"{path.name} already exists"
        path.write_text(
            "# MA-CLI project instructions\n\n"
            "Describe how the agent should work in this repository.\n\n"
            "## Commands\n- Test: python -m pytest -q\n",
            encoding="utf-8",
        )
        return f"wrote {path.name}"

    def _todo(self, arg: str) -> str:
        if arg.startswith("add "):
            item = arg[4:].strip()
            if not item:
                return "todo text required"
            self.todos.append({"text": item, "status": "pending"})
            return f"todo added ({len(self.todos)})"
        if not self.todos:
            return "(no todos)"
        return "\n".join(f"- [{item['status']}] {item['text']}" for item in self.todos)

    def _export(self) -> str:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        path = self.transcript_path()
        with path.open("w", encoding="utf-8") as handle:
            for turn in self.messages:
                handle.write(json.dumps({
                    "role": turn.role,
                    "content": turn.content,
                    "at": turn.at,
                    "metadata": turn.metadata,
                }, default=str) + "\n")
        return str(path)

    def _config(self) -> str:
        from ..config.engine import ConfigurationEngine
        config = ConfigurationEngine().load()
        return box("config", "\n".join([
            f"agent  {config.runtime.default_agent}",
            f"provider  {config.runtime.default_provider}",
            f"autonomy  {config.runtime.autonomy_level.name}",
            f"sandbox  {config.runtime.sandbox_enabled}",
        ]))

    def _agents(self) -> str:
        from ..agents.adapters import get_agent_registry
        lines = [f"{agent.name:16} {agent.status.value:8} {agent.health.value}"
                 for agent in get_agent_registry().list_all()]
        return box("agents", "\n".join(lines) or "(none)")

    def _mcp(self) -> str:
        from ..mcp.engine import get_mcp_engine
        names = [cfg.name for cfg in get_mcp_engine().discover()]
        return box("mcp", ", ".join(names) or "(none registered)")

    def _doctor(self) -> str:
        from .. import __version__
        return box("doctor", f"MA-CLI {__version__}\nworkspace {self.workspace}\nmode {self.mode}")

    def _plan_only(self, prompt: str) -> str:
        from ..runtime.planner import Planner
        intent, graph = Planner().plan(prompt)
        lines = [f"intent  private={intent.private} caps={', '.join(sorted(intent.capabilities)) or '(none)'}"]
        for index, task in enumerate(graph.topological(), 1):
            lines.append(f"{index}. {task.role.value} — {task.title[:80]}")
        lines.append("plan mode: nothing was executed. /mode default to run.")
        return box("plan", "\n".join(lines))

    def _turn(self, prompt: str) -> str:
        from ..security.runtime_policy import RuntimeSecurity
        decision = RuntimeSecurity(self.workspace).inspect_prompt(prompt)
        if not decision.allowed:
            turn = Turn("assistant", decision.reason, metadata={"blocked": True})
            self.messages.append(Turn("user", prompt))
            self.messages.append(turn)
            return box("blocked", decision.reason, ok=False)
        self.messages.append(Turn("user", prompt))
        self.usage["turns"] += 1
        if self.mode == "plan":
            body = self._plan_only(prompt)
            self.messages.append(Turn("assistant", body, metadata={"mode": "plan"}))
            return body
        if self.mode == "ask":
            from ..context.engine import ContextEngine
            bundle = ContextEngine(self.workspace, max_tokens=2000).collect(query=prompt)
            body = box("ask", bundle.as_prompt()[:3000] or "(no matching context)")
            self.messages.append(Turn("assistant", body, metadata={"mode": "ask"}))
            return body
        result = self._execute(prompt)
        evidence = []
        if getattr(result, "metadata", None):
            evidence = result.metadata.get("evidence") or []
            self.usage["tools"] += sum(len(item.get("tool_calls") or []) for item in evidence)
        rendered = render_evidence(evidence)
        status = "done" if getattr(result, "success", False) else "failed"
        output = assistant_text(getattr(result, "output", "") or "")
        error = getattr(result, "error", None)
        tail = output if output else (error or "")
        body = "\n".join(part for part in (rendered, tail, f"● {status}") if part)
        self.messages.append(Turn("assistant", body, metadata={"success": getattr(result, "success", False)}))
        self.persist(self.messages[-2])
        self.persist(self.messages[-1])
        return body

    def _execute(self, prompt: str) -> Any:
        if self.run_fn is not None:
            return self.run_fn(prompt)
        import asyncio

        from ..orchestrator.engine import Orchestrator
        orchestrator = Orchestrator(workspace=self.workspace)
        return asyncio.run(orchestrator.run(prompt, allow_external_fallback=False, timeout=120))

    def repl(self) -> None:
        self.out(self.banner())
        read = self.input_fn or input
        while True:
            try:
                line = read(self.prompt_str())
            except (EOFError, KeyboardInterrupt):
                self.out("\nbye")
                return
            if self.handle(line) is False:
                return


def launch_session(
    *,
    workspace: Path | None = None,
    prompt: str | None = None,
    print_mode: bool = False,
    continue_session: bool = False,
    resume_id: str | None = None,
    mode: str = "default",
    input_fn: InputFn | None = None,
    output_fn: OutputFn | None = None,
) -> SessionApp:
    app = SessionApp(
        workspace=workspace or Path.cwd(),
        mode=mode,
        input_fn=input_fn,
        output_fn=output_fn,
    )
    if resume_id:
        app.load_transcript(resume_id)
    elif continue_session:
        app.load_latest()
    if prompt:
        app.handle(prompt)
        if print_mode:
            return app
    if print_mode:
        raise SystemExit(2)
    if input_fn is None and output_fn is None:
        app.repl()
    return app
