# MA-CLI Loops Documentation

## Multi-Agent Autonomous CLI

**Version:** 1.0.0  
**Document Type:** Loop Engine Architecture  

---

## 1. Overview

MA-CLI uses **Loops** as its primary workflow abstraction. Unlike "Skills" systems, Loops are explicit, auditable workflows with clear success/failure criteria.

---

## 2. Loop Definition

```python
@dataclass
class Loop:
    """Loop specification"""
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

### Loop Components

| Component | Description |
|-----------|-------------|
| name | Unique loop identifier |
| objective | What the loop achieves |
| trigger | When the loop activates |
| inputs | Required input data |
| tools | Tools used in the loop |
| agents | Agents participating |
| models | Models required |
| constraints | Operational constraints |
| memory | Memory configuration |
| steps | Execution steps |
| success_criteria | Conditions for success |
| failure_criteria | Conditions for failure |
| retry_policy | Retry configuration |
| approval_policy | Human approval requirements |
| output | Output specification |

---

## 3. Built-in Loops

### 3.1 HumanizationLoop

**Purpose:** Produce natural, human-like text while maintaining accuracy.

```yaml
name: humanization_loop
objective: Generate natural language content
trigger: content_generation_request
inputs:
  - source_content
  - tone_specification
  - audience
tools:
  - read_context
  - generate_text
  - analyze_style
agents:
  - native
models:
  - qwen-3.8
constraints:
  - preserve_facts
  - no_deception
  - maintain_accuracy
success_criteria:
  - natural_sentence_structure
  - varied_vocabulary
  - consistent_tone
  - factual_accuracy
failure_criteria:
  - robotic_patterns_detected
  - factual_errors
  - repetitive_structure
```

### 3.2 ResearchLoop

**Purpose:** Gather and synthesize information from multiple sources.

```yaml
name: research_loop
objective: Comprehensive information gathering
trigger: research_request
inputs:
  - topic
  - scope
  - depth_level
tools:
  - web_search
  - fetch_url
  - extract_content
  - cite_source
agents:
  - native
  - claude
models:
  - claude-opus-5
  - qwen-3.8
constraints:
  - cite_all_sources
  - verify_claims
  - no_fabrication
success_criteria:
  - multiple_sources_consulted
  - sources_credible
  - claims_verified
  - citations_complete
failure_criteria:
  - insufficient_sources
  - unreliable_sources
  - unverified_claims
```

### 3.3 CodeReviewLoop

**Purpose:** Review code for quality, correctness, and best practices.

```yaml
name: code_review_loop
objective: Ensure code quality
trigger: code_submission
inputs:
  - code
  - context
  - requirements
tools:
  - analyze_syntax
  - check_standards
  - detect_smells
  - suggest_improvements
agents:
  - claude
  - qwen
  - codex
models:
  - claude-opus-5
  - qwen-3.8
  - gpt-5.5
constraints:
  - constructive_feedback
  - specific_suggestions
  - prioritize_issues
success_criteria:
  - all_files_reviewed
  - issues_categorized
  - suggestions_actionable
failure_criteria:
  - review_incomplete
  - vague_feedback
  - missed_critical_issues
```

### 3.4 SecurityReviewLoop

**Purpose:** Identify security vulnerabilities and risks.

```yaml
name: security_review_loop
objective: Security vulnerability assessment
trigger: security_audit_request
inputs:
  - code
  - architecture
  - threat_model
tools:
  - static_analysis
  - secret_detection
  - dependency_scan
  - vulnerability_check
agents:
  - claude
  - native
models:
  - claude-opus-5
constraints:
  - comprehensive_coverage
  - risk_prioritization
  - actionable_recommendations
success_criteria:
  - all_vectors_examined
  - vulnerabilities_identified
  - remediation_provided
failure_criteria:
  - incomplete_scan
  - false_negatives
  - missing_critical_findings
```

### 3.5 DebugLoop

**Purpose:** Diagnose and fix bugs systematically.

```yaml
name: debug_loop
objective: Identify and resolve defects
trigger: bug_report
inputs:
  - error_description
  - stack_trace
  - reproduction_steps
tools:
  - analyze_logs
  - reproduce_issue
  - inspect_state
  - apply_fix
  - verify_fix
agents:
  - native
  - codex
models:
  - qwen-3.8
  - gpt-5.5
constraints:
  - minimal_changes
  - preserve_functionality
  - add_tests
success_criteria:
  - root_cause_identified
  - fix_applied
  - tests_passing
  - no_regressions
failure_criteria:
  - cause_unknown
  - fix_incomplete
  - new_bugs_introduced
```

### 3.6 TestingLoop

**Purpose:** Create and execute comprehensive tests.

```yaml
name: testing_loop
objective: Validate code correctness
trigger: test_request
inputs:
  - code
  - requirements
  - edge_cases
tools:
  - generate_tests
  - execute_tests
  - measure_coverage
  - report_results
agents:
  - native
  - codex
models:
  - qwen-3.8
constraints:
  - cover_edge_cases
  - meaningful_assertions
  - fast_execution
success_criteria:
  - coverage_threshold_met
  - all_tests_pass
  - flaky_tests_eliminated
failure_criteria:
  - low_coverage
  - failing_tests
  - incomplete_scenarios
```

### 3.7 FrontendDesignLoop

**Purpose:** Design and implement user interfaces.

```yaml
name: frontend_design_loop
objective: Create polished UI/UX
trigger: ui_request
inputs:
  - requirements
  - design_preferences
  - target_platform
tools:
  - analyze_requirements
  - generate_mockup
  - implement_component
  - validate_accessibility
agents:
  - native
  - claude
models:
  - claude-opus-5
  - qwen-3.8
constraints:
  - responsive_design
  - accessibility_compliance
  - performance_budget
success_criteria:
  - matches_requirements
  - accessible
  - performant
  - visually_coherent
failure_criteria:
  - accessibility_violations
  - performance_issues
  - design_inconsistencies
```

### 3.8 DeploymentLoop

**Purpose:** Deploy applications safely.

```yaml
name: deployment_loop
objective: Safe application deployment
trigger: deployment_request
inputs:
  - build_artifacts
  - environment_config
  - rollback_plan
tools:
  - validate_build
  - deploy_staging
  - run_smoke_tests
  - deploy_production
  - monitor_health
agents:
  - native
models:
  - qwen-3.8
constraints:
  - zero_downtime
  - rollback_ready
  - monitoring_enabled
approval_policy:
  production_deploy: required
success_criteria:
  - deployment_successful
  - health_checks_pass
  - no_errors
failure_criteria:
  - deployment_failed
  - health_checks_fail
  - errors_detected
```

### 3.9 DocumentationLoop

**Purpose:** Generate comprehensive documentation.

```yaml
name: documentation_loop
objective: Create accurate documentation
trigger: documentation_request
inputs:
  - code
  - api_specs
  - user_flows
tools:
  - extract_api
  - generate_examples
  - write_guides
  - validate_accuracy
agents:
  - native
  - claude
models:
  - claude-opus-5
constraints:
  - accurate_information
  - clear_language
  - complete_coverage
success_criteria:
  - all_apis_documented
  - examples_working
  - guides_clear
failure_criteria:
  - missing_documentation
  - inaccurate_info
  - broken_examples
```

### 3.10 WebsiteCreationLoop

**Purpose:** Build complete websites from requirements.

```yaml
name: website_creation_loop
objective: End-to-end website development
trigger: website_request
inputs:
  - requirements
  - content
  - branding
tools:
  - plan_architecture
  - generate_components
  - integrate_styles
  - setup_routing
  - configure_deployment
agents:
  - native
  - claude
models:
  - claude-opus-5
  - qwen-3.8
constraints:
  - seo_optimized
  - mobile_responsive
  - fast_loading
success_criteria:
  - all_pages_functional
  - design_coherent
  - performance_good
  - seo_validated
failure_criteria:
  - broken_pages
  - design_issues
  - performance_problems
```

---

## 4. Loop Engine

The Loop Engine executes defined loops:

```python
class LoopEngine:
    def __init__(
        self,
        agent_router: AgentRouter,
        tool_engine: ToolEngine,
        memory: MemoryEngine,
        permission_engine: PermissionEngine
    ):
        self.agent_router = agent_router
        self.tool_engine = tool_engine
        self.memory = memory
        self.permissions = permission_engine
        self._loops: dict[str, Loop] = {}
    
    def register(self, loop: Loop):
        """Register a loop definition"""
        self._loops[loop.name] = loop
    
    async def execute(
        self,
        loop_name: str,
        inputs: dict,
        context: ExecutionContext
    ) -> LoopResult:
        """Execute a loop with given inputs"""
        loop = self._loops.get(loop_name)
        if not loop:
            raise LoopNotFoundError(f"Loop {loop_name} not found")
        
        # Check permissions
        await self.permissions.check_loop_permission(loop, context)
        
        # Initialize state
        state = LoopState(
            loop=loop,
            inputs=inputs,
            current_step=0,
            outputs={}
        )
        
        # Execute steps
        for step in loop.steps:
            result = await self._execute_step(step, state, context)
            if result.failed:
                return await self._handle_failure(loop, state, result)
            state.outputs[step.name] = result.output
        
        # Evaluate success criteria
        success = await self._evaluate_success(loop, state)
        
        return LoopResult(
            success=success,
            outputs=state.outputs,
            state=state
        )
    
    async def _execute_step(
        self,
        step: LoopStep,
        state: LoopState,
        context: ExecutionContext
    ) -> StepResult:
        """Execute a single loop step"""
        # Select agent for this step
        agent = await self.agent_router.select_for_step(step, state)
        
        # Execute with retry
        result = await self._execute_with_retry(agent, step, state, context)
        
        return result
```

---

## 5. Skill → Loop Converter

Import external skills and convert to MA-CLI Loops:

```bash
ma-cli loop import https://github.com/example/repository.git
```

### Conversion Process

1. **Clone Repository**
   ```python
   repo = await git.clone(url, temp_dir)
   ```

2. **Inspect Documentation**
   ```python
   docs = await find_and_parse_docs(repo)
   ```

3. **Identify Instructions**
   ```python
   instructions = extract_instructions(docs)
   ```

4. **Identify Tools**
   ```python
   tools = identify_required_tools(repo)
   ```

5. **Identify Workflows**
   ```python
   workflows = parse_workflows(repo)
   ```

6. **Identify Prompts**
   ```python
   prompts = extract_prompts(repo)
   ```

7. **Identify Reusable Logic**
   ```python
   logic = extract_reusable_logic(repo)
   ```

8. **Analyze Dependencies**
   ```python
   deps = analyze_dependencies(repo)
   ```

9. **Generate Loop Specification**
   ```python
   loop_spec = generate_loop_spec(
       instructions=instructions,
       tools=tools,
       workflows=workflows,
       prompts=prompts,
       logic=logic
   )
   ```

10. **Validate Loop**
    ```python
    validation = validate_loop(loop_spec)
    if not validation.valid:
        raise ValidationError(validation.errors)
    ```

11. **Sandbox Test**
    ```python
    test_result = await test_in_sandbox(loop_spec)
    ```

12. **Register Loop**
    ```python
    loop_engine.register(loop_spec)
    ```

---

## 6. Loop State Management

```python
@dataclass
class LoopState:
    loop: Loop
    inputs: dict
    current_step: int
    outputs: dict
    retries: dict[str, int]
    approvals: dict[str, bool]
    started_at: datetime
    last_updated: datetime
    status: LoopStatus

class LoopStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

---

## 7. Retry Policy

```python
@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_type: str = "exponential"  # linear, exponential
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    retry_on: list[str] = None  # Error types to retry
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False
        if self.retry_on and type(error).__name__ not in self.retry_on:
            return False
        return True
    
    def get_delay(self, attempt: int) -> float:
        if self.backoff_type == "linear":
            return self.initial_delay_ms * attempt / 1000
        else:  # exponential
            return min(
                self.initial_delay_ms * (2 ** attempt),
                self.max_delay_ms
            ) / 1000
```

---

## 8. Approval Policy

```python
@dataclass
class ApprovalPolicy:
    auto_approve: bool = False
    require_approval_for: list[str] = None
    approval_timeout_seconds: int = 300
    
    def requires_approval(self, action: str) -> bool:
        if self.auto_approve:
            return False
        if self.require_approval_for is None:
            return False
        return action in self.require_approval_for
```

---

## 9. Loop Registry

```python
class LoopRegistry:
    def __init__(self):
        self._loops: dict[str, Loop] = {}
        self._categories: dict[str, list[str]] = {}
    
    def register(self, loop: Loop, category: str = "custom"):
        self._loops[loop.name] = loop
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(loop.name)
    
    def get(self, name: str) -> Optional[Loop]:
        return self._loops.get(name)
    
    def list_all(self) -> list[Loop]:
        return list(self._loops.values())
    
    def list_by_category(self, category: str) -> list[Loop]:
        names = self._categories.get(category, [])
        return [self._loops[n] for n in names if n in self._loops]
    
    def list_categories(self) -> list[str]:
        return list(self._categories.keys())
```

---

## 10. Best Practices

### Loop Design

1. **Clear Objectives**: Each loop should have a single, clear objective
2. **Explicit Criteria**: Define success and failure explicitly
3. **Appropriate Granularity**: Not too coarse, not too fine
4. **Error Handling**: Include retry and failure handling
5. **Approval Gates**: Require approval for critical actions

### Loop Execution

1. **State Persistence**: Save state for resume capability
2. **Timeout Enforcement**: Prevent infinite loops
3. **Resource Limits**: Control resource consumption
4. **Audit Logging**: Log all loop executions
5. **Cancellation Support**: Allow graceful cancellation

### Loop Import

1. **Source Verification**: Verify repository authenticity
2. **Security Scanning**: Scan for malicious content
3. **Sandbox Testing**: Test before registration
4. **User Consent**: Require explicit user approval
5. **Documentation**: Document imported loops

---

**Document Owner:** MA-CLI Core Team  
**Last Updated:** Phase 1 Initiation
