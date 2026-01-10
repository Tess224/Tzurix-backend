"""
Sandbox Executor
Safely execute agent code in isolated environment.

MVP: Mock implementation for testing.
V2: Docker-based real execution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import time
import random
import hashlib
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of sandbox execution."""
    success: bool
    output: Any = None
    elapsed_ms: int = 0
    retries: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SandboxExecutor(ABC):
    """
    Abstract base class for sandbox execution.
    Allows swapping implementations (mock -> Docker -> cloud).
    """
    
    @abstractmethod
    def execute(
        self,
        code: str,
        input_data: Dict[str, Any],
        timeout: int = 30
    ) -> ExecutionResult:
        """
        Execute agent code with given input.
        
        Args:
            code: Agent's interface code
            input_data: Template input data
            timeout: Maximum execution time in seconds
        
        Returns:
            ExecutionResult with output or error
        """
        raise NotImplementedError


class MockSandbox(SandboxExecutor):
    """
    Mock sandbox for MVP testing.
    Simulates execution with deterministic-ish outputs.
    
    Features:
    - Deterministic outputs based on code hash (same code = same scores)
    - Realistic timing simulation
    - Configurable failure rates for testing
    """
    
    def __init__(
        self,
        failure_rate: float = 0.05,  # 5% chance of failure
        min_latency_ms: int = 50,
        max_latency_ms: int = 500,
        seed: Optional[int] = None
    ):
        self.failure_rate = failure_rate
        self.min_latency_ms = min_latency_ms
        self.max_latency_ms = max_latency_ms
        self.rng = random.Random(seed)
    
    def execute(
        self,
        code: str,
        input_data: Dict[str, Any],
        timeout: int = 30
    ) -> ExecutionResult:
        """
        Mock execution with deterministic outputs.
        """
        start_time = time.time()
        
        # Simulate latency
        latency = self.rng.randint(self.min_latency_ms, self.max_latency_ms)
        time.sleep(latency / 1000)
        
        # Simulate random failure
        if self.rng.random() < self.failure_rate:
            return ExecutionResult(
                success=False,
                elapsed_ms=latency,
                error='Simulated execution failure'
            )
        
        # Generate deterministic output based on code hash
        code_hash = hashlib.md5(code.encode()).hexdigest()
        seed_value = int(code_hash[:8], 16)
        output_rng = random.Random(seed_value)
        
        # Generate mock output
        output = self._generate_mock_output(input_data, output_rng)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return ExecutionResult(
            success=True,
            output=output,
            elapsed_ms=elapsed_ms,
            retries=0,
            metadata={'mock': True, 'code_hash': code_hash[:8]}
        )
    
    def _generate_mock_output(
        self,
        input_data: Dict[str, Any],
        rng: random.Random
    ) -> Dict[str, Any]:
        """
        Generate mock output based on input template type.
        """
        # Detect template type from input structure
        if 'existing_events' in input_data:
            # Scheduling template
            return {
                'all_scheduled': rng.random() > 0.2,  # 80% success
                'no_conflicts': rng.random() > 0.15,  # 85% no conflicts
                'events_created': rng.randint(1, 5),
            }
        
        elif 'code' in input_data or 'tests' in input_data:
            # Coding template
            tests_total = input_data.get('tests_total', 5)
            tests_passed = rng.randint(int(tests_total * 0.5), tests_total)
            return {
                'tests_passed': tests_passed,
                'tests_total': tests_total,
                'coverage': rng.uniform(0.5, 0.95),
                'compile_success': rng.random() > 0.1,
            }
        
        elif 'email' in str(input_data).lower():
            # Email template
            return {
                'summary_accurate': rng.random() > 0.2,
                'tone_appropriate': rng.random() > 0.1,
                'key_points_extracted': rng.randint(2, 5),
            }
        
        elif 'task' in str(input_data).lower():
            # Task management template
            return {
                'task_completed': rng.random() > 0.15,
                'priority_correct': rng.random() > 0.2,
                'deadline_met': rng.random() > 0.25,
            }
        
        else:
            # Generic template
            return {
                'task_success': rng.random() > 0.2,
                'quality_score': rng.uniform(0.6, 1.0),
                'steps_completed': rng.randint(1, 5),
            }


class DockerSandbox(SandboxExecutor):
    """
    Docker-based sandbox for real execution.
    Placeholder for V2 implementation.
    """
    
    def __init__(
        self,
        image: str = 'python:3.11-slim',
        memory_limit: str = '512m',
        cpu_limit: float = 0.5,
        network_disabled: bool = True
    ):
        self.image = image
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.network_disabled = network_disabled
        
        # Check if Docker is available
        self._check_docker()
    
    def _check_docker(self):
        """Check if Docker is available."""
        try:
            import docker
            self.client = docker.from_env()
            logger.info("Docker sandbox initialized")
        except Exception as e:
            logger.warning(f"Docker not available: {e}. Falling back to mock.")
            self.client = None
    
    def execute(
        self,
        code: str,
        input_data: Dict[str, Any],
        timeout: int = 30
    ) -> ExecutionResult:
        """
        Execute code in Docker container.
        Falls back to mock if Docker unavailable.
        """
        if self.client is None:
            # Fall back to mock
            mock = MockSandbox()
            return mock.execute(code, input_data, timeout)
        
        # TODO: Implement real Docker execution in V2
        # For now, use mock
        logger.warning("Docker execution not yet implemented, using mock")
        mock = MockSandbox()
        return mock.execute(code, input_data, timeout)


# Default sandbox factory
def create_sandbox(sandbox_type: str = 'mock') -> SandboxExecutor:
    """
    Factory function to create appropriate sandbox.
    
    Args:
        sandbox_type: 'mock' or 'docker'
    
    Returns:
        SandboxExecutor instance
    """
    if sandbox_type == 'docker':
        return DockerSandbox()
    else:
        return MockSandbox()
