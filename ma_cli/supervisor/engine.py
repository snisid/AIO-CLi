"""
Basic Supervisor for MA-CLI.

This module provides process monitoring, health checking, and status tracking.
"""

from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ProcessStatus(Enum):
    """Process execution status."""

    IDLE = "idle"
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"


@dataclass
class ProcessInfo:
    """Information about a monitored process."""

    id: str
    name: str
    command: list[str]
    status: ProcessStatus = ProcessStatus.IDLE
    pid: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    timeout_seconds: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """Get process duration in seconds."""
        if not self.started_at:
            return 0.0

        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()

    @property
    def is_running(self) -> bool:
        """Check if process is currently running."""
        return self.status in (ProcessStatus.RUNNING, ProcessStatus.STARTING)


@dataclass
class SystemHealth:
    """System health metrics."""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    disk_percent: float = 0.0
    active_processes: int = 0
    queued_tasks: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class Supervisor:
    """
    Basic supervisor for monitoring processes and system health.

    Provides process lifecycle management, health monitoring,
    and status reporting.
    """

    def __init__(self):
        self._processes: dict[str, ProcessInfo] = {}
        self._running_processes: dict[str, subprocess.Popen] = {}
        self._callbacks: dict[str, list[Callable[[ProcessInfo], None]]] = {
            "started": [],
            "completed": [],
            "failed": [],
            "status_change": [],
        }
        self._health_history: list[SystemHealth] = []
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None

    def register_process(
        self,
        process_id: str,
        name: str,
        command: list[str],
        timeout_seconds: int = 300,
        metadata: dict[str, Any] | None = None,
    ) -> ProcessInfo:
        """
        Register a process for monitoring.

        Args:
            process_id: Unique process identifier
            name: Human-readable name
            command: Command to execute
            timeout_seconds: Execution timeout
            metadata: Additional metadata

        Returns:
            ProcessInfo for the registered process
        """
        process = ProcessInfo(
            id=process_id,
            name=name,
            command=command,
            timeout_seconds=timeout_seconds,
            metadata=metadata or {},
            status=ProcessStatus.QUEUED,
        )

        self._processes[process_id] = process
        return process

    def start_process(self, process_id: str) -> bool:
        """
        Start a registered process.

        Args:
            process_id: Process ID to start

        Returns:
            True if started successfully
        """
        process = self._processes.get(process_id)
        if not process:
            return False

        if process.is_running:
            return False

        try:
            process.status = ProcessStatus.STARTING
            process.started_at = datetime.utcnow()

            # Start the process
            proc = subprocess.Popen(
                process.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            process.pid = proc.pid
            process.status = ProcessStatus.RUNNING

            self._running_processes[process_id] = proc

            # Notify callbacks
            self._notify_callbacks("started", process)

            # Start monitoring thread
            self._start_monitoring_thread(process_id)

            return True

        except Exception as e:
            process.status = ProcessStatus.FAILED
            process.error = str(e)
            self._notify_callbacks("failed", process)
            return False

    def _start_monitoring_thread(self, process_id: str) -> None:
        """Start a thread to monitor a process."""

        def monitor():
            process = self._processes.get(process_id)
            proc = self._running_processes.get(process_id)

            if not process or not proc:
                return

            try:
                stdout, stderr = proc.communicate(timeout=process.timeout_seconds)
                process.stdout = stdout
                process.stderr = stderr
                process.exit_code = proc.returncode

                if proc.returncode == 0:
                    process.status = ProcessStatus.COMPLETED
                else:
                    process.status = ProcessStatus.FAILED
                    process.error = f"Exit code: {proc.returncode}"

            except subprocess.TimeoutExpired:
                proc.kill()
                process.status = ProcessStatus.TIMEOUT
                process.error = f"Process exceeded timeout of {process.timeout_seconds}s"

            except Exception as e:
                process.status = ProcessStatus.FAILED
                process.error = str(e)

            finally:
                process.completed_at = datetime.utcnow()

                if process_id in self._running_processes:
                    del self._running_processes[process_id]

                event = "completed" if process.status == ProcessStatus.COMPLETED else "failed"
                self._notify_callbacks(event, process)
                self._notify_callbacks("status_change", process)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def stop_process(self, process_id: str) -> bool:
        """
        Stop a running process.

        Args:
            process_id: Process ID to stop

        Returns:
            True if stopped successfully
        """
        proc = self._running_processes.get(process_id)
        process = self._processes.get(process_id)

        if not proc or not process:
            return False

        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

            process.status = ProcessStatus.CANCELLED
            process.completed_at = datetime.utcnow()

            if process_id in self._running_processes:
                del self._running_processes[process_id]

            self._notify_callbacks("status_change", process)
            return True

        except Exception:
            return False

    def get_process(self, process_id: str) -> ProcessInfo | None:
        """Get process information by ID."""
        return self._processes.get(process_id)

    def get_all_processes(self) -> list[ProcessInfo]:
        """Get all registered processes."""
        return list(self._processes.values())

    def get_running_processes(self) -> list[ProcessInfo]:
        """Get all currently running processes."""
        return [p for p in self._processes.values() if p.is_running]

    def get_status(self) -> dict[str, Any]:
        """Get supervisor status summary."""
        processes = self._processes.values()

        return {
            "total_processes": len(self._processes),
            "running": sum(1 for p in processes if p.status == ProcessStatus.RUNNING),
            "queued": sum(1 for p in processes if p.status == ProcessStatus.QUEUED),
            "completed": sum(1 for p in processes if p.status == ProcessStatus.COMPLETED),
            "failed": sum(1 for p in processes if p.status == ProcessStatus.FAILED),
            "timeout": sum(1 for p in processes if p.status == ProcessStatus.TIMEOUT),
            "cancelled": sum(1 for p in processes if p.status == ProcessStatus.CANCELLED),
        }

    def on_event(self, event: str, callback: Callable[[ProcessInfo], None]) -> None:
        """
        Register a callback for process events.

        Args:
            event: Event type ('started', 'completed', 'failed', 'status_change')
            callback: Callback function
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _notify_callbacks(self, event: str, process: ProcessInfo) -> None:
        """Notify registered callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(process)
            except Exception:
                pass  # Don't let callback errors affect monitoring

    def get_system_health(self) -> SystemHealth:
        """Get current system health metrics."""
        health = SystemHealth(
            active_processes=len(self._running_processes),
            queued_tasks=sum(
                1 for p in self._processes.values() if p.status == ProcessStatus.QUEUED
            ),
            timestamp=datetime.utcnow(),
        )

        # Try to get system metrics (best effort)
        try:
            # Memory usage
            try:
                import resource

                rusage = resource.getrusage(resource.RUSAGE_SELF)
                health.memory_used_mb = rusage.ru_maxrss / 1024  # Convert to MB on Linux
            except Exception:
                pass

        except Exception:
            pass

        self._health_history.append(health)

        # Keep only recent history
        if len(self._health_history) > 100:
            self._health_history = self._health_history[-100:]

        return health

    def get_health_history(self, limit: int = 50) -> list[SystemHealth]:
        """Get recent health history."""
        return list(reversed(self._health_history[-limit:]))

    def cleanup_completed(self, older_than_seconds: int = 3600) -> int:
        """Clean up completed processes older than specified seconds."""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(seconds=older_than_seconds)
        cleaned = 0

        for process_id, process in list(self._processes.items()):
            if process.status in (
                ProcessStatus.COMPLETED,
                ProcessStatus.FAILED,
                ProcessStatus.CANCELLED,
                ProcessStatus.TIMEOUT,
            ):
                if process.completed_at and process.completed_at < cutoff:
                    del self._processes[process_id]
                    cleaned += 1

        return cleaned

    def shutdown(self, timeout: int = 10) -> None:
        """
        Shutdown supervisor and stop all running processes.

        Args:
            timeout: Timeout for each process to stop
        """
        # Stop all running processes
        for process_id in list(self._running_processes.keys()):
            self.stop_process(process_id)

        # Wait for threads to finish
        time.sleep(min(timeout / len(self._running_processes), 1) if self._running_processes else 0)


# Global supervisor instance
_supervisor: Supervisor | None = None


def get_supervisor() -> Supervisor:
    """Get global supervisor instance."""
    global _supervisor
    if _supervisor is None:
        _supervisor = Supervisor()
    return _supervisor
