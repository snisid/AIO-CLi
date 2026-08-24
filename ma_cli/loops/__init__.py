"""Loops module initialization."""

from .engine import (
    ApprovalPolicy,
    Loop,
    LoopEngine,
    LoopResult,
    LoopState,
    LoopStatus,
    LoopStep,
    MemoryConfig,
    OutputConfig,
    RetryPolicy,
)

__all__ = [
    "ApprovalPolicy",
    "Loop",
    "LoopEngine",
    "LoopResult",
    "LoopState",
    "LoopStatus",
    "LoopStep",
    "MemoryConfig",
    "OutputConfig",
    "RetryPolicy",
]

# Global loop engine instance
_loop_engine: LoopEngine | None = None


def get_loop_engine() -> LoopEngine:
    """Get the global loop engine instance."""
    global _loop_engine
    if _loop_engine is None:
        _loop_engine = LoopEngine()
        # Register built-in loops
        _register_builtin_loops(_loop_engine)
    return _loop_engine


def _register_builtin_loops(engine: LoopEngine) -> None:
    """Register built-in loop definitions."""
    from .engine import LoopStep

    # CodeLoop - Core development workflow
    engine.register(
        Loop(
            name="CodeLoop",
            objective="Implement code changes with testing and review",
            trigger="task_implementation",
            inputs=["task_description", "context", "requirements"],
            agents=["developer", "tester", "code_reviewer"],
            tools=["read_file", "write_file", "edit_file", "shell", "test"],
            steps=[
                LoopStep(name="analyze", description="Analyze requirements and context"),
                LoopStep(name="plan", description="Create implementation plan"),
                LoopStep(name="implement", description="Write code changes"),
                LoopStep(name="test", description="Run tests"),
                LoopStep(name="review", description="Code review"),
                LoopStep(name="fix", description="Address review feedback"),
            ],
            success_criteria=["tests_pass", "review_approved"],
            retry_policy=RetryPolicy(max_retries=3),
            approval_policy=ApprovalPolicy(require_approval_for=["deploy", "delete"]),
        )
    )

    # DebugLoop - Failure diagnosis and fix
    engine.register(
        Loop(
            name="DebugLoop",
            objective="Diagnose and fix failures",
            trigger="test_failure",
            inputs=["error_logs", "failing_tests", "context"],
            agents=["debugger", "developer"],
            tools=["read_file", "shell", "test"],
            steps=[
                LoopStep(name="analyze_error", description="Analyze error logs"),
                LoopStep(name="reproduce", description="Reproduce the issue"),
                LoopStep(name="hypothesize", description="Form hypotheses"),
                LoopStep(name="fix", description="Implement fix"),
                LoopStep(name="verify", description="Verify fix"),
            ],
            success_criteria=["tests_pass", "error_resolved"],
            retry_policy=RetryPolicy(max_retries=5),
        )
    )

    # TestLoop - Test execution workflow
    engine.register(
        Loop(
            name="TestLoop",
            objective="Execute comprehensive test suite",
            trigger="validation_required",
            inputs=["test_paths", "test_framework"],
            agents=["tester"],
            tools=["test", "shell", "read_file"],
            steps=[
                LoopStep(name="detect_framework", description="Detect test framework"),
                LoopStep(name="run_tests", description="Execute tests"),
                LoopStep(name="collect_results", description="Collect results"),
                LoopStep(name="report", description="Generate report"),
            ],
            success_criteria=["all_tests_pass"],
        )
    )

    # ReviewLoop - Code review workflow
    engine.register(
        Loop(
            name="ReviewLoop",
            objective="Perform code quality review",
            trigger="code_complete",
            inputs=["diff", "files_changed", "context"],
            agents=["code_reviewer"],
            tools=["read_file", "git"],
            steps=[
                LoopStep(name="analyze_diff", description="Analyze changes"),
                LoopStep(name="check_quality", description="Check code quality"),
                LoopStep(name="check_security", description="Security scan"),
                LoopStep(name="report", description="Generate review report"),
            ],
            success_criteria=["review_complete"],
        )
    )

    # SecurityReviewLoop - Security-focused review
    engine.register(
        Loop(
            name="SecurityReviewLoop",
            objective="Perform security review",
            trigger="pre_release",
            inputs=["code_changes", "sensitive_operations"],
            agents=["security_reviewer"],
            tools=["read_file", "search"],
            steps=[
                LoopStep(name="scan_secrets", description="Scan for exposed secrets"),
                LoopStep(name="check_injection", description="Check injection vulnerabilities"),
                LoopStep(name="check_auth", description="Review auth implementation"),
                LoopStep(name="report", description="Generate security report"),
            ],
            success_criteria=["no_critical_issues"],
            approval_policy=ApprovalPolicy(require_approval_for=["bypass"]),
        )
    )

    # ResearchLoop - Web research workflow
    engine.register(
        Loop(
            name="ResearchLoop",
            objective="Conduct web research with citation",
            trigger="research_needed",
            inputs=["topic", "questions"],
            agents=["researcher"],
            tools=["browser", "search", "read_file"],
            steps=[
                LoopStep(name="search", description="Search web sources"),
                LoopStep(name="extract", description="Extract facts"),
                LoopStep(name="verify", description="Verify sources"),
                LoopStep(name="cite", description="Add citations"),
                LoopStep(name="summarize", description="Create summary"),
            ],
            success_criteria=["sources_cited", "facts_verified"],
        )
    )

    # FrontendLoop - UI/UX development
    engine.register(
        Loop(
            name="FrontendLoop",
            objective="Build frontend components with visual validation",
            trigger="frontend_task",
            inputs=["design_specs", "requirements"],
            agents=["frontend_engineer", "ui_ux_engineer"],
            tools=["write_file", "browser", "test"],
            steps=[
                LoopStep(name="design", description="Plan UI structure"),
                LoopStep(name="implement", description="Build components"),
                LoopStep(name="visual_test", description="Visual validation"),
                LoopStep(name="fix", description="Fix issues"),
            ],
            success_criteria=["visual_tests_pass"],
        )
    )

    # WebsiteCreationLoop - Full website generation
    engine.register(
        Loop(
            name="WebsiteCreationLoop",
            objective="Create complete website/application",
            trigger="website_request",
            inputs=["requirements", "stack_preference"],
            agents=["architect", "frontend_engineer", "backend_engineer", "devops_engineer"],
            tools=["write_file", "shell", "docker", "browser", "test"],
            steps=[
                LoopStep(name="analyze_requirements", description="Understand requirements"),
                LoopStep(name="choose_stack", description="Select technology stack"),
                LoopStep(name="architecture", description="Design architecture"),
                LoopStep(name="implement", description="Build application"),
                LoopStep(name="test", description="Run tests"),
                LoopStep(name="visual_validate", description="Visual validation"),
                LoopStep(name="review", description="Final review"),
            ],
            success_criteria=["tests_pass", "visual_validation_pass"],
        )
    )

    # DocumentationLoop - Documentation generation
    engine.register(
        Loop(
            name="DocumentationLoop",
            objective="Generate project documentation",
            trigger="documentation_needed",
            inputs=["project_context", "doc_type"],
            agents=["documentation_writer"],
            tools=["read_file", "write_file", "search"],
            steps=[
                LoopStep(name="gather_info", description="Gather project info"),
                LoopStep(name="structure", description="Create outline"),
                LoopStep(name="write", description="Write documentation"),
                LoopStep(name="review", description="Review accuracy"),
            ],
            success_criteria=["documentation_complete"],
        )
    )

    # HumanizationLoop - Natural language refinement
    engine.register(
        Loop(
            name="HumanizationLoop",
            objective="Refine text to sound natural and human-like",
            trigger="content_generation",
            inputs=["draft_text", "tone", "audience"],
            agents=["documentation_writer"],
            tools=[],
            steps=[
                LoopStep(name="analyze_tone", description="Analyze desired tone"),
                LoopStep(name="vary_structure", description="Vary sentence structure"),
                LoopStep(name="remove_patterns", description="Remove AI patterns"),
                LoopStep(name="preserve_accuracy", description="Ensure factual accuracy"),
            ],
            success_criteria=["natural_language", "accurate_content"],
        )
    )

    # GitLoop - Git operations workflow
    engine.register(
        Loop(
            name="GitLoop",
            objective="Manage Git operations safely",
            trigger="git_operation_needed",
            inputs=["operation", "branch_name", "message"],
            agents=["git_manager"],
            tools=["git", "read_file"],
            steps=[
                LoopStep(name="status", description="Check Git status"),
                LoopStep(name="stage", description="Stage changes"),
                LoopStep(name="commit", description="Create commit"),
                LoopStep(name="push", description="Push to remote"),
            ],
            success_criteria=["operation_complete"],
            approval_policy=ApprovalPolicy(require_approval_for=["merge_main", "force_push"]),
        )
    )

    # DeploymentLoop - Safe deployment workflow
    engine.register(
        Loop(
            name="DeploymentLoop",
            objective="Deploy application safely",
            trigger="deployment_requested",
            inputs=["environment", "version"],
            agents=["devops_engineer"],
            tools=["shell", "docker"],
            steps=[
                LoopStep(name="validate", description="Validate preconditions"),
                LoopStep(name="build", description="Build artifacts"),
                LoopStep(name="deploy", description="Deploy to environment"),
                LoopStep(name="verify", description="Verify deployment"),
            ],
            success_criteria=["deployment_successful"],
            approval_policy=ApprovalPolicy(require_approval_for=["production"]),
        )
    )
