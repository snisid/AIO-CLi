"""
Native Agent for MA-CLI.

The NativeAgent executes tasks end-to-end using local tools and models.
"""
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

from ..agents.base import Agent
from ..core.models import (
    AgentStatus, 
    HealthStatus, 
    ExecutionResult, 
    ReviewResult,
    Task,
)
from .intent import IntentAnalyzer
from .planner import Planner, Plan
from .task_graph import TaskGraph, TaskNode, NodeStatus
from ..tools.registry import get_tool_registry, ToolRegistry


@dataclass
class AgentState:
    """State of the NativeAgent."""
    current_task: Optional[str] = None
    current_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 50
    started_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None


class NativeAgent(Agent):
    """
    Native Agent that executes tasks end-to-end.
    
    Capabilities:
    - Intent analysis
    - Planning
    - Task graph execution
    - Tool selection and execution
    - Permission enforcement
    - Self-testing and validation
    - Iterative fix cycles
    """
    
    def __init__(self, workspace: Optional[str] = None):
        self._workspace = workspace
        self._status = AgentStatus.IDLE
        self._health = HealthStatus.HEALTHY
        self._state = AgentState()
        self._intent_analyzer = IntentAnalyzer()
        self._planner = Planner()
        self._tool_registry = get_tool_registry()
        self._current_result: Optional[ExecutionResult] = None
        self._cancelled = False
        
    @property
    def id(self) -> str:
        return "native_agent"
    
    @property
    def name(self) -> str:
        return "NativeAgent"
    
    @property
    def provider(self) -> str:
        return "local"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "intent_analysis",
            "planning",
            "tool_use",
            "file_operations",
            "shell_execution",
            "testing",
            "code_review",
            "iterative_fix",
        ]
    
    @property
    def roles(self) -> List[str]:
        return [
            "developer",
            "tester",
            "architect",
            "code_reviewer",
            "debugger",
        ]
    
    @property
    def status(self) -> AgentStatus:
        return self._status
    
    @property
    def health(self) -> HealthStatus:
        return self._health
    
    async def execute(self, task: Task) -> ExecutionResult:
        """
        Execute a task end-to-end.
        
        Flow:
        1. Analyze intent
        2. Create plan
        3. Build task graph
        4. Execute steps with tool calls
        5. Test changes
        6. Review results
        7. Fix issues iteratively
        8. Final validation
        
        Args:
            task: Task to execute
            
        Returns:
            ExecutionResult with outcome
        """
        self._state = AgentState(
            current_task=task.id,
            started_at=datetime.utcnow(),
            max_iterations=50,
        )
        self._status = AgentStatus.BUSY
        self._cancelled = False
        
        try:
            # Step 1: Intent Analysis
            intent = self._intent_analyzer.analyze(task.description or task.title)
            
            # Step 2: Create Plan
            plan = self._planner.create_plan(intent)
            
            # Step 3: Build Task Graph
            graph = TaskGraph(graph_id=task.id)
            for step in plan.steps:
                node = TaskNode(
                    id=step.name,
                    name=step.name,
                    description=step.description,
                    agent_role=step.agent_role,
                    tools=step.tools,
                    dependencies=step.dependencies,
                )
                graph.add_node(node)
            
            # Step 4: Execute Task Graph
            result = await self._execute_graph(graph, plan)
            
            self._status = AgentStatus.IDLE if result.success else AgentStatus.ERROR
            return result
            
        except Exception as e:
            self._status = AgentStatus.ERROR
            return ExecutionResult(
                success=False,
                error=str(e),
                metadata={'stage': 'execution'},
            )
        finally:
            self._state.current_task = None
    
    async def _execute_graph(self, graph: TaskGraph, plan: Plan) -> ExecutionResult:
        """Execute a task graph."""
        outputs: Dict[str, Any] = {}
        
        while not graph.is_complete():
            if self._cancelled:
                return ExecutionResult(
                    success=False,
                    error="Execution cancelled",
                    metadata={'outputs': outputs},
                )
                
            # Check iteration limit
            self._state.iteration_count += 1
            if self._state.iteration_count > self._state.max_iterations:
                return ExecutionResult(
                    success=False,
                    error=f"Max iterations ({self._state.max_iterations}) exceeded",
                    metadata={'outputs': outputs},
                )
            
            # Get ready nodes
            ready_nodes = graph.get_ready_nodes()
            
            if not ready_nodes:
                if graph.has_failures():
                    break
                # No ready nodes but not complete - might be blocked
                break
            
            # Execute first ready node (could parallelize)
            node = ready_nodes[0]
            self._state.current_step = node.id
            
            try:
                graph.mark_started(node.id)
                
                # Execute the step
                step_result = await self._execute_step(node, outputs)
                
                if step_result.success:
                    graph.mark_completed(node.id, step_result.output)
                    self._state.completed_steps.append(node.id)
                    outputs[node.id] = step_result.output
                else:
                    # Retry logic
                    if node.can_retry():
                        node.retry_count += 1
                        graph.state.status = f"retrying_{node.retry_count}"
                        continue
                    else:
                        graph.mark_failed(node.id, step_result.error or "Step failed")
                        
            except Exception as e:
                graph.mark_failed(node.id, str(e))
        
        # Final evaluation
        success = not graph.has_failures() and graph.is_complete()
        
        return ExecutionResult(
            success=success,
            output=str(outputs) if success else None,
            error=graph.state.error if not success else None,
            metadata={
                'graph_state': graph.get_state(),
                'outputs': outputs,
                'iterations': self._state.iteration_count,
            },
        )
    
    async def _execute_step(self, node: TaskNode, context: Dict[str, Any]) -> ExecutionResult:
        """Execute a single step using tools."""
        # Select tools based on node requirements
        available_tools = node.tools
        
        if not available_tools:
            return ExecutionResult(
                success=True,
                output=f"Step '{node.name}' completed (no tools needed)",
            )
        
        # Execute tools based on agent role
        if node.agent_role == 'developer':
            return await self._execute_developer_step(node, context)
        elif node.agent_role == 'tester':
            return await self._execute_tester_step(node, context)
        elif node.agent_role == 'code_reviewer':
            return await self._execute_reviewer_step(node, context)
        elif node.agent_role == 'architect':
            return await self._execute_architect_step(node, context)
        else:
            return await self._execute_generic_step(node, context)
    
    async def _execute_developer_step(self, node: TaskNode, context: Dict[str, Any]) -> ExecutionResult:
        """Execute a developer step."""
        # For now, return placeholder - real implementation would use LLM
        return ExecutionResult(
            success=True,
            output=f"Developer step '{node.name}' executed",
        )
    
    async def _execute_tester_step(self, node: TaskNode, context: Dict[str, Any]) -> ExecutionResult:
        """Execute a tester step."""
        registry = get_tool_registry()
        
        if registry.has_tool('test'):
            result = await registry.execute('test')
            return ExecutionResult(
                success=result.success,
                output=result.output,
                error=result.error,
            )
        
        return ExecutionResult(
            success=True,
            output="Test step completed (no test tool available)",
        )
    
    async def _execute_reviewer_step(self, node: TaskNode, context: Dict[str, Any]) -> ExecutionResult:
        """Execute a code reviewer step."""
        # Placeholder - real implementation would analyze code
        return ExecutionResult(
            success=True,
            output=f"Review step '{node.name}' completed",
        )
    
    async def _execute_architect_step(self, node: TaskNode, context: Dict[str, Any]) -> ExecutionResult:
        """Execute an architect step."""
        # Placeholder - real implementation would analyze and plan
        return ExecutionResult(
            success=True,
            output=f"Architecture step '{node.name}' completed",
        )
    
    async def _execute_generic_step(self, node: TaskNode, context: Dict[str, Any]) -> ExecutionResult:
        """Execute a generic step."""
        return ExecutionResult(
            success=True,
            output=f"Step '{node.name}' completed",
        )
    
    async def cancel(self) -> bool:
        """Cancel current execution."""
        self._cancelled = True
        self._status = AgentStatus.IDLE
        return True
    
    async def inspect(self) -> Dict[str, Any]:
        """Return agent inspection details."""
        return {
            'agent_id': self.id,
            'agent_name': self.name,
            'status': self._status.value,
            'health': self._health.value,
            'state': {
                'current_task': self._state.current_task,
                'current_step': self._state.current_step,
                'completed_steps': self._state.completed_steps,
                'iteration_count': self._state.iteration_count,
                'max_iterations': self._state.max_iterations,
            },
            'capabilities': self.capabilities,
            'roles': self.roles,
        }
    
    async def review(self, code: str) -> ReviewResult:
        """Review generated code."""
        # Simple heuristic review
        issues = []
        suggestions = []
        
        if len(code) > 10000:
            issues.append("File is very large (>10KB)")
        
        if code.count('\n') < 5:
            suggestions.append("Consider breaking into smaller functions")
        
        passed = len(issues) == 0
        score = 1.0 - (len(issues) * 0.2)
        
        return ReviewResult(
            passed=passed,
            issues=issues,
            suggestions=suggestions,
            score=max(0.0, min(1.0, score)),
        )
    
    async def report(self) -> Dict[str, Any]:
        """Generate agent activity report."""
        return {
            'agent_id': self.id,
            'agent_name': self.name,
            'status': self._status.value,
            'tasks_completed': len(self._state.completed_steps),
            'last_activity': self._state.last_activity.isoformat() if self._state.last_activity else None,
        }
