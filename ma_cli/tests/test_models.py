"""Tests for core models."""

from datetime import datetime

from ma_cli.core.models import (
    AutonomyLevel,
    Event,
    EventType,
    ExecutionResult,
    Permission,
    PermissionLevel,
    PermissionPolicy,
    ReviewResult,
    State,
    Task,
    TaskStatus,
)


class TestTask:
    """Tests for Task model."""

    def test_task_creation(self):
        """Test creating a task with default values."""
        task = Task(title="Test Task", description="A test task")

        assert task.title == "Test Task"
        assert task.description == "A test task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == 5
        assert task.id is not None

    def test_task_is_blocked(self):
        """Test task dependency blocking."""
        task = Task(title="Dependent Task", dependencies=["task-1", "task-2"])

        # Should be blocked when dependencies incomplete
        assert task.is_blocked({"task-1"}) is True

        # Should not be blocked when all dependencies complete
        assert task.is_blocked({"task-1", "task-2"}) is False

        # Should not be blocked with no dependencies
        empty_task = Task(title="No deps")
        assert empty_task.is_blocked(set()) is False


class TestEvent:
    """Tests for Event model."""

    def test_event_creation(self):
        """Test creating an event."""
        event = Event(event_type=EventType.TASK_CREATED, payload={"task_id": "123"}, source="test")

        assert event.event_type == EventType.TASK_CREATED
        assert event.payload["task_id"] == "123"
        assert event.source == "test"
        assert isinstance(event.timestamp, datetime)

    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        event = Event(
            event_type=EventType.TASK_COMPLETED, payload={"result": "success"}, source="executor"
        )

        d = event.to_dict()
        assert d["event_type"] == "task_completed"
        assert d["payload"]["result"] == "success"
        assert d["source"] == "executor"
        assert "timestamp" in d


class TestState:
    """Tests for State model."""

    def test_state_creation(self):
        """Test creating state with defaults."""
        state = State()

        assert state.session_id is not None
        assert state.autonomy_level == AutonomyLevel.SUPERVISED_AUTO
        assert state.active_task_ids == []
        assert state.version == 1

    def test_state_update_activity(self):
        """Test updating activity timestamp."""
        state = State()
        old_timestamp = state.last_activity

        state.update_activity()

        assert state.last_activity >= old_timestamp


class TestPermission:
    """Tests for Permission model."""

    def test_permission_check_path(self):
        """Test path permission checking."""
        perm = Permission(
            action="read_file",
            level=PermissionLevel.READ_ONLY,
            allowed_paths=["/workspace", "/tmp"],
        )

        assert perm.check_path("/workspace/file.txt") is True
        assert perm.check_path("/tmp/test.txt") is True
        assert perm.check_path("/etc/passwd") is False

    def test_permission_check_command(self):
        """Test command permission checking."""
        perm = Permission(
            action="shell",
            level=PermissionLevel.STANDARD,
            denied_commands=["rm -rf /", "dd if=/dev/zero"],
        )

        assert perm.check_command("ls -la") is True
        assert perm.check_command("rm -rf /") is False
        assert perm.check_command("dd if=/dev/zero") is False


class TestPermissionPolicy:
    """Tests for PermissionPolicy model."""

    def test_policy_requires_approval(self):
        """Test approval requirement checking."""
        policy = PermissionPolicy(
            name="test_policy", approval_required_actions=["delete_database", "deploy_production"]
        )

        assert policy.requires_approval("delete_database") is True
        assert policy.requires_approval("deploy_production") is True
        assert policy.requires_approval("read_file") is False


class TestExecutionResult:
    """Tests for ExecutionResult model."""

    def test_result_success(self):
        """Test successful execution result."""
        result = ExecutionResult(
            success=True, output="Task completed successfully", duration_ms=1500
        )

        assert result.success is True
        assert result.error is None
        assert result.duration_ms == 1500

    def test_result_failure(self):
        """Test failed execution result."""
        result = ExecutionResult(success=False, error="Connection timeout", duration_ms=5000)

        assert result.success is False
        assert result.error == "Connection timeout"


class TestReviewResult:
    """Tests for ReviewResult model."""

    def test_review_passed(self):
        """Test passing review result."""
        result = ReviewResult(passed=True, score=0.95, severity="info")

        assert result.passed is True
        assert result.score == 0.95
        assert len(result.issues) == 0

    def test_review_failed(self):
        """Test failing review result."""
        result = ReviewResult(
            passed=False,
            issues=["Security vulnerability found"],
            suggestions=["Fix the vulnerability"],
            score=0.3,
            severity="critical",
        )

        assert result.passed is False
        assert len(result.issues) == 1
        assert result.severity == "critical"
