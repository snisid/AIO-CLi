"""
Task Graph Module

Manages task dependencies and execution order.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from enum import Enum


class NodeStatus(Enum):
    """Status of a task node."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class TaskNode:
    """A node in the task graph."""
    id: str
    name: str
    description: str
    agent_role: str
    tools: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def is_ready(self, completed: Set[str]) -> bool:
        """Check if this node is ready to execute."""
        if self.status != NodeStatus.PENDING:
            return False
        return all(dep in completed for dep in self.dependencies)
    
    def can_retry(self) -> bool:
        """Check if this node can be retried."""
        return self.retry_count < self.max_retries


@dataclass
class TaskGraphState:
    """State of a task graph execution."""
    graph_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_nodes: Set[str] = field(default_factory=set)
    failed_nodes: Set[str] = field(default_factory=set)
    current_node: Optional[str] = None
    status: str = "pending"
    error: Optional[str] = None


class TaskGraph:
    """
    Manages task dependencies and execution order.
    
    Supports:
    - Dependency tracking
    - Parallel execution of independent tasks
    - Failure propagation
    - Retry logic
    """
    
    def __init__(self, graph_id: str):
        self.graph_id = graph_id
        self.nodes: Dict[str, TaskNode] = {}
        self.state = TaskGraphState(graph_id=graph_id)
        self._order_cache: Optional[List[str]] = None
        
    def add_node(self, node: TaskNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node
        self._order_cache = None
        
    def get_node(self, node_id: str) -> Optional[TaskNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def get_ready_nodes(self) -> List[TaskNode]:
        """Get all nodes that are ready to execute."""
        ready = []
        for node in self.nodes.values():
            if node.is_ready(self.state.completed_nodes):
                ready.append(node)
        return ready
    
    def mark_started(self, node_id: str) -> None:
        """Mark a node as started."""
        node = self.nodes.get(node_id)
        if node:
            node.status = NodeStatus.RUNNING
            node.started_at = datetime.utcnow()
            self.state.current_node = node_id
            self.state.status = "running"
            
    def mark_completed(self, node_id: str, result: str) -> None:
        """Mark a node as completed."""
        node = self.nodes.get(node_id)
        if node:
            node.status = NodeStatus.COMPLETED
            node.result = result
            node.completed_at = datetime.utcnow()
            self.state.completed_nodes.add(node_id)
            self.state.current_node = None
            
            # Check if graph is complete
            if self.is_complete():
                self.state.status = "completed"
                
    def mark_failed(self, node_id: str, error: str) -> None:
        """Mark a node as failed."""
        node = self.nodes.get(node_id)
        if node:
            node.status = NodeStatus.FAILED
            node.error = error
            node.completed_at = datetime.utcnow()
            self.state.failed_nodes.add(node_id)
            self.state.current_node = None
            self.state.error = error
            
            # Propagate failure to dependent nodes
            self._propagate_failure(node_id)
            
    def _propagate_failure(self, failed_node_id: str) -> None:
        """Propagate failure to nodes that depend on the failed node."""
        for node in self.nodes.values():
            if failed_node_id in node.dependencies:
                if node.status == NodeStatus.PENDING:
                    node.status = NodeStatus.BLOCKED
                    node.error = f"Blocked by failed dependency: {failed_node_id}"
                    
    def can_finalize(self, node_id: str) -> bool:
        """Check if a node's result can be finalized (all validations passed)."""
        node = self.nodes.get(node_id)
        if not node:
            return False
        return node.status == NodeStatus.COMPLETED
    
    def is_complete(self) -> bool:
        """Check if all nodes are completed or failed."""
        for node in self.nodes.values():
            if node.status not in [NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.BLOCKED]:
                return False
        return True
    
    def has_failures(self) -> bool:
        """Check if any nodes have failed."""
        return len(self.state.failed_nodes) > 0
    
    def get_execution_order(self) -> List[str]:
        """Get a valid execution order using topological sort."""
        if self._order_cache:
            return self._order_cache
            
        # Kahn's algorithm for topological sort
        in_degree = {node_id: len(node.dependencies) for node_id, node in self.nodes.items()}
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        order = []
        
        while queue:
            node_id = queue.pop(0)
            order.append(node_id)
            
            # Reduce in-degree for dependent nodes
            for other_id, other_node in self.nodes.items():
                if node_id in other_node.dependencies:
                    in_degree[other_id] -= 1
                    if in_degree[other_id] == 0:
                        queue.append(other_id)
                        
        if len(order) != len(self.nodes):
            raise ValueError("Graph contains a cycle!")
            
        self._order_cache = order
        return order
    
    def get_state(self) -> Dict[str, Any]:
        """Get current graph state as dictionary."""
        return {
            'graph_id': self.graph_id,
            'status': self.state.status,
            'total_nodes': len(self.nodes),
            'completed': len(self.state.completed_nodes),
            'failed': len(self.state.failed_nodes),
            'current': self.state.current_node,
            'error': self.state.error,
            'nodes': {
                node_id: {
                    'name': node.name,
                    'status': node.status.value,
                    'result': node.result,
                    'error': node.error,
                }
                for node_id, node in self.nodes.items()
            }
        }
