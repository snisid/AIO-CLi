# MA-CLI Phase 2: Agent Integration

## Overview

Phase 2 implements the external agent adapter architecture for MA-CLI, providing a universal interface for integrating multiple agent CLIs while maintaining strict security and permission controls.

## Implementation Summary

### Files Created/Modified

#### New Files:
- `ma_cli/agents/adapters.py` - External agent adapter implementations
- `ma_cli/tests/test_agent_adapters.py` - Comprehensive test suite

#### Modified Files:
- `ma_cli/agents/__init__.py` - Updated exports
- `ma_cli/cli/main.py` - Enhanced agent commands

### Core Components

#### 1. AgentConfig Dataclass
Configuration layer for external agent CLIs that allows command names, arguments, and capabilities to be changed without modifying the orchestrator.

```python
@dataclass
class AgentConfig:
    name: str                # Agent name
    cli_command: str         # CLI executable name
    version_args: list[str]  # Arguments for version check
    health_check_args: list[str]  # Arguments for health check
    execute_args: list[str]  # Arguments for task execution
    default_timeout: int     # Default timeout in seconds
    required_env_vars: list[str]  # Required environment variables
    capabilities: list[str]  # Agent capabilities
    roles: list[str]         # Supported roles
```

#### 2. CLIInfo Dataclass
Structured information about detected CLI installations.

```python
@dataclass
class CLIInfo:
    exists: bool            # Whether CLI was found
    path: Optional[str]     # Full path to CLI
    version: Optional[str]  # Version string
    error: Optional[str]    # Error message if not found
```

#### 3. AgentResult Dataclass
Structured result from agent execution with stdout, stderr, exit code, and timing.

```python
@dataclass
class AgentResult:
    success: bool           # Execution success
    stdout: str             # Standard output
    stderr: str             # Standard error
    exit_code: int          # Process exit code
    duration_ms: int        # Execution duration
    cancelled: bool         # Was execution cancelled
    timed_out: bool         # Did execution timeout
    metadata: dict          # Additional metadata
```

#### 4. ExternalAgentBase Class
Abstract base class providing common functionality for all external agent adapters:

- **detect_cli()**: Detects CLI existence and version
- **health_check()**: Verifies agent health and connectivity
- **execute()**: Executes tasks with timeout and cancellation support
- **cancel()**: Cancels running processes
- **inspect()**: Returns detailed agent diagnostics
- **review()**: Reviews generated code
- **report()**: Generates activity reports

#### 5. Agent Implementations

| Agent | CLI Command | Required Env Vars | Capabilities |
|-------|-------------|-------------------|--------------|
| ClaudeAgent | `claude` | ANTHROPIC_API_KEY | coding, reasoning, tool_use, file_editing, shell |
| CodexAgent | `codex` | OPENAI_API_KEY | coding, reasoning, tool_use, file_editing |
| QwenAgent | `qwen` | DASHSCOPE_API_KEY | coding, reasoning, multilingual, analysis |
| ZcodeAgent | `zcode` | ZHIPU_API_KEY | coding, reasoning, glm_models |
| OpenClawAgent | `openclaw` (stub) | - | coding, reasoning |
| HermesAgent | `hermes` (stub) | - | coding, orchestration, multi_agent |

#### 6. AgentRegistry
Singleton registry for managing and discovering agents:

```python
registry = get_agent_registry()

# List all agents
all_agents = registry.list_all()

# Get by ID or name
agent = registry.get("claude_agent")
agent = registry.get_by_name("ClaudeAgent")

# Health check all
results = await registry.health_check_all()

# Get capabilities summary
summary = registry.get_capabilities_summary()
```

### Security Features

1. **Environment Variable Validation**: Agents check for required API keys before execution
2. **Process Isolation**: Each agent execution runs in a separate subprocess
3. **Timeout Enforcement**: Configurable timeouts prevent runaway processes
4. **Cancellation Support**: Processes can be terminated gracefully
5. **Permission Boundaries**: Agents don't have unrestricted host access

### CLI Commands

#### `ma-cli agents list`
Lists all available agents with status, capabilities, and requirements.

```
Available Agents:
------------------------------------------------------------
  ○ ClaudeAgent (CLI: claude)
      Provider: claudeagent
      Status: offline ⚠
      Capabilities: coding, reasoning, tool_use, file_editing, shell
      Roles: developer, architect, reviewer, planner
      Required Env: ANTHROPIC_API_KEY
```

#### `ma-cli agents status`
Shows detailed status for each agent including CLI detection results.

```
ClaudeAgent:
  ID: claude_agent
  Status: offline
  Health: unknown
  Provider: claudeagent
  CLI: Not found (Command 'claude' not found in PATH)
  Capabilities: coding, reasoning, tool_use, file_editing, shell
  Roles: developer, architect, reviewer, planner
```

## Test Results

```
======================= 97 passed, 36 warnings in 0.50s ========================
```

All tests pass including:
- AgentConfig creation and defaults
- CLIInfo handling
- AgentResult conversion
- ExternalAgentBase functionality
- Specific agent configurations
- AgentRegistry operations
- Mocked execution scenarios

## Design Principles

### 1. Adapter Pattern
Each external agent is wrapped in an adapter that conforms to the universal `Agent` interface, preventing vendor lock-in.

### 2. Configuration Over Convention
Agent behavior is defined through `AgentConfig` rather than hardcoded logic, enabling easy customization.

### 3. Fail-Safe Defaults
- Agents start OFFLINE until explicitly health-checked
- Missing CLI = immediate failure with clear error
- Missing env vars = blocked execution with informative message

### 4. Structured Results
All agent operations return structured dataclasses, not raw strings, enabling reliable parsing and error handling.

### 5. Async-First Design
All agent operations are async-native, supporting concurrent execution and proper timeout handling.

## Integration Points

### With Orchestrator
The orchestrator interacts with agents through the universal `Agent` interface, never directly with external CLIs.

### With Permission Engine
Before executing any agent command, the permission engine validates:
- Required environment variables
- Allowed paths
- Denied commands
- Resource limits

### With Event Bus
Agent lifecycle events are emitted:
- `AGENT_STARTED`
- `AGENT_STOPPED`
- `AGENT_FAILED`

### With State Manager
Agent states are persisted for recovery after interruptions.

## Next Steps (Phase 3+)

1. **NativeAgent Implementation**: Build local agent using Ollama
2. **Provider Engine**: Implement provider discovery and model routing
3. **OmniRoute Integration**: Add OmniRoute as model gateway
4. **Planner**: Implement task planning and decomposition
5. **Tool Engine**: Build native tool execution framework

## Known Limitations

1. **External CLI Dependencies**: ClaudeAgent, CodexAgent, QwenAgent, and ZcodeAgent require their respective CLIs to be installed separately
2. **Stub Agents**: OpenClawAgent and HermesAgent are interface-ready stubs awaiting actual CLI implementations
3. **No Direct API Integration**: Current implementation uses CLI wrappers; direct API integration may be added in future phases

## Migration Path

When new agent CLIs become available:

1. Create new adapter class extending `ExternalAgentBase`
2. Define `AgentConfig` with correct CLI command and args
3. Register in `AgentRegistry`
4. Update tests

No changes to orchestrator or other components required.
