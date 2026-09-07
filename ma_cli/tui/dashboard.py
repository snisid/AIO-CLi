"""Plain-text dashboard bound to live runtime objects (Rich optional)."""
from __future__ import annotations

from .. import __version__
from ..agents.adapters import get_agent_registry
from ..events.bus import get_event_bus
from ..supervisor.engine import get_supervisor
from .render import box


def render_dashboard() -> str:
    supervisor = get_supervisor()
    status = supervisor.get_status()
    health = supervisor.get_system_health()
    agents = get_agent_registry().list_all()
    events = get_event_bus().get_stats()
    agent_lines = "\n".join(
        f"{agent.name:20} {agent.status.value:8} {agent.health.value}"
        for agent in agents
    ) or "(no agents)"
    body = "\n".join([
        f"MA-CLI {__version__}",
        (
            f"processes  total={status['total_processes']} running={status['running']} "
            f"queued={status['queued']} failed={status['failed']}"
        ),
        f"memory  {health.memory_used_mb:.1f} MB",
        f"events  subscribers={events['total_subscribers']} history={events['events_in_history']}",
        "",
        agent_lines,
        "",
        "hint  ma-cli          interactive session",
        "hint  ma-cli -p TEXT  one-shot print mode",
        "hint  /help           slash commands inside the session",
    ])
    text = box("dashboard", body)
    try:
        from rich.console import Console
        from rich.panel import Panel
        console = Console(record=True, width=80)
        console.print(Panel(text, title="MA-CLI"))
        return console.export_text()
    except Exception:  # noqa: BLE001 - Rich is optional
        return text
