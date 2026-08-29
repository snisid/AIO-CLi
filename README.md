# AIO-CLI

**Autonomous Intelligent Operations CLI**

A frontier-level multi-model coding agent platform with intelligent routing, autonomous execution, and comprehensive verification capabilities.

## 🧠 Nouvelle Architecture

AIO-CLI est maintenant un **coding agent multi-modèles extrêmement puissant, performant, autonome et résilient**, capable d'utiliser dynamiquement plusieurs LLMs et plusieurs gateways/providers selon la nature de la tâche.

```
AIO-CLI KERNEL
     │
     ▼
┌────────────────────┐
│ GLOBAL TASK ROUTER │
└─────────┬──────────┘
          │
    ┌─────┼─────┬──────────┐
    ▼     ▼     ▼          ▼
CODING  RESEARCH  ARCHITECT  SECURITY
AGENT   AGENT     AGENT      AGENT
  │       │         │         │
  ▼       ▼         ▼         ▼
INTELLIGENT MODEL ROUTING
  │
  ├─ Frontier: Opus 5, Fable 5, GPT-5.6, GLM-5.3, Kimi 3
  ├─ Heavy: DeepSeek-V4-Pro, Qwen 3.8 27B
  ├─ Fast: GLM-5.3-Flash
  └─ Free: minimax-m3:free, glm-5.2:free, gemma-4:free, lfm-2.5:free
```

### Key Features

- **9 Specialized Agents**: Coding, Architect, Research, Debugging, Security, Planning, Fast, Vision, MCP
- **Intelligent Model Routing**: Capability-based selection with automatic fallback
- **Multi-Gateway Support**: Ollama (local), 9Router, OmniRoute, OpenRouter
- **Automatic Token/Quota Failover**: Bascule automatique quand les quotas sont épuisés
- **Preemptive Switching**: Anticipe l'épuisement des tokens avant l'échec
- **Circuit Breaker Pattern**: Protection contre les pannes en cascade
- **Dynamic Model Scoring**: Capability × Task_Match × Reliability / (Cost + Latency)
- **Multi-Model Code Review**: Évite qu'un modèle valide son propre code
- **PLAN → EXECUTE → VERIFY → REPAIR Loop**: Boucle de qualité robuste
- **Security Choke-Point**: Toutes les opérations sensibles passent par un point de contrôle central

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
