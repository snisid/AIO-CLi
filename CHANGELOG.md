# Changelog

All notable changes to MA-CLI are documented in this file.

## [1.0.0] - 2026-09-07

### Added
- Claude Code-style interactive session: `ma-cli` REPL, `-p` print mode, `-c`/`-r` resume, slash commands, tool traces, plan/ask modes, `MA.md` project memory.
- NativeAgent registered as a first-class agent with cancel/inspect/review.
- Real loop execution with retries, approval gates, and fail-closed success criteria.
- Tool engine expansions: edit_file, delete_file, search, glob, git, http_get.
- Git engine with workspace bounds and explicit approval for destructive operations.
- MCP JSON-RPC stdio client: connect, list tools, call, ping, restart, disconnect.
- Browser engine with swappable drivers (in-memory tests, Playwright when installed).
- Upgrade/rollback/repair/diagnostics manager with filesystem backups.
- Secret store with 0600 file permissions and log redaction.
- Allow-listed plugin loader and terminal dashboard (`ma-cli tui`).
- Prompt-injection inspection on the native runtime.
- CLI groups: git, mcp, browser, secrets, upgrade, plugins, sandbox, tui, review, report, observability, context.
- Review, report, observability, and context engines wired through the orchestrator validation gate.
- LICENSE (MIT), install.sh, and setup-ma-cli.ps1.

### Changed
- `ma-cli loop run` executes registered loops instead of printing a placeholder.
- `ma-cli doctor` reports agents from the live registry.
- `ma-cli sessions resume` replays a stored request through the orchestrator.
- Docker SDK is optional; sandbox remains fail-closed when unavailable.

### Security
- High-risk tools require an unforgeable in-process `RUNTIME_GRANT`; JSON `approved` flags from models are ignored.
- `run_command` executes argv lists (PowerShell `-Command` on Windows) and rejects shell metacharacters.
- Secret store encrypts values at rest (PBKDF2 + HMAC); plaintext files are migrated and never logged.
- Plugins load `PLUGIN` dict literals via AST only — source is never `exec`'d.
- Release gate stays BLOCKED while any domain is `PENDING LIVE`.
- Destructive git operations cannot run without `--approved`.
- Prompt injection patterns are blocked before native execution.

### Notes
- Production verification for live providers, Windows hosts, and real MCP/browser sessions remains PENDING LIVE. Code completeness is not a substitute for that evidence.
