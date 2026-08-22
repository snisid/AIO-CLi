# MA-CLI Architecture

## Multi-Agent Autonomous CLI

**Version:** 1.0.0  
**Status:** Phase 1 - Core Foundation

---

## 1. Executive Summary

MA-CLI (Multi-Agent Autonomous CLI) is an independent agent orchestration platform designed to function as an "AI Software Engineering Team in a CLI". It is NOT a wrapper around existing CLIs but a complete orchestration runtime with its own core intelligence.

### Key Design Principles

1. **Independence**: MA-CLI must work without Claude Code, Codex CLI, Qwen CLI, or Zcode
2. **Native First**: NativeAgent + Ollama provides local autonomous operation
3. **Modular Architecture**: No monolithic design; everything is pluggable
4. **Security by Default**: Permission engine, sandboxing, audit logging
5. **Event-Driven**: All subsystems communicate via event bus
6. **Loop-Based Execution**: Workflows are implemented as Loops, not Skills

---

## 2. System Architecture

```
                         USER
                           │
                           ▼
                    ┌──────────────┐
                    │   MASTER CLI │
                    └──────┬───────┘
                           ▼
                       ANALYZER
                           ▼
                        PLANNER
                           ▼
                      TASK ENGINE
                           ▼
                      AGENT ROUTER
                           ▼
                      MODEL ROUTER
                           ▼
                    EXECUTION ENGINE
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
     CLAUDE              CODEX              QWEN
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                         ZCODE
                           │
                           ▼
                       SUPERVISOR
                           ▼
                       TEST ENGINE
                           ▼
                      REVIEW ENGINE
                           ▼
                    SECURITY REVIEW
                           ▼
                       FIX ENGINE
                           ▼
                       VALIDATOR
                           ▼
                       FINALIZER
                           ▼
                         REPORT
```

---

## 3. Core Subsystems

### 3.1 CLI Engine
- Command parsing and routing
- Interactive REPL mode (`ma-cli >`)
- Direct execution mode (`ma-cli run "..."`)
- Configuration management

### 3.2 TUI Engine
- Real-time status dashboard
- Agent health monitoring
- Task progress visualization
- Event streaming display

### 3.3 Orchestrator (Master)
- Overall coordination
- Lifecycle management
- Error handling and recovery
- Shutdown coordination

### 3.4 Analyzer
- Request understanding
- Intent classification
- Context extraction
- Requirement analysis

### 3.5 Planner
- Task decomposition
- Dependency mapping
- Resource estimation
- Timeline planning

### 3.6 Task Engine
- Task creation and lifecycle
- Priority management
- Queue management
- Task state persistence

### 3.7 Scheduler
- Task scheduling
- Resource allocation
- Concurrency control
- Deadline management

### 3.8 Agent Router
- Agent selection based on capabilities
- Load balancing
- Health-aware routing
- Fallback strategies

### 3.9 Model Router
- Model selection based on task requirements
- Provider abstraction
- Cost/latency optimization
- Capability matching

### 3.10 Execution Engine
- Tool execution
- Process management
- Output capture
- Error handling

### 3.11 Tool Engine
- Tool registry
- Permission enforcement
- Timeout management
- Result normalization

### 3.12 MCP Engine
- MCP server management
- Protocol handling
- Permission layer
- Tool discovery

### 3.13 Supervisor
- Process monitoring
- Health checks
- Resource monitoring
- State tracking

### 3.14 State Manager
- State persistence
- Recovery support
- Snapshot management
- Resume capability

### 3.15 Memory Engine
- Conversation memory
- Project memory
- Task memory
- Long-term memory
- Searchable storage

### 3.16 Context Engine
- Context aggregation
- Relevance scoring
- Context window management
- Privacy filtering

### 3.17 Workspace Manager
- Directory isolation
- File locking
- Worktree management
- Cleanup coordination

### 3.18 File Lock Manager
- Concurrent access prevention
- Lock acquisition/release
- Deadlock detection
- Timeout handling

### 3.19 Git Engine
- Branch management
- Worktree operations
- Diff generation
- Commit coordination
- Rollback support

### 3.20 Sandbox Manager
- Docker integration
- Isolation enforcement
- Resource limits
- Security policies

### 3.21 Test Engine
- Test execution
- Result collection
- Coverage analysis
- Failure reporting

### 3.22 Review Engine
- Code review coordination
- Multi-agent review
- Quality assessment
- Fix recommendation

### 3.23 Security Review Engine
- Vulnerability scanning
- Secret detection
- Policy enforcement
- Risk assessment

### 3.24 Debug Engine
- Error diagnosis
- Root cause analysis
- Fix suggestion
- Verification

### 3.25 Validation Engine
- Build validation
- Type checking
- Lint enforcement
- Integration testing

### 3.26 Recovery Engine
- Failure classification
- Retry logic
- Alternative strategies
- Human escalation

### 3.27 Finalizer
- Result compilation
- Report generation
- Cleanup coordination
- Handoff preparation

### 3.28 Report Engine
- Status reporting
- Metrics collection
- Audit trail
- Documentation generation

### 3.29 Permission Engine
- Permission policies
- Approval gates
- Risk assessment
- Access control

### 3.30 Secrets Manager
- Credential storage
- Encryption
- Rotation support
- Access auditing

### 3.31 Audit Logger
- Event logging
- Action tracking
- Compliance reporting
- Forensic support

### 3.32 Event Bus
- Pub/sub messaging
- Event routing
- Subscription management
- Event persistence

### 3.33 Plugin Engine
- Plugin discovery
- Lifecycle management
- Version compatibility
- Security validation

### 3.34 Loop Engine
- Loop definition
- Workflow execution
- Step coordination
- Success/failure criteria

### 3.35 Provider Gateway
- Provider abstraction
- API normalization
- Rate limiting
- Error translation

---

## 4. Agent Architecture

### 4.1 Agent Interface

All agents implement the universal Agent interface:

```python
class Agent(ABC):
    @property
    def id(self) -> str: ...
    @property
    def name(self) -> str: ...
    @property
    def provider(self) -> str: ...
    @property
    def capabilities(self) -> list[str]: ...
    @property
    def roles(self) -> list[str]: ...
    @property
    def status(self) -> AgentStatus: ...
    @property
    def health(self) -> HealthStatus: ...
    
    async def execute(self, task: Task) -> ExecutionResult: ...
    async def cancel(self) -> bool: ...
    async def inspect(self) -> AgentInspection: ...
    async def review(self, code: str) -> ReviewResult: ...
    async def report(self) -> AgentReport: ...
```

### 4.2 Supported Agents

| Agent | Priority | Status |
|-------|----------|--------|
| NativeAgent | P0 | Required |
| ClaudeAgent | P0 | Required |
| CodexAgent | P0 | Required |
| QwenAgent | P0 | Required |
| ZcodeAgent | P0 | Required |
| OpenClawAgent | P1 | Optional |
| HermesAgent | P1 | Optional |

### 4.3 Agent Adapters

```
Agent Interface
    │
    ├── NativeAdapter
    ├── ClaudeAdapter
    ├── CodexAdapter
    ├── QwenAdapter
    ├── ZcodeAdapter
    ├── OpenClawAdapter
    └── HermesAdapter
```

### 4.4 Agent Roles

- planner
- architect
- senior_engineer
- developer
- frontend_engineer
- backend_engineer
- tester
- debugger
- code_reviewer
- security_reviewer
- researcher
- documentation_writer
- data_analyst
- ui_ux_engineer
- devops_engineer
- git_manager
- validator
- finalizer

---

## 5. Provider Architecture

### 5.1 Provider Interface

```python
class Provider(ABC):
    @property
    def name(self) -> str: ...
    @property
    def type(self) -> str: ...
    @property
    def base_url(self) -> str: ...
    @property
    def enabled(self) -> bool: ...
    
    async def discover_models(self) -> list[ModelInfo]: ...
    async def chat(self, messages: list[Message], model: str) -> ChatResponse: ...
    async def health_check(self) -> HealthStatus: ...
```

### 5.2 Supported Providers

| Provider | Type | Priority |
|----------|------|----------|
| Ollama | OpenAI-compatible | P0 |
| OmniRoute | OpenAI-compatible | P0 |
| 9router | OpenAI-compatible | P0 |
| Anthropic | Anthropic API | P0 |
| OpenAI | OpenAI API | P0 |
| Google | Gemini API | P1 |
| DeepSeek | OpenAI-compatible | P1 |
| Qwen | OpenAI-compatible | P1 |

### 5.3 Provider Fallback Chain

```
Primary → OmniRoute
Fallback 1 → 9router
Fallback 2 → Ollama
Fallback 3 → Direct Provider
```

---

## 6. Model Routing

### 6.1 Model Aliases

Configurable aliases map user-friendly names to actual model IDs:

```yaml
models:
  aliases:
    claude-opus-5:
      provider: omniroute
      model_id: auto-discovered
    
    gpt-5.5:
      provider: omniroute
      model_id: auto-discovered
    
    glm-5:
      provider: 9router
      model_id: auto-discovered
    
    deepseek-v4-pro:
      provider: omniroute
      model_id: auto-discovered
    
    qwen-3.7:
      provider: ollama
      model_id: auto-discovered
```

### 6.2 Model Discovery Flow

1. Detect provider availability
2. Query available models
3. Normalize model IDs
4. Map aliases to discovered IDs
5. Report unavailable models
6. Never silently substitute

---

## 7. Loop Engine

### 7.1 Loop Definition

```python
@dataclass
class Loop:
    name: str
    objective: str
    trigger: str
    inputs: list[str]
    tools: list[str]
    agents: list[str]
    models: list[str]
    constraints: list[str]
    memory: MemoryConfig
    steps: list[LoopStep]
    success_criteria: list[str]
    failure_criteria: list[str]
    retry_policy: RetryPolicy
    approval_policy: ApprovalPolicy
    output: OutputConfig
```

### 7.2 Built-in Loops

- HumanizationLoop
- ResearchLoop
- CodeReviewLoop
- SecurityReviewLoop
- FrontendDesignLoop
- DebugLoop
- TestingLoop
- DeploymentLoop
- DocumentationLoop
- GitHubIssueLoop
- WebsiteCreationLoop

### 7.3 Skill → Loop Converter

Import external skills and convert to MA-CLI Loops:

```bash
ma-cli loop import https://github.com/example/repository.git
```

Process:
1. Clone repository
2. Inspect documentation
3. Identify instructions/tools/workflows
4. Generate Loop specification
5. Validate and sandbox
6. Register in loop registry

---

## 8. Tool Architecture

### 8.1 Native Tools

- read_file
- write_file
- edit_file
- delete_file
- search
- glob
- shell
- powershell
- git
- test
- build
- docker
- browser
- http
- filesystem
- mcp
- lsp
- ripgrep
- tree-sitter
- github_cli

### 8.2 Tool Schema

```python
@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    permission_policy: PermissionPolicy
    timeout: int
    handler: Callable
```

---

## 9. MCP Architecture

### 9.1 MCP Categories

- filesystem
- github
- browser
- search
- shell
- database
- docker
- kubernetes
- slack
- google_workspace
- figma
- enterprise_search
- memory
- apis

### 9.2 Permission Layer

MCP tools require explicit permissions:
- No unrestricted access by default
- Per-tool permission policies
- User approval for sensitive operations

---

## 10. Security Architecture

### 10.1 Security Components

- **Permission Engine**: Access control and approval gates
- **Secrets Manager**: Encrypted credential storage
- **Audit Logger**: Complete action tracking
- **Sandbox**: Docker-based isolation
- **Command Restrictions**: Dangerous command detection
- **Network Policies**: Outbound connection control
- **Path Restrictions**: Filesystem access limits

### 10.2 Approval Gates

Critical operations requiring human approval:
- Database deletion
- Production deployment
- Production modification
- Secret rotation
- Destructive filesystem operations
- Mass deletion
- Privileged Docker operations
- Unrestricted shell access
- Credential modification

### 10.3 Autonomy Levels

| Level | Description | Capabilities |
|-------|-------------|--------------|
| 0 | Observe Only | Read-only, no modifications |
| 1 | Assist | Suggestions, requires approval |
| 2 | Autonomous Development | Self-directed with guardrails |
| 3 | Supervised Autonomy | Full autonomy with oversight |

Default: Level 3

---

## 11. State Management

### 11.1 Persisted State

- Request details
- Plan and tasks
- Dependencies
- Agent states
- Model states
- Tool calls and outputs
- Errors and recoveries
- Test results
- Reviews
- Git state
- Final results

### 11.2 Resume Support

```bash
ma-cli resume <session-id>
```

Recovery from:
- Process interruption
- System crash
- Network failure
- Agent failure

---

## 12. Memory Architecture

### 12.1 Memory Types

- **Conversation Memory**: Chat history
- **Project Memory**: Project-specific knowledge
- **Task Memory**: Task context
- **Run Memory**: Execution context
- **Agent Memory**: Agent-specific state
- **Long-term Memory**: Persistent knowledge

### 12.2 Memory Backends

- SQLite (default)
- PostgreSQL (production)
- OpenViking (pluggable)

### 12.3 Requirements

- Searchable storage
- Privacy compliance
- Security policies
- Retention policies

---

## 13. Event System

### 13.1 Event Types

```
TASK_CREATED
TASK_STARTED
TASK_PROGRESS
TASK_COMPLETED
TASK_FAILED

AGENT_STARTED
AGENT_STOPPED
AGENT_FAILED

TOOL_STARTED
TOOL_COMPLETED

TEST_STARTED
TEST_FAILED
TEST_PASSED

REVIEW_STARTED
REVIEW_FAILED
REVIEW_PASSED

BUILD_FAILED
BUILD_PASSED

APPROVAL_REQUIRED

FINALIZED
```

### 13.2 Event Bus API

```python
class EventBus:
    def publish(self, event: Event) -> None: ...
    def subscribe(self, event_type: str, handler: Callable) -> Subscription: ...
    def unsubscribe(self, subscription: Subscription) -> None: ...
```

---

## 14. Directory Structure

```
ma-cli/
├── cli/                    # CLI commands and parsing
├── core/                   # Core orchestration
├── agents/                 # Agent implementations and adapters
├── providers/              # Provider implementations
├── models/                 # Model definitions and routing
├── loops/                  # Loop definitions and engine
├── tools/                  # Tool implementations
├── mcp/                    # MCP engine
├── plugins/                # Plugin system
├── memory/                 # Memory backends
├── context/                # Context management
├── workspace/              # Workspace management
├── sandbox/                # Sandboxing
├── git_engine/             # Git operations
├── review/                 # Code review
├── validation/             # Validation engine
├── security/               # Security components
├── events/                 # Event system
├── state/                  # State management
├── tui/                    # Terminal UI
├── config/                 # Configuration schemas
├── scripts/                # Installation scripts
├── tests/                  # Test suite
└── docs/                   # Documentation
```

### 14.1 Runtime Directory

```
.ma-cli/
├── state/                  # Runtime state
├── runs/                   # Run histories
├── tasks/                  # Task definitions
├── workspaces/             # Isolated workspaces
├── memory/                 # Memory databases
├── logs/                   # Log files
├── reports/                # Generated reports
├── plans/                  # Plans
├── cache/                  # Cache
└── loops/                  # Custom loops
```

---

## 15. Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Core Runtime | Python 3.11+ | Async support, rich ecosystem |
| TUI | Textual/Rich | Modern terminal UI |
| CLI | Click/Typer | Robust command framework |
| State DB | SQLite | Embedded, no setup required |
| Production DB | PostgreSQL | Scalable production backend |
| Sandboxing | Docker | Industry standard isolation |
| Git Operations | GitPython | Pythonic Git API |
| HTTP Client | httpx | Async HTTP |
| Config | PyYAML | YAML support |
| Validation | Pydantic | Type-safe validation |

---

## 16. Integration References

The following repositories serve as architectural references:

| Repository | Purpose | Integration Type |
|------------|---------|------------------|
| gstack | Infrastructure patterns | Reference |
| claude-mem | Memory patterns | Reference |
| claude-code-system-prompts | Security review | Reference |
| academic-research-skills | Research loop | Reference |
| swiftui-design-skill | Frontend design | Reference |
| superpowers | Tool patterns | Reference |
| composio | MCP patterns | Reference |
| ui-ux-pro-max-skill | UI/UX patterns | Reference |
| ECC | Comprehensive patterns | Reference |
| OpenViking | Memory backend | Pluggable |
| taste-skill | Design patterns | Reference |
| impeccable | Quality patterns | Reference |
| playwright-cli | Browser automation | Integration |
| awesome-design-md | Design resources | Reference |
| img2threejs | 3D generation | Reference |

---

## 17. Phase Implementation Strategy

### Phase 1: Core Foundation (Current)
- Directory structure
- Architecture documentation
- Core interfaces
- Initial CLI
- Doctor command
- Test infrastructure

### Phase 2: Agent Interface
- Agent ABC definition
- Agent registry
- Health monitoring

### Phase 3: NativeAgent
- Planner component
- Context manager
- Tool manager
- File editor
- Shell execution

### Phase 4: External Agent Adapters
- ClaudeAdapter
- CodexAdapter
- QwenAdapter
- ZcodeAdapter

### Phase 5: Provider Engine
- Provider ABC
- Provider registry
- Health checks

### Phase 6-8: Provider Implementations
- OllamaProvider
- OmniRouteProvider
- NineRouterProvider

### Phase 9-11: Planning and Routing
- Planner
- Agent Router
- Model Router

### Phase 12-14: Execution
- Tool Engine
- Loop Engine
- Supervisor

### Phase 15-18: Supporting Systems
- Memory
- MCP
- Sandbox
- Git

### Phase 19-22: Quality and UX
- Review
- Security
- TUI
- Plugins

### Phase 23-24: Finalization
- PowerShell Installer
- Integration Tests

---

## 18. Engineering Rules

All implementations must include:
- Type safety (where possible)
- Structured logging
- Unit tests
- Error handling
- Configuration validation
- Graceful shutdown
- Cancellation support
- Retry logic
- Timeout handling
- Security controls
- Documentation

---

## 19. Critical Design Principle

**MA-CLI must continue working even when Claude Code, Codex, Qwen CLI, or Zcode are unavailable.**

NativeAgent + Ollama must provide local autonomous operation. Cloud providers and external agents should improve MA-CLI, not control it.

**MA-CLI = MASTER ORCHESTRATOR**
