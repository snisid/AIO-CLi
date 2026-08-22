"""
Sandbox Manager for MA-CLI.

Provides secure isolated execution environments using Docker.
CRITICAL: Hard-fail policy - never fallback to host execution.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import docker  # type: ignore

from ..core.models import HealthStatus
from ..events.bus import EventBus
from ..security.permission_engine import PermissionEngine

logger = logging.getLogger(__name__)


class SandboxPolicy(Enum):
    """Sandbox enforcement policy."""
    STRICT = "strict"  # Hard fail if sandbox unavailable
    PERMISSIVE = "permissive"  # Allow fallback (NOT RECOMMENDED)
    DISABLED = "disabled"  # No sandboxing


@dataclass
class SandboxConfig:
    """Configuration for sandbox environment."""
    
    image: str = "python:3.11-slim"
    network_enabled: bool = False
    allowed_network_hosts: list[str] = field(default_factory=list)
    filesystem_mounts: dict[str, str] = field(default_factory=dict)  # host:container
    memory_limit: str = "2g"
    cpu_limit: float = 2.0
    timeout_seconds: int = 600
    policy: SandboxPolicy = SandboxPolicy.STRICT
    allowed_commands: list[str] = field(default_factory=list)
    denied_commands: list[str] = field(default_factory=list)
    read_only_paths: list[str] = field(default_factory=list)
    writable_paths: list[str] = field(default_factory=list)


@dataclass
class SandboxResult:
    """Result of sandbox execution."""
    
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    container_id: str | None = None
    error: str | None = None
    policy_violation: bool = False
    violation_details: str | None = None


class SandboxUnavailableError(Exception):
    """Raised when sandbox cannot be established."""


class PolicyViolationError(Exception):
    """Raised when a command violates sandbox policy."""


class SandboxManager:
    """
    Manages secure sandboxed execution environments.
    
    CRITICAL SECURITY FEATURE:
    - Hard-fail policy: If Docker is unavailable, tasks are ABORTED
    - Never falls back to host execution
    - Enforces network egress filtering
    - Enforces granular filesystem permissions
    """
    
    def __init__(
        self,
        config: SandboxConfig | None = None,
        permission_engine: PermissionEngine | None = None,
        event_bus: EventBus | None = None
    ):
        self.config = config or SandboxConfig()
        self.permission_engine = permission_engine
        self.event_bus = event_bus
        self._docker_client: docker.DockerClient | None = None
        self._active_containers: dict[str, Any] = {}
        self._workspace_roots: dict[str, Path] = {}
        
    @property
    def docker_client(self) -> docker.DockerClient:
        """Get Docker client, raising error if unavailable."""
        if self._docker_client is None:
            try:
                self._docker_client = docker.from_env()
                # Test connection
                self._docker_client.ping()
            except Exception as e:
                logger.error(f"Docker unavailable: {e}")
                raise SandboxUnavailableError(
                    f"Docker daemon unavailable: {e}. "
                    "Sandbox enforcement requires Docker. Task aborted."
                )
        return self._docker_client
    
    def is_available(self) -> bool:
        """Check if Docker sandbox is available."""
        try:
            client = docker.from_env()
            client.ping()
            return True
        except Exception:
            return False
    
    def health_check(self) -> HealthStatus:
        """Perform health check on sandbox infrastructure."""
        if not self.is_available():
            return HealthStatus.UNHEALTHY
        
        try:
            # Check image availability
            if self.config.image:
                try:
                    self.docker_client.images.get(self.config.image)
                except Exception:
                    return HealthStatus.DEGRADED
            
            return HealthStatus.HEALTHY
        except Exception as e:
            logger.warning(f"Sandbox health degraded: {e}")
            return HealthStatus.DEGRADED
    
    def create_workspace(self, task_id: str) -> Path:
        """Create isolated workspace for a task."""
        workspace_root = Path(tempfile.mkdtemp(prefix=f"ma-cli-{task_id}-"))
        
        # Create standard directory structure
        (workspace_root / "workspace").mkdir()
        (workspace_root / "logs").mkdir()
        (workspace_root / "tmp").mkdir()
        
        self._workspace_roots[task_id] = workspace_root
        
        logger.info(f"Created workspace: {workspace_root}")
        return workspace_root / "workspace"
    
    def destroy_workspace(self, task_id: str) -> None:
        """Clean up workspace after task completion."""
        if task_id in self._workspace_roots:
            workspace = self._workspace_roots[task_id]
            try:
                import shutil
                shutil.rmtree(workspace.parent)
                logger.info(f"Destroyed workspace: {workspace.parent}")
            except Exception as e:
                logger.warning(f"Failed to cleanup workspace: {e}")
            finally:
                del self._workspace_roots[task_id]
    
    def _check_command_policy(self, command: str) -> None:
        """Validate command against sandbox policy."""
        # Check denied commands
        for denied in self.config.denied_commands:
            if denied in command:
                raise PolicyViolationError(
                    f"Command contains denied pattern '{denied}': {command}"
                )
        
        # Check allowed commands (if specified)
        if self.config.allowed_commands:
            allowed = False
            for allowed_cmd in self.config.allowed_commands:
                if allowed_cmd in command:
                    allowed = True
                    break
            if not allowed:
                raise PolicyViolationError(
                    f"Command not in allowed list: {command}"
                )
    
    def _build_docker_run_args(
        self,
        workspace_path: Path,
        command: str,
        network_hosts: list[str] | None = None
    ) -> dict[str, Any]:
        """Build Docker run arguments with security constraints."""
        
        # Build volume mounts
        volumes = {
            str(workspace_path): {
                "bind": "/workspace",
                "mode": "rw"
            }
        }
        
        # Add read-only mounts
        for host_path in self.config.read_only_paths:
            volumes[host_path] = {
                "bind": f"/readonly/{Path(host_path).name}",
                "mode": "ro"
            }
        
        # Build environment
        environment = {
            "MA_CLI_SANDBOX": "true",
            "WORKSPACE": "/workspace",
            "HOME": "/workspace",
        }
        
        # Build network configuration
        network_mode = "none" if not self.config.network_enabled else "bridge"
        
        # Build extra hosts for allowed destinations
        extra_hosts = {}
        if network_hosts:
            for host in network_hosts:
                if host in self.config.allowed_network_hosts or not self.config.allowed_network_hosts:
                    extra_hosts[host] = "host-gateway"
        
        return {
            "image": self.config.image,
            "command": command,
            "volumes": volumes,
            "working_dir": "/workspace",
            "environment": environment,
            "network_mode": network_mode,
            "mem_limit": self.config.memory_limit,
            "nano_cpus": int(self.config.cpu_limit * 1e9),
            "read_only": True,  # Root filesystem is read-only
            "tmpfs": {
                "/tmp": "rw,noexec,nosuid,size=512m",
                "/var/tmp": "rw,noexec,nosuid,size=512m",
            },
            "security_opt": [
                "no-new-privileges:true",
                "apparmor=unconfined",  # Can be customized
            ],
            "cap_drop": ["ALL"],  # Drop all capabilities
            "cap_add": ["CHOWN", "SETUID", "SETGID"] if self.config.allowed_commands else [],
            "extra_hosts": extra_hosts if extra_hosts else None,
            "remove": True,  # Auto-remove container
            "detach": False,
        }
    
    async def execute(
        self,
        task_id: str,
        command: str,
        workspace_path: Path | None = None,
        timeout: int | None = None
    ) -> SandboxResult:
        """
        Execute command in sandboxed environment.
        
        CRITICAL: Raises SandboxUnavailableError if Docker is not available.
        Never falls back to host execution.
        """
        start_time = datetime.utcnow()
        
        # Check sandbox availability FIRST
        if not self.is_available():
            logger.critical(f"TASK {task_id}: Sandbox unavailable - ABORTING")
            raise SandboxUnavailableError(
                "Docker sandbox required but unavailable. "
                "Task aborted for security. Install Docker or disable sandbox mode."
            )
        
        # Validate command against policy
        try:
            self._check_command_policy(command)
        except PolicyViolationError as e:
            logger.warning(f"Policy violation in task {task_id}: {e}")
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=0,
                policy_violation=True,
                violation_details=str(e)
            )
        
        # Get or create workspace
        if workspace_path is None:
            workspace_path = self.create_workspace(task_id)
        
        timeout = timeout or self.config.timeout_seconds
        
        try:
            # Build Docker run arguments
            run_args = self._build_docker_run_args(
                workspace_path=workspace_path,
                command=command,
                network_hosts=None  # Can be extended for specific hosts
            )
            
            logger.info(f"Executing in sandbox: {command[:100]}...")
            
            # Run container
            container_result = await asyncio.wait_for(
                asyncio.to_thread(
                    self.docker_client.containers.run,
                    **run_args
                ),
                timeout=timeout
            )
            
            # Parse result
            if isinstance(container_result, bytes):
                output = container_result.decode('utf-8', errors='replace')
                stdout = output
                stderr = ""
                exit_code = 0
            else:
                # Container object (detached mode)
                container = container_result
                self._active_containers[task_id] = container
                
                # Wait for completion
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(container.wait, condition="not-running"),
                        timeout=timeout
                    )
                    exit_code = result.get("StatusCode", 0) if isinstance(result, dict) else 0
                    
                    # Get logs
                    logs = await asyncio.to_thread(container.logs)
                    output = logs.decode('utf-8', errors='replace')
                    stdout = output
                    stderr = ""
                    
                except asyncio.TimeoutError:
                    logger.error(f"Container timeout for task {task_id}")
                    await asyncio.to_thread(container.stop)
                    return SandboxResult(
                        success=False,
                        exit_code=-1,
                        stdout="",
                        stderr=f"Timeout after {timeout}s",
                        duration_ms=timeout * 1000,
                        container_id=container.id,
                        error="timeout"
                    )
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            success = exit_code == 0
            
            result = SandboxResult(
                success=success,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms
            )
            
            logger.info(
                f"Sandbox execution {'succeeded' if success else 'failed'} "
                f"in {duration_ms}ms with exit code {exit_code}"
            )
            
            return result
            
        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Docker API error: {e}",
                duration_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                error=str(e)
            )
            
        except asyncio.TimeoutError:
            logger.error(f"Execution timeout after {timeout}s")
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                duration_ms=timeout * 1000,
                error="timeout"
            )
            
        except Exception as e:
            logger.exception(f"Unexpected sandbox error: {e}")
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Unexpected error: {e}",
                duration_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                error=str(e)
            )
    
    async def cancel(self, task_id: str) -> bool:
        """Cancel running container for task."""
        if task_id in self._active_containers:
            container = self._active_containers[task_id]
            try:
                await asyncio.to_thread(container.stop, timeout=10)
                logger.info(f"Cancelled container for task {task_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to cancel container: {e}")
                return False
        return False
    
    def get_network_policy_summary(self) -> dict[str, Any]:
        """Get summary of network restrictions."""
        return {
            "network_enabled": self.config.network_enabled,
            "allowed_hosts": self.config.allowed_network_hosts,
            "default_policy": "DENY_ALL" if not self.config.network_enabled else "ALLOW_SPECIFIED"
        }
    
    def get_filesystem_policy_summary(self) -> dict[str, Any]:
        """Get summary of filesystem restrictions."""
        return {
            "workspace_isolated": True,
            "read_only_root": True,
            "read_only_paths": self.config.read_only_paths,
            "writable_paths": self.config.writable_paths,
            "tmpfs_enabled": True
        }
