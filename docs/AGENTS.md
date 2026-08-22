# MA-CLI Agents Documentation

## Multi-Agent Autonomous CLI

**Version:** 1.0.0  
**Document Type:** Agent Architecture  

---

## 1. Overview

MA-CLI supports multiple AI agents through a universal interface. This document describes the agent architecture, supported agents, and integration patterns.

---

## 2. Agent Interface

All agents implement the following interface:

```python
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class AgentStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class ExecutionResult:
    success: bool
    output: str
    error: Optional[str]
    tool_calls: list
    duration_ms: int

@dataclass
class ReviewResult:
    passed: bool
    issues: list[str]
    suggestions: list[str]
    score: float

class Agent(ABC):
    """Universal Agent Interface"""
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique agent identifier"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name"""
    
    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider this agent uses"""
    
    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """List of agent capabilities"""
    
    @property
    @abstractmethod
    def roles(self) -> list[str]:
        """Roles this agent can perform"""
    
    @property
    @abstractmethod
    def status(self) -> AgentStatus:
        """Current agent status"""
    
    @property
    @abstractmethod
    def health(self) -> HealthStatus:
        """Agent health status"""
    
    @abstractmethod
    async def execute(self, task: Task) -> ExecutionResult:
        """Execute a task"""
    
    @abstractmethod
    async def cancel(self) -> bool:
        """Cancel current execution"""
    
    @abstractmethod
    async def inspect(self) -> dict:
        """Return agent inspection details"""
    
    @abstractmethod
    async def review(self, code: str) -> ReviewResult:
        """Review generated code"""
    
    @abstractmethod
    async def report(self) -> dict:
        """Generate agent activity report"""
```

---

## 3. Supported Agents

### Priority P0 (Required)

| Agent | Provider | Status | Description |
|-------|----------|--------|-------------|
| NativeAgent | Multiple | Required | Built-in agent, works locally |
| ClaudeAgent | Anthropic | Required | Claude via API or OmniRoute |
| CodexAgent | OpenAI | Required | GPT-based coding agent |
| QwenAgent | Qwen | Required | Alibaba Qwen models |
| ZcodeAgent | GLM/Zcode | Required | Zhipu GLM models |

### Priority P1 (Optional)

| Agent | Provider | Status | Description |
|-------|----------|--------|-------------|
| OpenClawAgent | Various | Optional | Open source agent framework |
| HermesAgent | Various | Optional | Hermes agent system |

---

## 4. Agent Adapters

Each external agent is integrated via an adapter pattern:

```
Agent Interface (ABC)
    │
    ├── NativeAdapter
    │   └── Direct provider integration
    │
    ├── ClaudeAdapter
    │   └── Anthropic API / OmniRoute
    │
    ├── CodexAdapter
    │   └── OpenAI API / OmniRoute
    │
    ├── QwenAdapter
    │   └── Qwen API / Ollama
    │
    ├── ZcodeAdapter
    │   └── GLM API / 9router
    │
    ├── OpenClawAdapter
    │   └── OpenClaw protocol
    │
    └── HermesAdapter
        └── Hermes protocol
```

### Adapter Responsibilities

1. **Protocol Translation**: Convert between agent-specific and MA-CLI protocols
2. **Error Handling**: Translate agent errors to MA-CLI error types
3. **Streaming**: Handle streaming responses if supported
4. **Tool Support**: Implement agent-specific tool calling
5. **Health Monitoring**: Track agent connectivity and performance

---

## 5. Agent Roles

Agents can perform different roles based on their capabilities:

| Role | Description | Required Capabilities |
|------|-------------|----------------------|
| planner | Task planning and decomposition | Reasoning, structured output |
| architect | System design | High-level reasoning, diagrams |
| senior_engineer | Complex implementation | Advanced coding, debugging |
| developer | General development | Coding, testing |
| frontend_engineer | UI/UX development | HTML/CSS/JS, design sense |
| backend_engineer | Server-side development | APIs, databases, infrastructure |
| tester | Test creation and execution | Testing frameworks, validation |
| debugger | Issue diagnosis | Debugging, analysis |
| code_reviewer | Code quality review | Code analysis, best practices |
| security_reviewer | Security auditing | Security knowledge, vulnerability detection |
| researcher | Information gathering | Search, synthesis, citation |
| documentation_writer | Technical writing | Clear communication, docs |
| data_analyst | Data analysis | Statistics, visualization |
| ui_ux_engineer | User experience design | Design principles, usability |
| devops_engineer | Infrastructure and deployment | CI/CD, containers, cloud |
| git_manager | Version control operations | Git expertise |
| validator | Final validation | Comprehensive checking |
| finalizer | Delivery preparation | Packaging, documentation |

### Role Assignment

```python
ROLE_REQUIREMENTS = {
    "planner": ["reasoning", "planning"],
    "architect": ["reasoning", "system_design"],
    "senior_engineer": ["coding", "debugging", "architecture"],
    "developer": ["coding", "testing"],
    "frontend_engineer": ["html", "css", "javascript", "design"],
    "backend_engineer": ["api", "database", "infrastructure"],
    "tester": ["testing", "validation"],
    "debugger": ["analysis", "debugging"],
    "code_reviewer": ["code_analysis", "best_practices"],
    "security_reviewer": ["security", "vulnerability_detection"],
    # ... etc
}
```

---

## 6. NativeAgent

NativeAgent is MA-CLI's built-in agent that works without external dependencies.

### Architecture

```
NativeAgent
├── Planner
│   └── Task decomposition
├── Context Manager
│   └── Conversation and project context
├── Tool Manager
│   └── Tool selection and execution
├── Memory
│   └── Short and long-term memory
├── File Editor
│   └── Read/write/edit files
├── Shell
│   └── Command execution
├── Git
│   └── Version control operations
├── Test Runner
│   └── Execute tests
├── Browser
│   └── Web automation (Playwright)
├── MCP Client
│   └── MCP tool integration
├── Permission Manager
│   └── Access control
└── Loop Engine
    └── Workflow execution
```

### NativeAgent Loop

```
REQUEST
    ↓
THINK/PLAN
    ↓
SELECT TOOL
    ↓
EXECUTE TOOL
    ↓
OBSERVE RESULT
    ↓
UPDATE STATE
    ↓
NEXT ACTION
    ↓
[repeat until complete]
    ↓
TEST
    ↓
REVIEW
    ↓
FIX (if needed)
    ↓
FINALIZE
```

### Configuration

```yaml
agents:
  native:
    enabled: true
    default_model: qwen2.5-coder:32b
    max_iterations: 50
    timeout_seconds: 300
    tools:
      - read_file
      - write_file
      - edit_file
      - shell
      - git
      - test
    permissions:
      level: standard
      require_approval_for:
        - delete_file
        - destructive_operations
```

---

## 7. External Agent Integration

### ClaudeAgent

```python
class ClaudeAdapter(Agent):
    def __init__(self, config: ClaudeConfig):
        self.config = config
        self.client = AnthropicClient(config.api_key)
        self._status = AgentStatus.IDLE
        self._health = HealthStatus.UNKNOWN
    
    @property
    def id(self) -> str:
        return "claude"
    
    @property
    def name(self) -> str:
        return "Claude"
    
    @property
    def provider(self) -> str:
        return "anthropic"
    
    @property
    def capabilities(self) -> list[str]:
        return ["coding", "reasoning", "analysis", "writing", "tool_use"]
    
    @property
    def roles(self) -> list[str]:
        return [
            "planner", "architect", "senior_engineer", 
            "developer", "code_reviewer", "security_reviewer",
            "documentation_writer", "researcher"
        ]
    
    async def execute(self, task: Task) -> ExecutionResult:
        # Implementation using Anthropic API
        pass
```

### CodexAgent

```python
class CodexAdapter(Agent):
    def __init__(self, config: CodexConfig):
        self.config = config
        self.client = OpenAIClient(config.api_key)
        self._status = AgentStatus.IDLE
    
    @property
    def id(self) -> str:
        return "codex"
    
    @property
    def name(self) -> str:
        return "Codex"
    
    @property
    def provider(self) -> str:
        return "openai"
    
    @property
    def capabilities(self) -> list[str]:
        return ["coding", "debugging", "testing", "refactoring"]
    
    @property
    def roles(self) -> list[str]:
        return [
            "developer", "backend_engineer", "frontend_engineer",
            "tester", "debugger"
        ]
```

---

## 8. Agent Selection

The Agent Router selects agents based on:

1. **Task Requirements**: What capabilities are needed?
2. **Agent Availability**: Which agents are healthy?
3. **Role Matching**: Which agents can perform the required role?
4. **Load Balancing**: Distribute work across agents
5. **Cost Considerations**: Prefer cost-effective agents when appropriate
6. **User Preferences**: Respect user's agent preferences

### Selection Algorithm

```python
async def select_agent(task: Task) -> Agent:
    # Get required capabilities
    required_caps = task.required_capabilities
    required_role = task.role
    
    # Filter available agents
    candidates = []
    for agent in registry.get_available_agents():
        if agent.health != HealthStatus.HEALTHY:
            continue
        if required_role and required_role not in agent.roles:
            continue
        if not all(cap in agent.capabilities for cap in required_caps):
            continue
        candidates.append(agent)
    
    if not candidates:
        raise NoAvailableAgentError("No agents match requirements")
    
    # Score candidates
    scored = []
    for agent in candidates:
        score = await calculate_agent_score(agent, task)
        scored.append((score, agent))
    
    # Select best candidate
    scored.sort(reverse=True)
    return scored[0][1]
```

---

## 9. Agent Health Monitoring

Agents are continuously monitored:

```python
class AgentHealthMonitor:
    def __init__(self):
        self.check_interval = 30  # seconds
        self.failure_threshold = 3
        self.recovery_threshold = 2
    
    async def monitor(self, agent: Agent):
        failures = 0
        successes = 0
        
        while True:
            try:
                health = await agent.health_check()
                if health.healthy:
                    successes += 1
                    failures = 0
                else:
                    failures += 1
                
                if failures >= self.failure_threshold:
                    agent.status = AgentStatus.ERROR
                    agent.health = HealthStatus.UNHEALTHY
                elif successes >= self.recovery_threshold:
                    agent.status = AgentStatus.IDLE
                    agent.health = HealthStatus.HEALTHY
                
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                failures += 1
                logger.error(f"Health check failed for {agent.id}: {e}")
```

---

## 10. Agent Registry

Central registry for all agents:

```python
class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, Agent] = {}
        self._lock = asyncio.Lock()
    
    async def register(self, agent: Agent):
        async with self._lock:
            self._agents[agent.id] = agent
    
    async def unregister(self, agent_id: str):
        async with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
    
    def get(self, agent_id: str) -> Optional[Agent]:
        return self._agents.get(agent_id)
    
    def list_all(self) -> list[Agent]:
        return list(self._agents.values())
    
    def get_available(self) -> list[Agent]:
        return [
            a for a in self._agents.values()
            if a.health == HealthStatus.HEALTHY
        ]
    
    def get_by_role(self, role: str) -> list[Agent]:
        return [
            a for a in self._agents.values()
            if role in a.roles and a.health == HealthStatus.HEALTHY
        ]
```

---

## 11. Multi-Agent Collaboration

MA-CLI supports multi-agent workflows:

### Parallel Review

```
Implementation
    ↓
┌─────────────┬─────────────┬─────────────┐
│  Claude     │   Qwen      │   Codex     │
│  Review     │   Review    │   Review    │
└─────────────┴─────────────┴─────────────┘
    ↓
Aggregator
    ↓
Consolidated Feedback
```

### Sequential Pipeline

```
Planner → Architect → Developer → Tester → Reviewer → Finalizer
```

### Fallback Chain

```
Primary Agent (Claude)
    ↓ (if fails)
Secondary Agent (Codex)
    ↓ (if fails)
Tertiary Agent (Qwen)
    ↓ (if fails)
NativeAgent (local)
```

---

## 12. Best Practices

### Agent Selection

1. Match agent capabilities to task requirements
2. Consider cost vs. quality tradeoffs
3. Use specialized agents for specialized tasks
4. Have fallback agents configured

### Error Handling

1. Always handle agent failures gracefully
2. Implement retry logic with backoff
3. Log detailed error information
4. Provide clear error messages to users

### Performance

1. Cache agent responses when appropriate
2. Use streaming for long outputs
3. Set reasonable timeouts
4. Monitor agent latency

### Security

1. Never expose agent API keys in logs
2. Validate all agent outputs
3. Sanitize inputs before sending to agents
4. Implement rate limiting

---

**Document Owner:** MA-CLI Core Team  
**Last Updated:** Phase 1 Initiation
