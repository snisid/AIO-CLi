"""Command-line interface for AIO-CLi."""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import click

from .. import __version__
from ..config.engine import ConfigurationEngine
from ..core.models import AgentStatus, HealthStatus
from ..events.bus import get_event_bus
from ..memory.engine import create_memory_engine, create_session_manager, format_memory_summary, format_session_list
from ..orchestrator import get_orchestrator
from ..providers import get_provider_registry
from ..state.manager import get_state_manager
from ..supervisor.engine import get_supervisor
from ..workspace.manager import get_workspace_manager


@click.group()
@click.version_option(version=__version__, prog_name="ma-cli")
def cli() -> None:
    """MA-CLI — multi-agent autonomous coding runtime."""


@cli.command()
def init() -> None:
    """Initialize the current project."""
    root = Path.cwd() / ".ma-cli"
    for name in ("state", "runs", "tasks", "workspaces", "memory", "logs", "reports", "plans", "cache", "loops"):
        (root / name).mkdir(parents=True, exist_ok=True)
    config = ConfigurationEngine().load()
    click.echo(f"Initialized {root}")
    click.echo(f"Config: {ConfigurationEngine().config_path}")
    click.echo(f"Default provider: {config.runtime.default_provider}")


@cli.command()
def setup() -> None:
    """Create or normalize user configuration."""
    engine = ConfigurationEngine()
    config = engine.load()
    engine.save(config)
    click.echo(f"Configuration ready: {engine.config_path}")


@cli.command()
def doctor() -> None:
    """Run local runtime and provider diagnostics."""
    issues: list[str] = []
    warnings: list[str] = []
    click.echo("AIO-CLi Doctor")
    click.echo("=" * 60)
    click.echo(f"Python: {sys.version.split()[0]}")
    click.echo(f"AIO-CLi: {__version__}")
    try:
        git = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        if git.returncode == 0:
            click.echo(f"Git: {git.stdout.strip()}")
        else:
            issues.append("Git is unavailable")
    except OSError as exc:
        issues.append(f"Git check failed: {exc}")
    try:
        docker = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
        click.echo(f"Docker: {docker.stdout.strip() if docker.returncode == 0 else 'unavailable'}")
        if docker.returncode != 0:
            warnings.append("Docker unavailable; container sandbox features may be disabled")
    except OSError:
        warnings.append("Docker unavailable; container sandbox features may be disabled")

    config_engine = ConfigurationEngine()
    try:
        config = config_engine.load()
        click.echo(f"Config: {config_engine.config_path}")
        for warning in config_engine.validate():
            warnings.append(warning)
        registry = get_provider_registry()
        registry.initialize(config)
        click.echo("\nProviders:")
        for provider in registry.list_all():
            state = provider.circuit_breaker.state.value
            try:
                health = asyncio.run(provider.health_check()).value
            except Exception as exc:  # noqa: BLE001
                health = "error"
                warnings.append(f"{provider.name}: {exc}")
            click.echo(f"  {provider.name}: enabled={provider.enabled} health={health} circuit={state}")
    except Exception as exc:  # noqa: BLE001
        issues.append(f"Configuration/provider failure: {exc}")

    click.echo("\nAgents:")
    try:
        from ..agents import get_agent_registry
        for agent in get_agent_registry().list_all():
            icon = "OK" if agent.health == HealthStatus.HEALTHY else "WARN"
            click.echo(f"  {icon} {agent.name} provider={agent.provider} status={agent.status.value}")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Agent registry unavailable: {exc}")

    click.echo("\nState:")
    try:
        click.echo(f"  state db: {get_state_manager().db_path}")
        click.echo("  workspace manager: OK")
    except Exception as exc:  # noqa: BLE001
        issues.append(f"State initialization failed: {exc}")

    click.echo("\n" + "=" * 60)
    if issues:
        click.echo("Status: ERROR")
        for item in issues:
            click.echo(f"  - {item}")
        raise click.exceptions.Exit(1)
    if warnings:
        click.echo("Status: READY WITH WARNINGS")
        for item in warnings:
            click.echo(f"  - {item}")
    else:
        click.echo("Status: READY")


@cli.command()
def status() -> None:
    """Show runtime status."""
    supervisor = get_supervisor()
    data = supervisor.get_status()
    click.echo("AIO-CLi Status")
    for key in ("total_processes", "running", "queued", "completed", "failed"):
        click.echo(f"{key}: {data[key]}")
    health = supervisor.get_system_health()
    click.echo(f"memory_mb: {health.memory_used_mb:.1f}")
    click.echo(f"active_processes: {health.active_processes}")
    click.echo(f"queued_tasks: {health.queued_tasks}")
    stats = get_event_bus().get_stats()
    click.echo(f"events: {stats['events_in_history']}")


@cli.group()
def agents() -> None:
    """Agent management."""


@agents.command("list")
def list_agents() -> None:
    from ..agents import get_agent_registry
    for agent in get_agent_registry().list_all():
        icon = "OK" if agent.health == HealthStatus.HEALTHY else "WARN"
        click.echo(f"{icon} {agent.name} provider={agent.provider} status={agent.status.value}")


@agents.command("status")
def agent_status() -> None:
    from ..agents import get_agent_registry
    for agent in get_agent_registry().list_all():
        click.echo(f"\n{agent.name}")
        click.echo(f"  id={agent.id}")
        click.echo(f"  status={agent.status.value}")
        click.echo(f"  health={agent.health.value}")
        click.echo(f"  provider={agent.provider}")
        click.echo(f"  capabilities={','.join(agent.capabilities)}")
        click.echo(f"  roles={','.join(agent.roles)}")


@cli.group()
def provider() -> None:
    """Provider management."""


@provider.command("list")
def list_providers() -> None:
    config = ConfigurationEngine().load()
    for name, cfg in config.providers.items():
        click.echo(f"{'OK' if cfg.enabled else 'OFF'} {name} {cfg.base_url}")


@provider.command("test")
@click.argument("provider_name")
def test_provider(provider_name: str) -> None:
    config = ConfigurationEngine().load()
    cfg = config.providers.get(provider_name)
    if cfg is None:
        raise click.ClickException(f"Provider '{provider_name}' not configured")
    registry = get_provider_registry()
    registry.initialize(config)
    instance = registry.get(provider_name)
    if instance is None:
        raise click.ClickException(f"Provider '{provider_name}' could not be instantiated")
    try:
        health = asyncio.run(instance.health_check())
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc
    click.echo(f"provider={provider_name} health={health.value} circuit={instance.circuit_breaker.state.value}")


@cli.group()
def model() -> None:
    """Model aliases."""


@model.command("list")
def list_models() -> None:
    config = ConfigurationEngine().load()
    for alias, item in config.models.items():
        click.echo(f"{alias} -> {item.provider}/{item.model_id or 'auto'}")


@cli.command("config")
def show_config() -> None:
    config = ConfigurationEngine().load()
    click.echo(f"Config: {ConfigurationEngine().config_path}")
    click.echo(f"Autonomy: {config.runtime.autonomy_level.name}")
    click.echo(f"Agent: {config.runtime.default_agent}")
    click.echo(f"Provider: {config.runtime.default_provider}")
    click.echo(f"Sandbox: {config.runtime.sandbox_enabled}")
    click.echo(f"Audit: {config.runtime.audit_logging}")


@cli.group()
def memory() -> None:
    """Memory management."""


@memory.command("list")
def list_memory() -> None:
    click.echo(format_memory_summary(create_memory_engine().get_summary()))


@memory.command("search")
@click.argument("query")
@click.option("--limit", default=10, type=click.IntRange(1, 100))
def search_memory(query: str, limit: int) -> None:
    results = create_memory_engine().search_long_term(query, limit)
    for entry in results:
        click.echo(f"{entry.key}: {entry.content[:300]}")


@memory.command("cleanup")
@click.option("--days", default=90, type=click.IntRange(1, 3650))
def cleanup_memory(days: int) -> None:
    click.echo(f"Cleaned: {create_memory_engine().cleanup_old_memory(days)}")


@cli.group()
def sessions() -> None:
    """Session management."""


@sessions.command("list")
def list_sessions() -> None:
    click.echo(format_session_list(create_session_manager().get_recent_sessions(limit=10)))


@sessions.command("resume")
@click.argument("session_id")
def resume_session(session_id: str) -> None:
    state = create_session_manager().resume_session(session_id)
    if state is None:
        raise click.ClickException(f"Session not found: {session_id}")
    click.echo(f"Resumed {session_id}: {state.status}")


@cli.group()
def loop() -> None:
    """Workflow loop management."""


@loop.command("list")
def list_loops() -> None:
    from ..loops import get_loop_engine
    for item in get_loop_engine().list_all():
        click.echo(f"{item.name}: {item.objective} ({len(item.steps)} steps)")


@loop.command("create")
@click.argument("name")
@click.option("--objective", required=True)
@click.option("--agents", multiple=True)
def create_loop(name: str, objective: str, agents: tuple[str, ...]) -> None:
    from ..loops.engine import Loop, get_loop_engine
    get_loop_engine().register(Loop(name=name, objective=objective, agents=list(agents)))
    click.echo(f"Created loop: {name}")


@loop.command("run")
@click.argument("loop_name")
@click.option("--input", "input_data", multiple=True, help="key=value")
def run_loop(loop_name: str, input_data: tuple[str, ...]) -> None:
    from ..loops import get_loop_engine
    inputs = dict(item.split("=", 1) for item in input_data if "=" in item)
    engine = get_loop_engine()
    if engine.get(loop_name) is None:
        raise click.ClickException(f"Loop '{loop_name}' not found")

    async def executor(step, state, context):
        result = await get_orchestrator().run(
            step.description or step.name,
            preferred_agent=step.agent,
            timeout=step.timeout_seconds,
            retries=0,
        )
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "agent": result.agent,
            "attempts": result.attempts,
        }

    result = asyncio.run(engine.execute(loop_name, inputs, {"step_executor": executor}))
    click.echo(f"Loop: {loop_name}")
    click.echo(f"Status: {result.state.status.value}")
    click.echo(f"Steps: {result.steps_completed}/{result.steps_total}")
    if result.outputs:
        for name, value in result.outputs.items():
            click.echo(f"[{name}] {value}")
    if not result.success:
        raise click.exceptions.Exit(1)


@cli.command("run")
@click.argument("task")
@click.option("--agent", "agent_name", default=None)
@click.option("--timeout", default=900, type=click.IntRange(1, 3600), show_default=True)
@click.option("--retries", default=1, type=click.IntRange(0, 10), show_default=True)
def run_task(task: str, agent_name: str | None, timeout: int, retries: int) -> None:
    """Execute an autonomous coding task."""
    result = asyncio.run(get_orchestrator().run(task, preferred_agent=agent_name, timeout=timeout, retries=retries))
    if result.output:
        click.echo(result.output)
    if not result.success:
        click.echo(f"[FAIL] {result.error}", err=True)
        raise click.exceptions.Exit(1)
    click.echo(f"[PASS] agent={result.agent} attempts={result.attempts}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
