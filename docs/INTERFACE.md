# MA-CLI interfaces

MA-CLI’s primary surface is a **Claude Code-style terminal session**: a REPL in the project workspace, slash commands, visible tool traces, and explicit permission prompts for high-risk tools.

This is an independent interface. It does not wrap or require Claude Code.

## Launch

```bash
ma-cli                          # interactive session in cwd
ma-cli "Add RBAC to the API"    # first turn, then stay in the REPL
ma-cli -p "Add RBAC to the API" # one-shot print mode, then exit
ma-cli -c                       # continue the latest session
ma-cli -r <session-id>          # resume a transcript
ma-cli --mode plan              # plan only; no writes or commands
```

Subcommands (`doctor`, `run`, `git`, `mcp`, …) still work.

## Session chrome

```
╭─ ● session ──────────────────────────────────────────────╮
│ MA-CLI · /path/to/project · main · no model · default    │
╰──────────────────────────────────────────────────────────╯
instructions: MA.md
  /help  /status  /mode  /review  /diff  /clear  /exit
>
```

- **default** — run the native orchestrator and show tool evidence
- **plan** — planner graph only; nothing is executed
- **ask** — read-only context assembly (no writes)

Prompt prefixes: `>` (default), `plan>`, `ask>`.

## Slash commands

| Command | Action |
|---|---|
| `/help` | List commands |
| `/status` | Session, cwd, git branch, model, mode |
| `/mode default\|plan\|ask` | Switch mode |
| `/model [id]` | Show or set a concrete model id (`auto` is refused) |
| `/clear` | Clear conversation |
| `/compact` | Summarize older turns |
| `/review` | Code + security review |
| `/diff` `/git` | Git diff / status |
| `/context` | Token-budgeted workspace context |
| `/memory` `/init` | Read or write `MA.md` project instructions |
| `/todo` `/todo add …` | Session todos |
| `/export` `/resume` | Transcript path / session id |
| `/permissions` | Always-allow list |
| `/config` `/agents` `/mcp` `/doctor` `/cost` | Runtime inspection |
| `/exit` | Leave |

`?` prints the shortcut line.

## Tool traces

Each orchestrator step is rendered as a card (Read / Write / Test / Security / …), then a `● done` or `● failed` line. High-risk tools still require `RUNTIME_GRANT`; the session does not forge approval from model JSON.

## Project memory

On start, MA-CLI loads `MA.md`, `AGENTS.md`, and `CLAUDE.md` if present (same role as Claude Code’s `CLAUDE.md`). `/init` writes a `MA.md` stub.

Transcripts live in `.ma-cli/sessions/<id>.jsonl`.

## Other surfaces

| Surface | Command | Notes |
|---|---|---|
| Status dashboard | `ma-cli tui` | Live process/agent snapshot |
| Scripted run | `ma-cli run "…"` | Orchestrator without the REPL |
| Doctor | `ma-cli doctor` | Health / config |

There is no claim that a desktop IDE plugin or Claude Code parity of every keybinding exists until it is implemented, tested, and production-verified.
