"""Additional CLI command groups wired to Git, MCP, browser, secrets, upgrade, TUI."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click


@click.group(name="git")
def git_group():
    """Workspace-bounded Git operations."""


@git_group.command("status")
def git_status():
    from ..git_engine.engine import get_git_engine
    result = get_git_engine().status()
    click.echo(result.stdout or result.stderr)
    if not result.success:
        raise click.exceptions.Exit(result.returncode or 1)


@git_group.command("diff")
@click.option("--staged", is_flag=True)
def git_diff(staged: bool):
    from ..git_engine.engine import get_git_engine
    result = get_git_engine().diff(staged=staged)
    click.echo(result.stdout or result.stderr)


@git_group.command("commit")
@click.option("--message", "-m", required=True)
@click.option("--approved", is_flag=True)
def git_commit(message: str, approved: bool):
    from ..git_engine.engine import get_git_engine
    engine = get_git_engine()
    engine.add()
    result = engine.commit(message, approved=approved)
    click.echo(result.stdout or result.stderr)
    if not result.success:
        raise click.exceptions.Exit(1)


@git_group.command("rollback")
@click.option("--hard", is_flag=True)
@click.option("--approved", is_flag=True)
def git_rollback(hard: bool, approved: bool):
    from ..git_engine.engine import get_git_engine
    result = get_git_engine().rollback(hard=hard, approved=approved)
    click.echo(result.stdout or result.stderr)
    if not result.success:
        raise click.exceptions.Exit(1)


@click.group(name="mcp")
def mcp_group():
    """MCP server lifecycle."""


@mcp_group.command("register")
@click.argument("name")
@click.argument("command")
@click.argument("args", nargs=-1)
def mcp_register(name: str, command: str, args: tuple[str, ...]):
    from ..mcp.engine import MCPServerConfig, get_mcp_engine
    get_mcp_engine().register(MCPServerConfig(name=name, command=command, args=list(args)))
    click.echo(f"Registered MCP server: {name}")


@mcp_group.command("tools")
@click.argument("name")
def mcp_tools(name: str):
    from ..mcp.engine import get_mcp_engine
    tools = asyncio.run(get_mcp_engine().list_tools(name))
    for tool in tools:
        click.echo(f"{tool.name}: {tool.description}")


@mcp_group.command("call")
@click.argument("server")
@click.argument("tool")
@click.option("--args", default="{}", help="JSON object of tool arguments")
def mcp_call(server: str, tool: str, args: str):
    from ..mcp.engine import get_mcp_engine
    payload = json.loads(args)
    result = asyncio.run(get_mcp_engine().execute(server, tool, payload))
    click.echo(json.dumps(result, indent=2))


@click.group(name="browser")
def browser_group():
    """Browser automation."""


@browser_group.command("open")
@click.argument("url")
def browser_open(url: str):
    from ..browser.engine import InMemoryDriver, get_browser_engine
    engine = get_browser_engine()
    if engine.driver is None:
        engine.driver = InMemoryDriver()
    engine.start()
    click.echo(engine.navigate(url))


@click.group(name="secrets")
def secrets_group():
    """Secret storage (file mode 0600, values never printed)."""


@secrets_group.command("set")
@click.argument("name")
@click.argument("value")
def secrets_set(name: str, value: str):
    from ..secrets.manager import get_secret_store
    get_secret_store().set(name, value)
    click.echo(f"Stored secret {name.upper().replace('-', '_')}")


@secrets_group.command("list")
def secrets_list():
    from ..secrets.manager import get_secret_store
    names = get_secret_store().list_names()
    click.echo("\n".join(names) if names else "(no secrets)")


@secrets_group.command("delete")
@click.argument("name")
def secrets_delete(name: str):
    from ..secrets.manager import get_secret_store
    get_secret_store().delete(name)
    click.echo(f"Deleted secret {name}")


@click.group(name="upgrade")
def upgrade_group():
    """Upgrade, rollback, repair, and diagnostics."""


@upgrade_group.command("status")
def upgrade_status():
    from ..upgrade.engine import get_upgrade_manager
    click.echo(json.dumps(get_upgrade_manager().diagnostics(), indent=2))


@upgrade_group.command("backup")
def upgrade_backup():
    from ..upgrade.engine import get_upgrade_manager
    record = get_upgrade_manager().backup()
    click.echo(f"backup_id={record.id} version={record.version}")


@upgrade_group.command("rollback")
@click.option("--backup-id")
def upgrade_rollback(backup_id: str | None):
    from ..upgrade.engine import get_upgrade_manager
    result = get_upgrade_manager().rollback(backup_id)
    click.echo(json.dumps(result, indent=2))


@upgrade_group.command("repair")
def upgrade_repair():
    from ..upgrade.engine import get_upgrade_manager
    click.echo(json.dumps(get_upgrade_manager().repair(), indent=2))


@click.command(name="tui")
def tui_command():
    """Render the runtime status dashboard (REPL is `ma-cli` with no args)."""
    from ..tui.dashboard import render_dashboard
    click.echo(render_dashboard())


@click.group(name="plugins")
def plugins_group():
    """Plugin discovery and validation."""


@plugins_group.command("list")
@click.option("--dir", "plugin_dir", type=click.Path(), default=None)
def plugins_list(plugin_dir: str | None):
    from ..plugins.engine import get_plugin_engine
    engine = get_plugin_engine(Path(plugin_dir) if plugin_dir else None)
    specs = engine.discover()
    if not specs:
        click.echo("No plugins discovered.")
        return
    for spec in specs:
        click.echo(f"{spec.name} v{spec.version} enabled={spec.enabled} path={spec.path}")


@click.group(name="sandbox")
def sandbox_group():
    """Sandbox diagnostics."""


@sandbox_group.command("status")
def sandbox_status():
    from ..sandbox.manager import SandboxManager
    manager = SandboxManager()
    click.echo(f"available={manager.is_available()}")
    click.echo(json.dumps(manager.get_network_policy_summary(), indent=2))
    click.echo(json.dumps(manager.get_filesystem_policy_summary(), indent=2))


@click.group(name="report")
def report_group():
    """Generate run reports."""


@report_group.command("dir")
def report_dir():
    from ..report.engine import get_report_engine
    click.echo(str(get_report_engine().output_dir))


@click.group(name="observability")
def observability_group():
    """Runtime traces and counters."""


@observability_group.command("snapshot")
def observability_snapshot():
    from ..observability.engine import get_observability
    click.echo(json.dumps(get_observability().snapshot(), indent=2, default=str))


@click.group(name="context")
def context_group():
    """Workspace context assembly."""


@context_group.command("collect")
@click.option("--query", default=None)
def context_collect(query: str | None):
    from ..context.engine import get_context_engine
    bundle = get_context_engine().collect(query=query)
    click.echo(json.dumps({"tokens": bundle.tokens, "truncated": bundle.truncated,
                           "files": [item["path"] for item in bundle.files]}, indent=2))


@click.group(name="review")
def review_group():
    """Static code and security review."""


@review_group.command("workspace")
def review_workspace():
    from ..review.engine import get_review_engine
    engine = get_review_engine()
    code = engine.review_workspace()
    security = engine.security_review()
    click.echo(json.dumps({
        "code": {"passed": code.passed, "issues": code.issues, "score": code.score},
        "security": {"passed": security.passed, "issues": security.issues, "score": security.score},
    }, indent=2))


def register_extra_commands(cli) -> None:
    for command in (git_group, mcp_group, browser_group, secrets_group, upgrade_group,
                    tui_command, plugins_group, sandbox_group, report_group,
                    observability_group, context_group, review_group):
        cli.add_command(command)
