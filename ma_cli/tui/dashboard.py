"""Plain-text dashboard bound to live runtime objects (Rich optional)."""
from __future__ import annotations

from .. import __version__
from ..agents.adapters import get_agent_registry
from ..events.bus import get_event_bus
from ..supervisor.engine import get_supervisor


def render_dashboard() -> str:
    supervisor = get_supervisor()
    status = supervisor.get_status()
    health = supervisor.get_system_health()
    agents = get_agent_registry().list_all()
    events = get_event_bus().get_stats()
    lines = [
        f"MA-CLI {__version__} dashboard",
        "=" * 50,
        (
            f"Processes  total={status['total_processes']} running={status['running']} "
            f"queued={status['queued']} failed={status['failed']}"
        ),
        f"Memory     {health.memory_used_mb:.1f} MB",
        f"Events     subscribers={events['total_subscribers']} history={events['events_in_history']}",
        "",
        "Agents",
        "-" * 50,
    ]
    for agent in agents:
        lines.append(f"  {agent.name:20} status={agent.status.value:8} health={agent.health.value}")
    text = "\n".join(lines)
    try:
        from rich.console import Console
        from rich.panel import Panel
        console = Console(record=True, width=80)
        console.print(Panel(text, title="MA-CLI"))
        return console.export_text()
    except Exception:  # noqa: BLE001 - Rich is optional
        return text
