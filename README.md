# MA-CLI

**Multi-Agent Autonomous CLI / Autonomous AI Development Runtime**

MA-CLI is an independent agent orchestration platform designed to plan work, decompose tasks, route models, execute policy-controlled tools, observe results, repair failures, and produce evidence.

It is **not** a wrapper that requires Claude Code, Codex, Qwen CLI, or another external coding CLI. External agents and providers can remain optional integrations.

## 10/10 engineering contract

A feature is complete only when it passes:

```text
IMPLEMENTED
     ↓
INTEGRATED
     ↓
TESTED
     ↓
SECURED
     ↓
DOCUMENTED
     ↓
AUTOMATED
     ↓
PRODUCTION VERIFIED
```

Mocks do not count as live verification. `TODO`, placeholders, mock-only paths, disconnected features, or documentation without executable integration do not count as completion.

See:

- `docs/QUALITY_10_10.md` — mandatory completion contract
- `docs/10_10_DOMAIN_MATRIX.md` — evidence matrix and release blockers

## Current architecture

The target native runtime is:

```text
USER
 ↓
Intent Analyzer
 ↓
Planner
 ↓
Task Graph
 ↓
Native Agent
 ↓
Coder / Tester / Research / Security
 ↓
Model Router
 ↓
Tool Engine
 ↓
Security / Sandbox
 ↓
Observer
 ↓
Diagnoser / Repair
 ↓
Validator
 ↓
Finalizer
 ↓
RESULT
```

The repository is being hardened incrementally. **The project does not claim global 10/10 until the domain matrix reaches PASS for production verification.**

## Quick Start

```bash
pip install -e ".[dev]"
ma-cli doctor
ma-cli init
ma-cli run "Build authentication with RBAC"
```

## Core capabilities

- Native agent orchestration foundation
- Provider abstraction and model routing
- Policy-controlled Tool Registry
- Workspace boundary and path traversal protection
- Explicit high-risk command approval
- Command timeout and output capture
- Tool audit evidence
- Persistent memory architecture
- Security and sandbox architecture
- Cross-platform CI on Linux and Windows
- Python 3.11–3.13 validation
- Automated dependency audit
- Fail-closed release gate

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Roadmap](docs/ROADMAP.md)
- [Security](docs/SECURITY.md)
- [Providers](docs/PROVIDERS.md)
- [Agents](docs/AGENTS.md)
- [Loops](docs/LOOPS.md)
- [Model Routing](docs/MODEL_ROUTING.md)
- [Installation](docs/INSTALLATION.md)
- [10/10 Quality Contract](docs/QUALITY_10_10.md)
- [10/10 Domain Matrix](docs/10_10_DOMAIN_MATRIX.md)

## Requirements

- Python 3.11+
- Git
- Docker (optional, for sandboxing)
- Ollama (recommended for local models)

## Release policy

A green unit-test suite is not sufficient for a 10/10 release. Production verification must cover real providers, tools, security controls, MCP, Git, browser, desktop, Windows packaging, upgrade/rollback, and clean-host E2E behavior before release approval.

## License

MIT License — See `LICENSE`.
