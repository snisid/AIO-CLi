# MA-CLI Roadmap

## Multi-Agent Autonomous CLI

**Version:** 1.0.0  
**Document Type:** Product Roadmap  
**Last Updated:** Phase 1 Initiation

---

## Vision

MA-CLI will become the definitive **independent multi-agent software engineering platform** - an "AI Software Engineering Team in a CLI" that operates autonomously while maintaining security, quality, and user control.

---

## Strategic Pillars

### 1. Independence
MA-CLI must function without reliance on any single external agent or provider. NativeAgent + Ollama provides baseline autonomous operation.

### 2. Security First
Every action is permissioned, audited, and sandboxed. Dangerous operations require human approval.

### 3. Quality Assurance
All code is tested, reviewed, and validated before acceptance. Multi-agent review ensures quality.

### 4. Extensibility
Plugin system, Loop definitions, and MCP integration enable unlimited capabilities.

### 5. Transparency
Full audit logs, state persistence, and resume capability ensure users always know what happened.

---

## Version Roadmap

### v0.1.0 - Foundation (Current)

**Theme:** Core Infrastructure

**Features:**
- Project structure
- Core interfaces (Agent, Provider, Model, Loop)
- Configuration system
- Basic CLI
- Doctor command
- Test infrastructure

**Timeline:** Week 1

---

### v0.2.0 - Agent System

**Theme:** Universal Agent Abstraction

**Features:**
- Agent interface (ABC)
- Agent registry
- NativeAgent implementation
- Claude/Codex/Qwen/Zcode adapters
- Health monitoring

**Timeline:** Weeks 2-3

---

### v0.3.0 - Provider System

**Theme:** Model Provider Integration

**Features:**
- Provider abstraction
- Ollama provider
- OmniRoute provider
- 9router provider
- Model discovery
- Alias resolution

**Timeline:** Weeks 4-5

---

### v0.4.0 - Planning & Routing

**Theme:** Intelligent Orchestration

**Features:**
- Request analyzer
- Task planner
- Agent router
- Model router
- Capability matching

**Timeline:** Week 6

---

### v0.5.0 - Execution Engine

**Theme:** Tool & Loop Execution

**Features:**
- Tool engine
- Built-in tools (file, shell, git, etc.)
- Loop engine
- Built-in loops
- Permission enforcement

**Timeline:** Weeks 7-8

---

### v0.6.0 - Supporting Systems

**Theme:** Infrastructure Services

**Features:**
- Memory system
- MCP integration
- Sandbox manager
- Git engine
- State management

**Timeline:** Weeks 9-10

---

### v0.7.0 - Quality & Review

**Theme:** Code Quality Assurance

**Features:**
- Review engine
- Security review
- Test engine
- Validation engine
- Debug engine

**Timeline:** Week 11

---

### v0.8.0 - User Experience

**Theme:** Terminal Interface & Plugins

**Features:**
- TUI dashboard
- Plugin system
- Initial plugins
- Enhanced CLI commands

**Timeline:** Week 12

---

### v0.9.0 - Installation & Deployment

**Theme:** Production Readiness

**Features:**
- PowerShell installer
- Docker setup
- Configuration wizard
- Documentation

**Timeline:** Week 13

---

### v1.0.0 - General Availability

**Theme:** Production Release

**Features:**
- All core features complete
- Integration tests passing
- Documentation complete
- Security audit passed

**Timeline:** Week 14

---

## Feature Categories

### Core Features (v1.0)

| Feature | Priority | Status |
|---------|----------|--------|
| NativeAgent | P0 | Planned |
| External Agents | P0 | Planned |
| Provider System | P0 | Planned |
| Planning System | P0 | Planned |
| Tool Engine | P0 | Planned |
| Loop Engine | P0 | Planned |
| Memory System | P0 | Planned |
| Security System | P0 | Planned |
| Review System | P0 | Planned |
| Git Integration | P0 | Planned |

### Enhanced Features (v1.1+)

| Feature | Priority | Status |
|---------|----------|--------|
| Advanced TUI | P1 | Future |
| Plugin Ecosystem | P1 | Future |
| PostgreSQL Backend | P1 | Future |
| Advanced Sandboxing | P1 | Future |
| Multi-workspace | P1 | Future |

### Future Features (v2.0+)

| Feature | Priority | Status |
|---------|----------|--------|
| Distributed Agents | P2 | Research |
| Custom Model Training | P2 | Research |
| Enterprise SSO | P2 | Research |
| Advanced Analytics | P2 | Research |

---

## Technical Milestones

### M1: Core Interfaces Complete
- Agent ABC
- Provider ABC
- Model interface
- Loop interface
- Event system

### M2: NativeAgent Operational
- Can execute tasks independently
- Works with Ollama
- File operations work
- Shell execution works

### M3: Provider Discovery Working
- Auto-detect providers
- Discover models
- Map aliases
- Report availability honestly

### M4: Planning System Functional
- Analyze requests
- Decompose tasks
- Route to agents
- Execute plans

### M5: Quality Pipeline Complete
- Tests run automatically
- Code review happens
- Security checks pass
- Validation completes

### M6: Production Ready
- Installer works
- All tests pass
- Documentation complete
- Security audit passed

---

## Success Metrics

### Technical Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test Coverage | >80% | pytest-cov |
| Type Safety | 100% public API | mypy |
| Build Time | <30s | CI pipeline |
| Startup Time | <2s | Benchmark |
| Memory Usage | <500MB baseline | Monitoring |

### User Experience Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Command Success Rate | >95% | Telemetry |
| Error Recovery Rate | >80% | Logs |
| User Satisfaction | >4.0/5.0 | Surveys |

### Reliability Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Uptime | >99% | Monitoring |
| MTTR | <5 min | Incident logs |
| Crash Rate | <0.1% | Error tracking |

---

## Risk Register

### High Priority Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Provider API changes | High | Medium | Abstraction layer |
| Security vulnerabilities | Critical | Low | Regular audits |
| Performance degradation | Medium | Medium | Load testing |

### Medium Priority Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Dependency conflicts | Medium | Medium | Vendor isolation |
| Platform compatibility | Medium | Medium | Cross-platform testing |
| User adoption | Medium | Unknown | Documentation, UX focus |

---

## Community & Ecosystem

### Open Source Strategy

- Core: Open source (MIT/Apache 2.0)
- Plugins: Community contributions welcome
- Reference implementations: Public
- Security patches: Rapid response

### Integration Partners

| Partner | Integration Type | Status |
|---------|-----------------|--------|
| Ollama | Provider | Planned |
| OmniRoute | Provider | Planned |
| Composio | MCP patterns | Reference |
| Playwright | Browser automation | Integration |
| OpenViking | Memory backend | Pluggable |

---

## Release Cadence

### Major Releases (vX.0.0)
- New features
- Breaking changes possible
- Quarterly target

### Minor Releases (vX.Y.0)
- Feature enhancements
- Backward compatible
- Monthly target

### Patch Releases (vX.Y.Z)
- Bug fixes
- Security patches
- As needed

---

## Governance

### Decision Making

- Architecture decisions: Lead Architect
- Feature priorities: Product team
- Security issues: Security team
- Community contributions: Maintainers

### Contribution Guidelines

1. Fork and branch
2. Implement feature/fix
3. Write tests
4. Submit PR
5. Code review
6. Merge

---

## Next Quarter Focus

### Q1 Goals

1. Complete Phase 1-10 (Core through Routing)
2. Achieve v0.5.0 release
3. Establish test coverage >70%
4. Document all public APIs
5. Create getting started guide

### Key Deliverables

- Working NativeAgent
- Provider integrations (Ollama, OmniRoute)
- Planning system operational
- Tool engine functional
- Initial loop implementations

---

## Long-term Vision (2-3 Years)

### Year 1: Foundation
- Establish core platform
- Build user base
- Create plugin ecosystem

### Year 2: Expansion
- Enterprise features
- Advanced capabilities
- Partner integrations

### Year 3: Leadership
- Industry standard
- AI-native development
- Autonomous workflows

---

## Appendix: Version History

| Version | Date | Notes |
|---------|------|-------|
| 0.1.0-dev | Current | Initial development |

---

**Document Owner:** MA-CLI Core Team  
**Review Cycle:** Monthly  
**Next Review:** After Phase 1 completion
