# SubAgents Integration for AIO-CLI

This directory integrates the [awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) collection, providing **158+ specialized agents** across **10 categories** for AIO-CLI.

## 📚 Available Categories

| # | Category | Agents | Description |
|---|----------|--------|-------------|
| 01 | Core Development | 11 | Full-stack, backend, frontend, API design, mobile development |
| 02 | Language Specialists | 22 | Python, JavaScript, TypeScript, Rust, Go, PHP, and more |
| 03 | Infrastructure & DevOps | 14 | Cloud architecture, Kubernetes, Terraform, CI/CD |
| 04 | Quality & Security | 16 | Testing, code review, security auditing, compliance |
| 05 | Data & AI | 15 | Data engineering, ML pipelines, AI integration |
| 06 | Developer Experience | 19 | Documentation, refactoring, build systems, CLI tools |
| 07 | Specialized Domains | 17 | Game dev, blockchain, embedded systems, graphics |
| 08 | Business & Productivity | 16 | Project management, analytics, automation |
| 09 | Meta & Orchestration | 14 | Agent coordination, installation, workflow management |
| 10 | Research & Analysis | 14 | Codebase analysis, dependency mapping, technical research |

## 🚀 Usage

### List All Categories

```python
from ma_cli.agents.subagents import get_subagent_registry

registry = get_subagent_registry()
categories = registry.list_categories()

for cat_id, cat_name in categories.items():
    print(f"{cat_id}: {cat_name}")
```

### List Agents in a Category

```python
# Get all agents in Core Development category
agents = registry.list_agents(category="01-core-development")

for agent in agents:
    print(f"- {agent['id']}: {agent.get('description', 'No description')}")
```

### Search for Agents

```python
# Search by keyword
matches = registry.search_agents("python")

for agent in matches:
    print(f"{agent['category_name']} / {agent['id']}")
    print(f"  {agent.get('description', '')}")
```

### Get Agent Details

```python
# Get specific agent info
agent = registry.get_agent("01-core-development/fullstack-developer")

if agent:
    print(f"Name: {agent['name']}")
    print(f"Description: {agent['description']}")
    print(f"Model: {agent.get('model', 'N/A')}")
    print(f"Tools: {agent.get('tools', 'N/A')}")
```

### Get Agent Content

```python
# Get full agent definition
content = registry.get_agent_content("01-core-development/fullstack-developer")
print(content)
```

### Install Agent

```python
from pathlib import Path

# Install to global location
global_agents = Path.home() / ".claude" / "agents"
success = registry.install_agent(
    "01-core-development/fullstack-developer",
    global_agents
)

if success:
    print("✓ Agent installed successfully")
```

## 📋 Example: Using SubAgents with AIO-CLI

```python
from ma_cli.agents.subagents import get_subagent_registry
from ma_cli.core.supervisor import Supervisor

# Initialize registry
registry = get_subagent_registry()

# Find a suitable agent for your task
task = "Build a REST API with authentication"
matches = registry.search_agents("api")

if matches:
    # Select the best matching agent
    best_agent = matches[0]
    print(f"Using agent: {best_agent['id']}")
    
    # Load the agent's system prompt
    agent_content = registry.get_agent_content(best_agent['category'] + '/' + best_agent['id'])
    
    # Use with AIO-CLI supervisor
    supervisor = Supervisor()
    response = await supervisor.run(
        prompt=task,
        system_prompt=agent_content
    )
```

## 🔧 Integration with NativeAgent

The subagents can be integrated into the NativeAgent workflow:

```python
from ma_cli.agents.native_agent import NativeAgent
from ma_cli.agents.subagents import get_subagent_registry

registry = get_subagent_registry()

# Get a specialized agent for coding tasks
coding_agent = registry.get_agent("01-core-development/fullstack-developer")

if coding_agent:
    # Extract the system prompt from the agent file
    agent_prompt = registry.get_agent_content(coding_agent['category'] + '/' + coding_agent['id'])
    
    # Initialize NativeAgent with specialized prompt
    agent = NativeAgent(
        workspace=workspace,
        model=model,
        system_prompt=agent_prompt  # Use specialized agent knowledge
    )
```

## 📊 Statistics

- **Total Agents**: 158
- **Categories**: 10
- **Languages Supported**: 20+
- **Domains Covered**: Full-stack development, DevOps, Security, AI/ML, and more

## 🎯 Common Use Cases

### 1. Full-Stack Feature Development
```python
agent = registry.get_agent("01-core-development/fullstack-developer")
```

### 2. Language-Specific Tasks
```python
# Python specialist
python_agent = registry.get_agent("02-language-specialists/python-pro")

# TypeScript specialist  
ts_agent = registry.get_agent("02-language-specialists/typescript-expert")
```

### 3. Architecture Design
```python
architect = registry.get_agent("01-core-development/microservices-architect")
```

### 4. Security Audit
```python
security = registry.get_agent("04-quality-security/security-auditor")
```

### 5. Code Review
```python
reviewer = registry.get_agent("04-quality-security/code-reviewer")
```

## 🔄 Updating SubAgents

To update the subagents collection:

```bash
cd /workspace/awesome-claude-code-subagents
git pull origin main
```

Then re-run the agent loader if needed.

## 📝 Agent File Format

Each agent is defined in a Markdown file with YAML frontmatter:

```markdown
---
name: agent-id
description: "What this agent does"
tools: Read, Write, Edit, Bash
model: sonnet
---

Agent instructions and system prompt...
```

## ⚠️ Important Notes

1. **Agent Selection**: Choose agents based on your specific task requirements
2. **Model Compatibility**: Some agents specify preferred models (e.g., `sonnet`, `opus`)
3. **Tool Requirements**: Check which tools an agent needs before using it
4. **Customization**: Feel free to modify agent prompts for your specific use case

## 🙏 Credits

This integration is based on the excellent work by the VoltAgent team:
- Repository: https://github.com/VoltAgent/awesome-claude-code-subagents
- License: Check original repository for licensing terms

## 🤝 Contributing

To add new agents or improve existing ones, consider contributing to the upstream repository.
