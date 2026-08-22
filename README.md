# MA-CLI

**Multi-Agent Autonomous CLI**

An independent agent orchestration platform capable of planning, task decomposition, agent selection, model selection, tool selection, execution, observation, supervision, and more.

## Overview

MA-CLI is NOT a simple wrapper around Claude Code, Codex, Qwen CLI, or Zcode. It is an **independent Agent Orchestration Platform** that can work with or without external agents.

### Key Features

- **NativeAgent**: Works locally with Ollama - no external dependencies required
- **Multi-Agent Support**: Claude, Codex, Qwen, Zcode, and more
- **Provider Abstraction**: Ollama, OmniRoute, 9router, Anthropic, OpenAI, etc.
- **Model Routing**: Intelligent model selection with alias resolution
- **Loop Engine**: Workflow execution with explicit success/failure criteria
- **Security First**: Permission engine, sandboxing, audit logging
- **Memory System**: Persistent, searchable memory with privacy controls

## Quick Start

```bash
# Install
pip install -e .

# Check system status
ma-cli doctor

# Initialize a project
ma-cli init

# Run a task
ma-cli run "Build authentication with RBAC"
```

## Documentation

See the `docs/` folder for detailed documentation:

- [Architecture](docs/ARCHITECTURE.md) - System architecture overview
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md) - Phase-by-phase plan
- [Roadmap](docs/ROADMAP.md) - Product roadmap
- [Security](docs/SECURITY.md) - Security architecture
- [Providers](docs/PROVIDERS.md) - Provider integration guide
- [Agents](docs/AGENTS.md) - Agent interface documentation
- [Loops](docs/LOOPS.md) - Loop engine documentation
- [Model Routing](docs/MODEL_ROUTING.md) - Model routing guide
- [Installation](docs/INSTALLATION.md) - Installation instructions

## Development Status

**Current Phase:** Phase 1 - Core Foundation

Completed:
- [x] Directory structure
- [x] Architecture documentation
- [x] Configuration schema
- [x] Agent interface (ABC)
- [x] Provider interface (ABC)
- [x] Model interface
- [x] Loop interface
- [x] Task model
- [x] Event model
- [x] State model
- [x] Permission model
- [x] Initial CLI
- [x] Doctor command
- [x] Test infrastructure

## Requirements

- Python 3.11+
- Git
- Docker (optional, for sandboxing)
- Ollama (recommended, for local models)

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please read our contributing guidelines before submitting PRs. 
