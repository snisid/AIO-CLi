from ma_cli.runtime import ExecutionEngine, Task, TaskGraph, TaskState


def test_task_graph_executes_dependencies_in_order():
    seen = []
    graph = TaskGraph([
        Task("a", lambda: seen.append("a")),
        Task("b", lambda: seen.append("b"), dependencies=("a",)),
    ])
    report = ExecutionEngine().run(graph)
    assert report.success
    assert seen == ["a", "b"]


def test_task_graph_rejects_cycles():
    a = Task("a", lambda: None, dependencies=("b",))
    b = Task("b", lambda: None, dependencies=("a",))
    try:
        TaskGraph([a, b])
    except ValueError as exc:
        assert "cycle" in str(exc).lower()
    else:
        raise AssertionError("cycle must be rejected")


def test_bounded_repair():
    attempts = []

    def action():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("transient")
        return "ok"

    report = ExecutionEngine(max_attempts=2).run(
        TaskGraph([Task("repairable", action)]),
        repair=lambda task, exc: True,
    )
    task = report.tasks["repairable"]
    assert report.success
    assert task.state in {TaskState.REPAIRED, TaskState.PASSED}
    assert task.attempts == 2


def test_failure_is_not_reported_as_success():
    report = ExecutionEngine().run(
        TaskGraph([Task("bad", lambda: (_ for _ in ()).throw(RuntimeError("boom")))])
    )
    assert not report.success
    assert report.tasks["bad"].state == TaskState.FAILED
