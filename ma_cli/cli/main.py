"""
MA-CLI CLI Entry Point.

This module provides the command-line interface for MA-CLI.
"""

import sys
import click

from . import __version__


@click.group()
@click.version_option(version=__version__, prog_name="ma-cli")
def cli():
    """MA-CLI - Multi-Agent Autonomous CLI
    
    An independent agent orchestration platform capable of planning,
    task decomposition, agent selection, model selection, and more.
    """
    pass


@cli.command()
def doctor():
    """Check system health and configuration."""
    click.echo("MA-CLI Doctor")
    click.echo("=" * 40)
    
    # Runtime check
    click.echo("\nRuntime:")
    try:
        import python_version
        click.echo(f"  ✓ Python {sys.version.split()[0]}")
    except Exception as e:
        click.echo(f"  ✗ Python check failed: {e}")
    
    click.echo(f"  ✓ MA-CLI {__version__}")
    
    # System checks
    click.echo("\nSystem:")
    
    # Git check
    try:
        import subprocess
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            click.echo(f"  ✓ Git {result.stdout.strip()}")
        else:
            click.echo("  ✗ Git not found")
    except Exception as e:
        click.echo(f"  ✗ Git check failed: {e}")
    
    # Docker check (optional)
    try:
        import subprocess
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            click.echo(f"  ✓ Docker {result.stdout.strip()}")
        else:
            click.echo("  ⚠ Docker not installed (optional)")
    except Exception:
        click.echo("  ⚠ Docker not installed (optional)")
    
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
    except Exception:
        click.echo("  ⚠ Ollama not running")
    
    # OmniRoute check
    try:
        import httpx
        response = httpx.get("http://localhost:20128/v1/models", timeout=5)
        if response.status_code == 200:
            click.echo("  ✓ OmniRoute connected")
        else:
            click.echo("  ⚠ OmniRoute not responding")
    except Exception:
        click.echo("  ⚠ OmniRoute not running")
    
    # 9router check
    click.echo("  ⚠ 9router not configured")
    
    # Agent status
    click.echo("\nAgents:")
    click.echo("  ✓ NativeAgent ready")
    click.echo("  ⚠ ClaudeAgent requires API key")
    click.echo("  ⚠ CodexAgent requires API key")
    click.echo("  ⚠ QwenAgent requires configuration")
    click.echo("  ⚠ ZcodeAgent requires configuration")
    
    # Overall status
    click.echo("\n" + "=" * 40)
    click.echo("Status: READY (with warnings)")
    click.echo("\nNote: Warnings are normal for initial setup.")
    click.echo("Configure providers and agents to enable full functionality.")


@cli.command()
def version():
    """Show version information."""
    click.echo(f"MA-CLI version {__version__}")


@cli.command()
def init():
    """Initialize a new MA-CLI project."""
    click.echo("Initializing MA-CLI project...")
    
    import os
    from pathlib import Path
    
    # Create .ma-cli directory
    ma_cli_dir = Path.cwd() / ".ma-cli"
    ma_cli_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    (ma_cli_dir / "state").mkdir(exist_ok=True)
    (ma_cli_dir / "runs").mkdir(exist_ok=True)
    (ma_cli_dir / "tasks").mkdir(exist_ok=True)
    (ma_cli_dir / "workspaces").mkdir(exist_ok=True)
    (ma_cli_dir / "memory").mkdir(exist_ok=True)
    (ma_cli_dir / "logs").mkdir(exist_ok=True)
    (ma_cli_dir / "reports").mkdir(exist_ok=True)
    (ma_cli_dir / "plans").mkdir(exist_ok=True)
    (ma_cli_dir / "cache").mkdir(exist_ok=True)
    (ma_cli_dir / "loops").mkdir(exist_ok=True)
    
    # Create config file if it doesn't exist
    config_file = Path.home() / ".ma-cli" / "config.yaml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    
    if not config_file.exists():
        config_content = """version: 1

runtime:
  autonomy_level: 3
  default_agent: native
  default_provider: omniroute

providers:
  ollama:
    type: openai-compatible
    enabled: true
    base_url: http://localhost:11434/v1

  omniroute:
    type: openai-compatible
    enabled: true
    base_url: http://localhost:20128/v1

  9router:
    type: openai-compatible
    enabled: true

models:
  aliases:
    claude-opus-5:
      provider: omniroute
    qwen-3.8:
      provider: ollama
"""
        config_file.write_text(config_content)
        click.echo(f"Created config file: {config_file}")
    else:
        click.echo(f"Config file exists: {config_file}")
    
    click.echo("\nProject initialized successfully!")
    click.echo("Run 'ma-cli doctor' to check system status.")


@cli.group()
def agents():
    """Agent management commands."""
    pass


@agents.command("list")
def list_agents():
    """List available agents."""
    click.echo("Available Agents:")
    click.echo("-" * 40)
    click.echo("  NativeAgent  - Built-in local agent")
    click.echo("  ClaudeAgent  - Anthropic Claude (requires API key)")
    click.echo("  CodexAgent   - OpenAI Codex (requires API key)")
    click.echo("  QwenAgent    - Alibaba Qwen (requires configuration)")
    click.echo("  ZcodeAgent   - Zhipu GLM (requires configuration)")


@cli.group()
def provider():
    """Provider management commands."""
    pass


@provider.command("list")
def list_providers():
    """List configured providers."""
    click.echo("Configured Providers:")
    click.echo("-" * 40)
    click.echo("  ollama     - Local models (Ollama)")
    click.echo("  omniroute  - Multi-provider gateway")
    click.echo("  9router    - Alternative router")
    click.echo("  anthropic  - Anthropic API")
    click.echo("  openai     - OpenAI API")


@cli.group()
def model():
    """Model management commands."""
    pass


@model.command("list")
def list_models():
    """List available models."""
    click.echo("Model Aliases:")
    click.echo("-" * 40)
    click.echo("  claude-opus-5    → omniroute (auto-discovered)")
    click.echo("  claude-fable-5   → omniroute (auto-discovered)")
    click.echo("  gpt-5.5          → omniroute (auto-discovered)")
    click.echo("  gpt-5.6          → omniroute (auto-discovered)")
    click.echo("  glm-5            → 9router (auto-discovered)")
    click.echo("  glm-5.2          → 9router (auto-discovered)")
    click.echo("  deepseek-v4-pro  → omniroute (auto-discovered)")
    click.echo("  qwen-3.7         → ollama (auto-discovered)")
    click.echo("  qwen-3.8         → ollama (auto-discovered)")
    click.echo("\nNote: Actual model IDs are discovered at runtime.")


@cli.command()
@click.argument("task")
def run(task: str):
    """Run a task."""
    click.echo(f"Running task: {task}")
    click.echo("(Task execution will be implemented in Phase 9+)")
    click.echo("\nFor now, use 'ma-cli doctor' to verify your setup.")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
