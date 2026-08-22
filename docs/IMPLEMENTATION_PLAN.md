# MA-CLI Implementation Plan

## Project: Multi-Agent Autonomous CLI

**Version:** 1.0.0  
**Document Type:** Implementation Plan  
**Status:** Active

---

## 1. Overview

This document outlines the phased implementation strategy for MA-CLI, an independent multi-agent software engineering platform.

### Implementation Philosophy

1. **Incremental Delivery**: Each phase produces working, testable code
2. **No Placeholders**: Every function must be implemented or explicitly marked as stub
3. **Test-Driven**: Tests accompany every feature
4. **Verification Required**: Every phase must pass validation before proceeding
5. **No Fake Features**: Never claim a feature works unless it is implemented and tested

---

## 2. Phase Breakdown

### PHASE 1: Core Foundation (CURRENT)

**Objective:** Establish project structure, core interfaces, and initial CLI

**Deliverables:**
- [x] Directory structure
- [x] Architecture documentation
- [ ] Configuration schema
- [ ] Agent interface (ABC)
- [ ] Provider interface (ABC)
- [ ] Model interface
- [ ] Loop interface
- [ ] Task model
- [ ] Event model
- [ ] State model
- [ ] Permission model
- [ ] Initial CLI entry point
- [ ] Doctor command (basic)
- [ ] Test infrastructure

**Exit Criteria:**
- `ma-cli --help` works
- `ma-cli doctor` runs and reports system status
- All tests pass
- No import errors

---

### PHASE 2: Agent Interface

**Objective:** Define universal agent abstraction

**Deliverables:**
- [ ] Agent ABC with all required properties/methods
- [ ] AgentStatus enum
- [ ] HealthStatus enum
- [ ] ExecutionResult dataclass
- [ ] AgentRegistry
- [ ] Agent health monitoring
- [ ] Unit tests for agent interface

**Exit Criteria:**
- Agent interface is type-safe
- Registry can register/list agents
- Health checks work

---

### PHASE 3: NativeAgent

**Objective:** Implement fully functional local agent

**Deliverables:**
- [ ] NativeAgent class implementing Agent interface
- [ ] Planner component
- [ ] Context Manager
- [ ] Tool Manager
- [ ] Memory integration
- [ ] File Editor tool
- [ ] Shell execution
- [ ] Git integration (basic)
- [ ] Test Runner integration
- [ ] Browser tool (Playwright)
- [ ] MCP client
- [ ] Permission Manager
- [ ] Loop Engine integration

**Exit Criteria:**
- NativeAgent can execute tasks independently
- Works with Ollama provider
- Can read/write files
- Can execute shell commands safely
- Can run tests

---

### PHASE 4: External Agent Adapters

**Objective:** Integrate external agent systems

**Deliverables:**
- [ ] ClaudeAdapter
- [ ] CodexAdapter
- [ ] QwenAdapter
- [ ] ZcodeAdapter
- [ ] OpenClawAdapter (optional)
- [ ] HermesAdapter (optional)
- [ ] Adapter factory
- [ ] Connection testing

**Exit Criteria:**
- All adapters implement Agent interface
- Connection to external agents works
- Graceful degradation when unavailable

---

### PHASE 5: Provider Engine

**Objective:** Abstract model providers

**Deliverables:**
- [ ] Provider ABC
- [ ] ProviderRegistry
- [ ] Provider configuration
- [ ] Health check mechanism
- [ ] Model discovery interface
- [ ] Chat interface normalization

**Exit Criteria:**
- Providers can be registered/configured
- Health checks report accurate status
- Model discovery works

---

### PHASE 6: Ollama Provider

**Objective:** Local model support via Ollama

**Deliverables:**
- [ ] OllamaProvider implementation
- [ ] Model discovery from Ollama
- [ ] Chat completion
- [ ] Streaming support
- [ ] Configuration options
- [ ] Error handling

**Exit Criteria:**
- Can connect to local Ollama
- Can list available models
- Can send chat requests
- Handles connection failures gracefully

---

### PHASE 7: OmniRoute Provider

**Objective:** Integrate OmniRoute gateway

**Deliverables:**
- [ ] OmniRouteProvider implementation
- [ ] Auto-discovery of endpoint
- [ ] Model enumeration
- [ ] Model alias mapping
- [ ] Fallback logic
- [ ] Installation/configuration support

**Exit Criteria:**
- Detects OmniRoute automatically
- Discovers available models
- Maps aliases correctly
- Reports unavailable models honestly

---

### PHASE 8: 9router Provider

**Objective:** Secondary gateway support

**Deliverables:**
- [ ] NineRouterProvider implementation
- [ ] Model discovery
- [ ] Chat completion
- [ ] Fallback from OmniRoute

**Exit Criteria:**
- Works as fallback provider
- Model routing functions correctly

---

### PHASE 9: Planner

**Objective:** Task planning and decomposition

**Deliverables:**
- [ ] Planner class
- [ ] Request analysis
- [ ] Task decomposition algorithm
- [ ] Dependency graph
- [ ] Resource estimation
- [ ] Timeline planning
- [ ] Plan serialization

**Exit Criteria:**
- Can break down complex requests
- Generates executable task lists
- Identifies dependencies correctly

---

### PHASE 10: Agent Router

**Objective:** Intelligent agent selection

**Deliverables:**
- [ ] AgentRouter class
- [ ] Capability matching
- [ ] Load balancing
- [ ] Health-aware routing
- [ ] Fallback strategies
- [ ] Role-based selection

**Exit Criteria:**
- Selects appropriate agent for task
- Handles agent failures
- Respects role requirements

---

### PHASE 11: Model Router

**Objective:** Intelligent model selection

**Deliverables:**
- [ ] ModelRouter class
- [ ] Model capability matching
- [ ] Cost optimization
- [ ] Latency optimization
- [ ] Provider selection
- [ ] Alias resolution
- [ ] Model verification

**Exit Criteria:**
- Selects best model for task
- Resolves aliases to actual model IDs
- Verifies model availability
- Never fakes model availability

---

### PHASE 12: Tool Engine

**Objective:** Tool execution framework

**Deliverables:**
- [ ] ToolEngine class
- [ ] Tool registry
- [ ] Tool schemas
- [ ] Permission enforcement
- [ ] Timeout management
- [ ] Result normalization
- [ ] Error handling
- [ ] Cancellation support

**Tools to Implement:**
- [ ] read_file
- [ ] write_file
- [ ] edit_file
- [ ] delete_file
- [ ] search
- [ ] glob
- [ ] shell
- [ ] powershell
- [ ] git
- [ ] test
- [ ] build
- [ ] docker
- [ ] browser
- [ ] http

**Exit Criteria:**
- All tools have schemas
- Permissions are enforced
- Timeouts work correctly
- Results are normalized

---

### PHASE 13: Loop Engine

**Objective:** Workflow execution engine

**Deliverables:**
- [ ] LoopEngine class
- [ ] Loop definition parser
- [ ] Step executor
- [ ] Success/failure criteria evaluation
- [ ] Retry policy implementation
- [ ] Approval policy implementation
- [ ] Loop state management
- [ ] Built-in loops:
  - [ ] HumanizationLoop
  - [ ] ResearchLoop
  - [ ] CodeReviewLoop
  - [ ] SecurityReviewLoop
  - [ ] DebugLoop
  - [ ] TestingLoop

**Exit Criteria:**
- Loops can be defined and executed
- Steps execute in order
- Success criteria are evaluated
- Retries work correctly

---

### PHASE 14: Supervisor

**Objective:** System monitoring and coordination

**Deliverables:**
- [ ] Supervisor class
- [ ] Process monitoring
- [ ] Health check coordinator
- [ ] Resource monitoring (CPU, memory)
- [ ] Timeout enforcement
- [ ] Error aggregation
- [ ] State tracking
- [ ] Event publishing

**Exit Criteria:**
- Monitors all agents and processes
- Detects failures promptly
- Publishes status events

---

### PHASE 15: Memory

**Objective:** Persistent memory system

**Deliverables:**
- [ ] MemoryEngine class
- [ ] SQLite backend
- [ ] PostgreSQL backend (optional)
- [ ] Conversation memory
- [ ] Project memory
- [ ] Task memory
- [ ] Search functionality
- [ ] Privacy filtering
- [ ] Retention policies

**Exit Criteria:**
- Memory persists across sessions
- Search returns relevant results
- Privacy policies are enforced

---

### PHASE 16: MCP

**Objective:** Model Context Protocol integration

**Deliverables:**
- [ ] MCPEngine class
- [ ] MCP server discovery
- [ ] Protocol handling
- [ ] Permission layer
- [ ] Tool translation
- [ ] Supported categories:
  - [ ] filesystem
  - [ ] github
  - [ ] browser
  - [ ] search
  - [ ] shell

**Exit Criteria:**
- Can connect to MCP servers
- Tools are discovered and registered
- Permissions are enforced

---

### PHASE 17: Sandbox

**Objective:** Execution isolation

**Deliverables:**
- [ ] SandboxManager class
- [ ] Docker integration
- [ ] Container lifecycle management
- [ ] Resource limits
- [ ] Network policies
- [ ] Volume mounting
- [ ] Security profiles

**Exit Criteria:**
- Commands execute in isolated containers
- Resource limits are enforced
- Network access is controlled

---

### PHASE 18: Git

**Objective:** Version control operations

**Deliverables:**
- [ ] GitEngine class
- [ ] Status
- [ ] Diff
- [ ] Branch management
- [ ] Worktree support
- [ ] Stage/unstage
- [ ] Commit (with policy)
- [ ] Rollback
- [ ] Cherry-pick
- [ ] Merge
- [ ] Patch generation

**Exit Criteria:**
- All Git operations work
- Commits respect user policy
- Worktrees provide isolation

---

### PHASE 19: Review

**Objective:** Code review system

**Deliverables:**
- [ ] ReviewEngine class
- [ ] Code review coordination
- [ ] Multi-agent review
- [ ] Quality assessment
- [ ] Fix recommendation
- [ ] Review aggregation
- [ ] Review reporting

**Exit Criteria:**
- Code is reviewed before acceptance
- Multiple agents can review
- Reviews are actionable

---

### PHASE 20: Security

**Objective:** Security controls

**Deliverables:**
- [ ] SecurityReviewEngine
- [ ] Vulnerability scanning
- [ ] Secret detection
- [ ] Policy enforcement
- [ ] Risk assessment
- [ ] PermissionEngine
- [ ] Approval gates
- [ ] AuditLogger
- [ ] SecretsManager

**Exit Criteria:**
- Secrets are detected and protected
- Dangerous operations require approval
- All actions are logged

---

### PHASE 21: TUI

**Objective:** Terminal user interface

**Deliverables:**
- [ ] TUI Engine (Textual/Rich)
- [ ] Dashboard view
- [ ] Agent status panel
- [ ] Task progress visualization
- [ ] Event stream display
- [ ] Log viewer
- [ ] Interactive commands

**Exit Criteria:**
- Real-time status dashboard works
- Agent health is visible
- Task progress is tracked visually

---

### PHASE 22: Plugins

**Objective:** Extensibility system

**Deliverables:**
- [ ] PluginEngine class
- [ ] Plugin discovery
- [ ] Lifecycle management
- [ ] Version compatibility
- [ ] Security validation
- [ ] Initial plugins:
  - [ ] Slack
  - [ ] Data
  - [ ] Figma
  - [ ] Enterprise Search
  - [ ] Google Workspace

**Exit Criteria:**
- Plugins can be installed/loaded
- Plugin API is stable
- Security validation works

---

### PHASE 23: PowerShell Installer

**Objective:** Windows installation

**Deliverables:**
- [ ] setup-ma-cli.ps1
- [ ] OS detection
- [ ] Dependency detection
- [ ] Dependency installation (safe only)
- [ ] MA-CLI installation
- [ ] Provider configuration
- [ ] OmniRoute setup
- [ ] PATH configuration
- [ ] Directory creation
- [ ] Workspace setup
- [ ] Sandbox configuration
- [ ] Doctor execution

**Exit Criteria:**
- One-command installation on Windows
- All dependencies detected
- Safe installation practices
- User consent for privileged operations

---

### PHASE 24: Integration Tests

**Objective:** End-to-end validation

**Deliverables:**
- [ ] Integration test suite
- [ ] E2E scenarios
- [ ] Performance tests
- [ ] Security tests
- [ ] Reliability tests
- [ ] CI/CD integration

**Exit Criteria:**
- All integration tests pass
- Performance meets requirements
- Security vulnerabilities identified and fixed

---

## 3. Verification Protocol

After EVERY phase:

1. **Run Tests**
   ```bash
   pytest tests/ -v
   ```

2. **Run Lint/Type Checks**
   ```bash
   ruff check .
   mypy .
   ```

3. **Run Doctor**
   ```bash
   ma-cli doctor
   ```

4. **Verify Files**
   - Check all expected files exist
   - Verify imports work
   - Check file permissions

5. **Verify Commands**
   - Test all new CLI commands
   - Verify help text
   - Test error cases

6. **Report Failures**
   - Document any failures
   - Fix before proceeding
   - Update this document

---

## 4. Risk Management

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Provider API changes | High | Abstraction layer, version pinning |
| Docker availability | Medium | Fallback to local execution |
| Memory performance | Medium | Indexing, pagination |
| Agent reliability | High | Retry logic, fallback agents |

### Schedule Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Scope creep | High | Strict phase boundaries |
| Integration complexity | Medium | Early integration testing |
| Dependency issues | Medium | Vendor isolation |

---

## 5. Quality Gates

Every phase must meet these quality standards:

1. **Code Coverage**: >80% for core modules
2. **Type Safety**: All public APIs typed
3. **Documentation**: Docstrings for all public methods
4. **Error Handling**: All exceptions caught and handled
5. **Logging**: Structured logging throughout
6. **Security**: No hardcoded secrets, proper permission checks
7. **Performance**: Reasonable response times

---

## 6. Dependencies

### Core Dependencies

```
python >= 3.11
click >= 8.0
pydantic >= 2.0
pyyaml >= 6.0
httpx >= 0.25
sqlite3 (built-in)
gitpython >= 3.1
docker >= 6.0
rich >= 13.0
textual >= 0.40
pytest >= 7.0
ruff >= 0.1
mypy >= 1.0
```

### Optional Dependencies

```
psycopg2-binary (PostgreSQL)
playwright (Browser automation)
```

---

## 7. Milestone Summary

| Phase | Name | Estimated Completion |
|-------|------|---------------------|
| 1 | Core Foundation | Week 1 |
| 2-4 | Agent System | Week 2-3 |
| 5-8 | Provider System | Week 4-5 |
| 9-11 | Planning & Routing | Week 6 |
| 12-14 | Execution | Week 7-8 |
| 15-18 | Supporting Systems | Week 9-10 |
| 19-22 | Quality & UX | Week 11-12 |
| 23-24 | Finalization | Week 13 |

---

## 8. Next Steps

**Current Phase:** Phase 1 - Core Foundation

**Immediate Tasks:**
1. Create configuration schema
2. Implement core interfaces
3. Build initial CLI
4. Implement doctor command
5. Set up test infrastructure
6. Run verification

**Next Phase:** Phase 2 - Agent Interface
