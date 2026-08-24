"""
MA-CLI CLI Entry Point.

This module provides the command-line interface for MA-CLI.
"""

import sys
from pathlib import Path

import click

from .. import __version__
from ..config.engine import ConfigurationEngine
from ..core.models import AgentStatus, HealthStatus
from ..events.bus import get_event_bus
from ..memory.engine import (
    create_memory_engine,
    create_session_manager,
    format_memory_summary,
    format_session_list,
)
from ..state.manager import get_state_manager
from ..supervisor.engine import get_supervisor
from ..workspace.manager import get_workspace_manager


@click.group()
@click.version_option(version=__version__, prog_name="ma-cli")
def cli():
    """MA-CLI - Multi-Agent Autonomous CLI
    
    An independent agent orchestration platform capable of planning,
    task decomposition, agent selection, model selection, and more.
    """


@cli.command()
def init():
    """Initialize a new MA-CLI project."""
    
    click.echo("Initializing MA-CLI project...")
    
    # Create .ma-cli directory
    ma_cli_dir = Path.cwd() / ".ma-cli"
    ma_cli_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    for subdir in ["state", "runs", "tasks", "workspaces", "memory", "logs", 
                   "reports", "plans", "cache", "loops"]:
        (ma_cli_dir / subdir).mkdir(exist_ok=True)
    
    # Initialize config engine
    config_engine = ConfigurationEngine()
    config = config_engine.load()
    
    click.echo(f"Created config file: {config_engine.config_path}")
    
    # Initialize state manager
    state_manager = get_state_manager()
    click.echo("Initialized state database")
    
    # Initialize workspace manager
    workspace_manager = get_workspace_manager()
    click.echo("Initialized workspace manager")
    
    click.echo("\nProject initialized successfully!")
    click.echo("Run 'ma-cli doctor' to check system status.")


@cli.command()
def setup():
    """Set up MA-CLI configuration and environment."""
    
    click.echo("Setting up MA-CLI...")
    
    # Ensure config directory exists
    config_dir = Path.home() / ".ma-cli"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Create default config
    config_engine = ConfigurationEngine()
    config = config_engine.load()
    config_engine.save(config)
    
    click.echo(f"Configuration created at: {config_engine.config_path}")
    
    # Initialize databases
    state_manager = get_state_manager()
    click.echo("State database initialized")
    
    # Show configuration summary
    click.echo("\nConfiguration Summary:")
    click.echo("-" * 40)
    click.echo(f"Default Agent: {config.runtime.default_agent}")
    click.echo(f"Default Provider: {config.runtime.default_provider}")
    click.echo(f"Autonomy Level: {config.runtime.autonomy_level.name}")
    click.echo(f"Sandbox Enabled: {config.runtime.sandbox_enabled}")
    
    click.echo("\nProviders configured:")
    for name, provider in config.providers.items():
        status = "✓" if provider.enabled else "✗"
        click.echo(f"  {status} {name}: {provider.base_url or '(no URL)'}")
    
    click.echo("\nSetup complete! Run 'ma-cli doctor' to verify.")


@cli.command()
def doctor():
    """Check system health and configuration."""
    import subprocess
    
    click.echo("MA-CLI Doctor")
    click.echo("=" * 50)
    
    issues = []
    warnings = []
    
    # Runtime check
    click.echo("\nRuntime:")
    try:
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        click.echo(f"  ✓ Python {python_version}")
    except Exception as e:
        click.echo(f"  ✗ Python check failed: {e}")
        issues.append("Python check failed")
    
    click.echo(f"  ✓ MA-CLI {__version__}")
    
    # System checks
    click.echo("\nSystem:")
    
    # Git check
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            click.echo(f"  ✓ Git {result.stdout.strip()}")
        else:
            click.echo("  ✗ Git not found")
            issues.append("Git not installed")
    except Exception as e:
        click.echo(f"  ✗ Git check failed: {e}")
        issues.append("Git check failed")
    
    # Docker check (optional)
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            click.echo(f"  ✓ Docker {result.stdout.strip()}")
        else:
            click.echo("  ⚠ Docker not installed (optional)")
            warnings.append("Docker not available for sandboxing")
    except Exception:
        click.echo("  ⚠ Docker not installed (optional)")
        warnings.append("Docker not available for sandboxing")
    
    # Provider checks
    click.echo("\nProviders:")
    
    # Ollama check
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            click.echo(f"  ✓ Ollama connected ({len(models)} models)")
        else:
            click.echo("  ⚠ Ollama not responding")
            warnings.append("Ollama service not responding")
    except Exception:
        click.echo("  ⚠ Ollama not running")
        warnings.append("Ollama not available")
    
    # OmniRoute check
    try:
        import httpx
        response = httpx.get("http://localhost:20128/v1/models", timeout=5)
        if response.status_code == 200:
            click.echo("  ✓ OmniRoute connected")
        else:
            click.echo("  ⚠ OmniRoute not responding")
            warnings.append("OmniRoute service not responding")
    except Exception:
        click.echo("  ⚠ OmniRoute not running")
        warnings.append("OmniRoute not available")
    
    # 9router check
    click.echo("  ⚠ 9router not configured")
    warnings.append("9router not configured")
    
    # Configuration check
    click.echo("\nConfiguration:")
    try:
        config_engine = ConfigurationEngine()
        config = config_engine.load()
        click.echo(f"  ✓ Config file: {config_engine.config_path}")
        
        validation_warnings = config_engine.validate()
        if validation_warnings:
            for warning in validation_warnings:
                click.echo(f"  ⚠ {warning}")
                warnings.append(warning)
        else:
            click.echo("  ✓ Configuration valid")
    except Exception as e:
        click.echo(f"  ✗ Configuration error: {e}")
        issues.append(f"Configuration error: {e}")
    
    # State check
    click.echo("\nState:")
    try:
        state_manager = get_state_manager()
        click.echo(f"  ✓ State database: {state_manager.db_path}")
    except Exception as e:
        click.echo(f"  ✗ State error: {e}")
        issues.append(f"State error: {e}")
    
    # Agent status
    click.echo("\nAgents:")
    click.echo("  ✓ NativeAgent ready")
    click.echo("  ⚠ ClaudeAgent requires API key")
    click.echo("  ⚠ CodexAgent requires API key")
    click.echo("  ⚠ QwenAgent requires configuration")
    click.echo("  ⚠ ZcodeAgent requires configuration")
    
    # Overall status
    click.echo("\n" + "=" * 50)
    
    if issues:
        click.echo("Status: ERROR")
        click.echo("\nErrors:")
        for issue in issues:
            click.echo(f"  • {issue}")
    elif warnings:
        click.echo("Status: READY (with warnings)")
        click.echo("\nWarnings:")
        for warning in warnings:
            click.echo(f"  • {warning}")
    else:
        click.echo("Status: READY")
    
    click.echo("\nNote: Warnings are normal for initial setup.")
    click.echo("Configure providers and agents to enable full functionality.")


@cli.command()
def status():
    """Show current MA-CLI status."""
    click.echo("MA-CLI Status")
    click.echo("=" * 50)
    
    # Get supervisor status
    supervisor = get_supervisor()
    status = supervisor.get_status()
    
    click.echo("\nProcesses:")
    click.echo(f"  Total: {status['total_processes']}")
    click.echo(f"  Running: {status['running']}")
    click.echo(f"  Queued: {status['queued']}")
    click.echo(f"  Completed: {status['completed']}")
    click.echo(f"  Failed: {status['failed']}")
    
    # Get system health
    health = supervisor.get_system_health()
    click.echo(f"\nMemory Used: {health.memory_used_mb:.1f} MB")
    click.echo(f"Active Processes: {health.active_processes}")
    click.echo(f"Queued Tasks: {health.queued_tasks}")
    
    # Get event bus stats
    event_bus = get_event_bus()
    stats = event_bus.get_stats()
    click.echo("\nEvent Bus:")
    click.echo(f"  Subscribers: {stats['total_subscribers']}")
    click.echo(f"  Events in History: {stats['events_in_history']}")
    
    # Get workspace info
    workspace_manager = get_workspace_manager()
    workspaces = workspace_manager.list_workspaces()
    click.echo(f"\nWorkspaces: {len(workspaces)}")
    
    current_ws = workspace_manager.current_workspace
    if current_ws:
        click.echo(f"  Current: {current_ws.name}")


@cli.group()
def agents():
    """Agent management commands."""


@agents.command("list")
def list_agents():
    """List available agents."""
    from ..agents import get_agent_registry
    
    registry = get_agent_registry()
    all_agents = registry.list_all()
    
    click.echo("Available Agents:")
    click.echo("-" * 60)
    
    for agent in all_agents:
        health_icon = "✓" if agent.health == HealthStatus.HEALTHY else "⚠"
        status_icon = "●" if agent.status == AgentStatus.IDLE else "○"
        
        cli_info_line = ""
        if hasattr(agent, 'config'):
            cli_cmd = agent.config.cli_command
            cli_info_line = f" (CLI: {cli_cmd})"
        
        click.echo(f"  {status_icon} {agent.name}{cli_info_line}")
        click.echo(f"      Provider: {agent.provider}")
        click.echo(f"      Status: {agent.status.value} {health_icon}")
        click.echo(f"      Capabilities: {', '.join(agent.capabilities)}")
        click.echo(f"      Roles: {', '.join(agent.roles)}")
        
        # Show required env vars if any
        if hasattr(agent, 'config') and agent.config.required_env_vars:
            click.echo(f"      Required Env: {', '.join(agent.config.required_env_vars)}")
        click.echo()
    
    click.echo("Note: External agents require proper CLI installation and API keys.")


@agents.command("status")
def agent_status():
    """Show detailed agent status."""
    from ..agents import get_agent_registry
    
    registry = get_agent_registry()
    all_agents = registry.list_all()
    
    click.echo("Agent Status")
    click.echo("=" * 60)
    
    for agent in all_agents:
        click.echo(f"\n{agent.name}:")
        click.echo(f"  ID: {agent.id}")
        click.echo(f"  Status: {agent.status.value}")
        click.echo(f"  Health: {agent.health.value}")
        click.echo(f"  Provider: {agent.provider}")
        
        # Get detailed info
        if hasattr(agent, 'inspect'):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            info = loop.run_until_complete(agent.inspect())
            
            if info.get('cli_exists'):
                click.echo(f"  CLI Path: {info.get('cli_path', 'N/A')}")
                click.echo(f"  CLI Version: {info.get('cli_version', 'Unknown')}")
            else:
                click.echo(f"  CLI: Not found ({info.get('error', 'Unknown error')})")
        
        click.echo(f"  Capabilities: {', '.join(agent.capabilities)}")
        click.echo(f"  Roles: {', '.join(agent.roles)}")


@cli.group()
def provider():
    """Provider management commands."""


@provider.command("list")
def list_providers():
    """List configured providers."""
    config_engine = ConfigurationEngine()
    config = config_engine.load()
    
    click.echo("Configured Providers:")
    click.echo("-" * 50)
    
    for name, provider_config in config.providers.items():
        status = "✓" if provider_config.enabled else "✗"
        click.echo(f"  {status} {name}")
        click.echo(f"      Type: {provider_config.type}")
        click.echo(f"      URL: {provider_config.base_url or '(not set)'}")
        click.echo(f"      Timeout: {provider_config.timeout}s")


@provider.command("test")
@click.argument("provider_name")
def test_provider(provider_name: str):
    """Test connectivity to a provider."""
    import httpx
    
    config_engine = ConfigurationEngine()
    config = config_engine.load()
    
    provider_config = config.providers.get(provider_name)
    if not provider_config:
        click.echo(f"Error: Provider '{provider_name}' not found")
        return
    
    click.echo(f"Testing provider: {provider_name}")
    click.echo(f"URL: {provider_config.base_url}")
    
    if not provider_config.base_url:
        click.echo("Error: No base_url configured")
        return
    
    try:
        # Try to connect
        response = httpx.get(f"{provider_config.base_url}/models", timeout=10)
        
        if response.status_code == 200:
            models = response.json().get("models", [])
            click.echo("✓ Connected successfully")
            click.echo(f"  Available models: {len(models)}")
        else:
            click.echo(f"✗ Connection failed: HTTP {response.status_code}")
    except httpx.ConnectError:
        click.echo("✗ Connection failed: Unable to connect")
    except httpx.TimeoutException:
        click.echo("✗ Connection failed: Timeout")
    except Exception as e:
        click.echo(f"✗ Connection failed: {e}")


@cli.group()
def model():
    """Model management commands."""


@model.command("list")
def list_models():
    """List available model aliases."""
    config_engine = ConfigurationEngine()
    config = config_engine.load()
    
    click.echo("Model Aliases:")
    click.echo("-" * 50)
    
    for alias, model_config in config.models.items():
        click.echo(f"  {alias}")
        click.echo(f"    Provider: {model_config.provider}")
        click.echo(f"    Model ID: {model_config.model_id or '(auto-discover)'}")
        if model_config.fallback:
            click.echo(f"    Fallback: {model_config.fallback}")
    
    click.echo("\nNote: Actual model IDs are discovered at runtime.")


@cli.command()
def config():
    """Show current configuration."""
    config_engine = ConfigurationEngine()
    config = config_engine.load()
    
    click.echo("MA-CLI Configuration")
    click.echo("=" * 50)
    click.echo(f"Config file: {config_engine.config_path}")
    click.echo("")
    
    click.echo("Runtime Settings:")
    click.echo(f"  Autonomy Level: {config.runtime.autonomy_level.name}")
    click.echo(f"  Default Agent: {config.runtime.default_agent}")
    click.echo(f"  Default Provider: {config.runtime.default_provider}")
    click.echo(f"  Sandbox Enabled: {config.runtime.sandbox_enabled}")
    click.echo(f"  Audit Logging: {config.runtime.audit_logging}")
    click.echo(f"  Max Concurrent Tasks: {config.runtime.max_concurrent_tasks}")
    
    click.echo("\nProviders:")
    for name, p in config.providers.items():
        enabled = "✓" if p.enabled else "✗"
        click.echo(f"  {enabled} {name}: {p.type}")
    
    click.echo("\nModel Aliases:")
    for alias, m in config.models.items():
        click.echo(f"  {alias} → {m.provider}")


@cli.group()
def memory():
    """Memory management commands."""


@memory.command("list")
def list_memory():
    """List memory entries."""
    memory_engine = create_memory_engine()
    summary = memory_engine.get_summary()
    
    click.echo("MA-CLI Memory Summary")
    click.echo("=" * 50)
    click.echo(format_memory_summary(summary))


@memory.command("search")
@click.argument("query")
@click.option("--limit", default=10, help="Maximum results to return")
def search_memory(query: str, limit: int):
    """Search long-term memory."""
    memory_engine = create_memory_engine()
    results = memory_engine.search_long_term(query, limit)
    
    if not results:
        click.echo(f"No memories found for: {query}")
        return
    
    click.echo(f"Search results for '{query}':")
    click.echo("-" * 50)
    
    for i, entry in enumerate(results, 1):
        click.echo(f"\n{i}. [{entry.memory_type.value}] {entry.key}")
        click.echo(f"   Content: {entry.content[:200]}...")
        click.echo(f"   Created: {entry.created_at.isoformat()}")
        click.echo(f"   Accessed: {entry.access_count} times")


@memory.command("cleanup")
@click.option("--days", default=90, help="Clean up entries older than this many days")
def cleanup_memory(days: int):
    """Clean up old memory entries."""
    memory_engine = create_memory_engine()
    deleted = memory_engine.cleanup_old_memory(days)
    
    click.echo(f"Cleaned up {deleted} memory entries older than {days} days.")


@memory.command("export")
@click.argument("output_path", type=click.Path())
@click.option("--type", "memory_type", default=None, help="Filter by memory type")
def export_memory(output_path: str, memory_type: str):
    """Export memory to JSON file."""
    
    memory_engine = create_memory_engine()
    filters = None
    if memory_type:
        filters = {"memory_type": memory_type}
    
    count = memory_engine.export_memory(Path(output_path), filters)
    click.echo(f"Exported {count} memory entries to {output_path}")


@memory.command("import")
@click.argument("input_path", type=click.Path(exists=True))
def import_memory(input_path: str):
    """Import memory from JSON file."""
    
    memory_engine = create_memory_engine()
    count = memory_engine.import_memory(Path(input_path))
    click.echo(f"Imported {count} memory entries from {input_path}")


@cli.group()
def sessions():
    """Session management commands."""


@sessions.command("list")
def list_sessions():
    """List recent sessions."""
    session_manager = create_session_manager()
    sessions = session_manager.get_recent_sessions(limit=10)
    
    click.echo("Recent Sessions")
    click.echo("=" * 50)
    click.echo(format_session_list(sessions))


@sessions.command("resume")
@click.argument("session_id")
def resume_session(session_id: str):
    """Resume a previous session."""
    session_manager = create_session_manager()
    state = session_manager.resume_session(session_id)
    
    if state is None:
        click.echo(f"Session not found: {session_id}", err=True)
        sys.exit(1)
    
    click.echo(f"Resumed session: {session_id}")
    click.echo(f"Status: {state.status}")
    click.echo(f"Request: {state.request or 'N/A'}")
    click.echo(f"Completed tasks: {len(state.completed_tasks)}")
    click.echo(f"Pending tasks: {len(state.pending_tasks)}")
    
    if state.errors:
        click.echo(f"Errors: {len(state.errors)}")


@sessions.command("show")
@click.argument("session_id")
def show_session(session_id: str):
    """Show details of a specific session."""
    session_manager = create_session_manager()
    state = session_manager.load_session(session_id)
    
    if state is None:
        click.echo(f"Session not found: {session_id}", err=True)
        sys.exit(1)
    
    click.echo(f"Session: {session_id}")
    click.echo("=" * 50)
    click.echo(f"Status: {state.status}")
    click.echo(f"Started: {state.started_at.isoformat()}")
    click.echo(f"Last Activity: {state.last_activity.isoformat()}")
    click.echo(f"Workspace: {state.workspace_path or 'N/A'}")
    click.echo(f"Request: {state.request or 'N/A'}")
    click.echo(f"Plan: {state.plan or 'N/A'}")
    click.echo("\nTasks:")
    click.echo(f"  Total: {len(state.tasks)}")
    click.echo(f"  Completed: {len(state.completed_tasks)}")
    click.echo(f"  Pending: {len(state.pending_tasks)}")
    
    if state.agent_states:
        click.echo("\nAgent States:")
        for agent, status in state.agent_states.items():
            click.echo(f"  {agent}: {status}")
    
    if state.outputs:
        click.echo(f"\nOutputs: {len(state.outputs)} items")
    
    if state.errors:
        click.echo("\nErrors:")
        for error in state.errors:
            click.echo(f"  - {error}")


@cli.group()
def loop():
    """Loop management commands."""


@loop.command("list")
def list_loops():
    """List available loops."""
    from ..loops import get_loop_engine
    
    loop_engine = get_loop_engine()
    loops = loop_engine.list_all()
    
    if not loops:
        click.echo("No loops registered.")
        return
    
    click.echo("Available Loops")
    click.echo("=" * 50)
    
    for loop_def in loops:
        status_icon = "●"
        click.echo(f"{status_icon} {loop_def.name}")
        click.echo(f"   Objective: {loop_def.objective}")
        click.echo(f"   Agents: {', '.join(loop_def.agents) if loop_def.agents else 'auto'}")
        click.echo(f"   Steps: {len(loop_def.steps)}")
        click.echo("")


@loop.command("create")
@click.argument("name")
@click.option("--objective", required=True, help="Loop objective")
@click.option("--agents", multiple=True, help="Agents to use (can be specified multiple times)")
def create_loop(name: str, objective: str, agents: tuple[str, ...]):
    """Create a new loop definition."""
    from ..loops.engine import LoopDefinition, get_loop_engine
    
    loop_engine = get_loop_engine()
    
    loop_def = LoopDefinition(
        name=name,
        objective=objective,
        agents=list(agents) if agents else [],
        steps=[]  # Steps can be added later
    )
    
    loop_engine.register_loop(loop_def)
    click.echo(f"Created loop: {name}")


@loop.command("run")
@click.argument("loop_name")
@click.option("--input", "input_data", multiple=True, help="Input data (key=value)")
def run_loop(loop_name: str, input_data: tuple[str, ...]):
    """Run a loop."""
    from ..loops.engine import get_loop_engine
    
    loop_engine = get_loop_engine()
    
    # Parse inputs
    inputs = {}
    for item in input_data:
        if "=" in item:
            key, value = item.split("=", 1)
            inputs[key] = value
    
    click.echo(f"Running loop: {loop_name}")
    click.echo(f"Inputs: {inputs or 'none'}")
    click.echo("(Loop execution will be fully implemented in Phase 13+)")


@cli.command()
@click.argument("task")
@click.option("--agent", "agent_name", default=None, help="Preferred registered agent.")
@click.option("--timeout", default=900, type=click.IntRange(1, 3600), show_default=True)
@click.option("--retries", default=1, type=click.IntRange(0, 5), show_default=True)
def run(task: str, agent_name: str | None, timeout: int, retries: int):
    """Execute a task through the MA-CLI autonomous orchestration runtime."""
    import asyncio
    from ..orchestrator import get_orchestrator
    click.echo(f"MA-CLI: {task}")
    result = asyncio.run(get_orchestrator().run(
        task, preferred_agent=agent_name, timeout=timeout, retries=retries
    ))
    if result.output:
        click.echo(result.output)
    if not result.success:
        click.echo(f"[FAIL] {result.error}", err=True)
        raise click.exceptions.Exit(1)
    click.echo(f"[PASS] agent={result.agent} attempts={result.attempts}")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
