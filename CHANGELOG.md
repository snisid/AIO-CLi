Voici votre fichier **`Changelog.md`** généré et prêt à être téléchargé / visualisé. Le fichier a été ouvert directement dans l'aperçu.

### Contenu du fichier :

```markdown
# Changelog

All notable changes to MA-CLI will be documented in this file.

## [1.0.0] - 2024-01-17

### Added
- **Core Architecture**: Modular multi-agent system with NativeAgent, Planner, Coder, Tester, Debugger, Reviewer, Security, and Research agents.
- **Providers**: Full support for Ollama (local), OmniRoute, 9router, OpenAI, and Anthropic with automatic fallback.
- **Security Engine**: Path traversal protection, shell injection prevention, prompt injection defense, and sandbox isolation (Docker).
- **Permissions**: Granular permission levels (Read, Write, Execute, High Risk, Critical) with approval gates.
- **Session Management**: SQLite-based persistence with `ma-cli resume` capability.
- **Windows Support**: Native PowerShell installer (`install.ps1`) and path handling.
- **CLI Commands**: `run`, `doctor`, `agents`, `models`, `provider`, `session`, `resume`, `config`, `sandbox`, `git`.
- **Documentation**: Comprehensive guides for installation, architecture, security, and providers.

### Changed
- Renamed project to MA-CLI v1.0.0.
- Optimized dependency management (optional extras for cloud providers).

### Fixed
- Resolved timezone issues in memory engine.
- Fixed path resolution on Windows for symlink attacks.
- Corrected provider timeout handling.

### Security
- Implemented strict secret redaction in logs.
- Added circuit breakers for external providers.
- Enforced validation gates before task finalization.
```
