"""
Planner Module

Creates executable plans from intents and task graphs.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from ..models.intent import Intent, TaskComplexity
from .task_graph import TaskGraph, TaskNode


@dataclass
class PlanStep:
    """A step in an execution plan."""
    name: str
    description: str
    agent_role: str
    tools: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    requires_approval: bool = False
    

@dataclass 
class Plan:
    """An executable plan."""
    intent: Intent
    steps: List[PlanStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_next_step(self, completed: List[str]) -> Optional[PlanStep]:
        """Get the next executable step given completed steps."""
        completed_set = set(completed)
        for step in self.steps:
            if step.name not in completed_set:
                # Check if all dependencies are met
                if all(dep in completed_set for dep in step.dependencies):
                    return step
        return None
    
    def is_complete(self, completed: List[str]) -> bool:
        """Check if all steps are complete."""
        return all(step.name in completed for step in self.steps)


class Planner:
    """Creates executable plans from intents."""
    
    # Default step templates by intent type
    STEP_TEMPLATES = {
        'create': [
            PlanStep('analyze', 'Analyze requirements and context', 'architect', ['read_file', 'search']),
            PlanStep('plan', 'Create implementation plan', 'architect', []),
            PlanStep('implement', 'Write code changes', 'developer', ['write_file', 'edit_file', 'shell']),
            PlanStep('test', 'Run tests', 'tester', ['test', 'shell']),
            PlanStep('review', 'Code review', 'code_reviewer', ['read_file', 'git']),
        ],
        'modify': [
            PlanStep('analyze', 'Analyze current code and requirements', 'architect', ['read_file']),
            PlanStep('plan', 'Plan modifications', 'architect', []),
            PlanStep('implement', 'Apply modifications', 'developer', ['edit_file', 'write_file']),
            PlanStep('test', 'Verify changes with tests', 'tester', ['test', 'shell']),
            PlanStep('review', 'Review changes', 'code_reviewer', ['read_file']),
        ],
        'test': [
            PlanStep('setup', 'Setup test environment', 'tester', ['shell']),
            PlanStep('execute', 'Run tests', 'tester', ['test', 'shell']),
            PlanStep('report', 'Generate test report', 'tester', []),
        ],
        'complex': [
            PlanStep('analyze', 'Comprehensive analysis', 'architect', ['read_file', 'search']),
            PlanStep('design', 'Design solution architecture', 'architect', []),
            PlanStep('implement', 'Implement solution', 'developer', ['write_file', 'shell']),
            PlanStep('test', 'Run comprehensive tests', 'tester', ['test', 'shell']),
            PlanStep('review', 'Full code review', 'code_reviewer', ['read_file', 'git']),
            PlanStep('validate', 'Final validation', 'tester', ['test', 'shell']),
        ],
    }
    
    def __init__(self):
        pass
    
    def create_plan(self, intent: Intent, context: Optional[Dict[str, Any]] = None) -> Plan:
        """
        Create an executable plan from an intent.
        
        Args:
            intent: The analyzed intent
            context: Optional context about current state
            
        Returns:
            Plan object with executable steps
        """
        # Select template based on intent type
        template_key = intent.type.value
        if template_key not in self.STEP_TEMPLATES:
            template_key = 'complex'
            
        # Clone template steps
        base_steps = self.STEP_TEMPLATES.get(template_key, self.STEP_TEMPLATES['complex'])
        steps = []
        
        for i, base_step in enumerate(base_steps):
            step = PlanStep(
                name=base_step.name,
                description=f"{base_step.description} for: {intent.description[:100]}",
                agent_role=base_step.agent_role,
                tools=base_step.tools.copy(),
                dependencies=[s.name for s in steps[:i]] if i > 0 else [],
                timeout_seconds=base_step.timeout_seconds,
                requires_approval=base_step.requires_approval,
            )
            steps.append(step)
            
        # Adjust based on complexity
        if intent.complexity == TaskComplexity.SIMPLE:
            # Reduce steps for simple tasks
            steps = [s for s in steps if s.name in ['analyze', 'implement', 'test']]
            # Remove dependencies for simpler flow
            for i, step in enumerate(steps):
                step.dependencies = []
                
        elif intent.complexity == TaskComplexity.COMPLEX:
            # Add extra validation steps for complex tasks
            steps.append(PlanStep(
                'security_check', 
                'Security vulnerability scan', 
                'security_reviewer', 
                ['read_file', 'search'],
                dependencies=['review']
            ))
            
        plan = Plan(
            intent=intent,
            steps=steps,
            metadata={
                'complexity': intent.complexity.value,
                'confidence': intent.confidence,
                'entities': intent.entities,
            }
        )
        
        return plan
    
    def adapt_plan(self, plan: Plan, observation: Dict[str, Any]) -> Plan:
        """
        Adapt a plan based on execution observations.
        
        Args:
            plan: Current plan
            observation: Observation from execution
            
        Returns:
            Adapted plan
        """
        # If we observe failures, add debug steps
        if observation.get('failed', False):
            error_info = observation.get('error', '')
            
            # Insert debug step before the failed step
            failed_step = observation.get('step', 'implement')
            debug_step = PlanStep(
                'debug',
                f'Debug failure: {error_info[:50]}',
                'debugger',
                ['read_file', 'shell', 'test'],
                dependencies=[],
                requires_approval=False,
            )
            
            # Find where to insert
            for i, step in enumerate(plan.steps):
                if step.name == failed_step:
                    plan.steps.insert(i, debug_step)
                    # Update dependencies
                    step.dependencies.append('debug')
                    break
                    
        return plan
