"""
Base Arena Engine
Abstract base class and common functionality for all arena types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.models import Agent
from app.config import UPI_WEIGHTS


@dataclass
class ArenaResult:
    """Result of an arena run."""
    agent_id: int
    arena_type: str
    score: float
    raw_score: float
    
    # UPI breakdown (for utility/coding)
    effectiveness: float = 0
    efficiency: float = 0
    autonomy: float = 0
    
    # Execution details
    templates_run: List[str] = field(default_factory=list)
    template_scores: Dict[str, float] = field(default_factory=dict)
    execution_time_ms: int = 0
    errors: List[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            'agent_id': self.agent_id,
            'arena_type': self.arena_type,
            'score': self.score,
            'raw_score': self.raw_score,
            'upi_breakdown': {
                'effectiveness': self.effectiveness,
                'efficiency': self.efficiency,
                'autonomy': self.autonomy,
            },
            'templates_run': self.templates_run,
            'template_scores': self.template_scores,
            'execution_time_ms': self.execution_time_ms,
            'errors': self.errors,
            'created_at': self.created_at.isoformat()
        }


class BaseArenaEngine(ABC):
    """
    Abstract base class for arena engines.
    Each arena type implements its own run() method.
    """
    
    arena_type: str = 'base'
    
    @abstractmethod
    def run(self, agent: Agent) -> ArenaResult:
        """
        Run the arena for a given agent.
        
        Args:
            agent: Agent to test
        
        Returns:
            ArenaResult with score and details
        """
        raise NotImplementedError
    
    def calculate_upi(
        self,
        effectiveness: float,
        efficiency: float,
        autonomy: float
    ) -> float:
        """
        Calculate Universal Performance Index.
        
        Args:
            effectiveness: Task completion rate (0-100)
            efficiency: Time/resource efficiency (0-100)
            autonomy: Independence level (0-100)
        
        Returns:
            UPI score (0-100)
        """
        upi = (
            effectiveness * UPI_WEIGHTS['effectiveness'] +
            efficiency * UPI_WEIGHTS['efficiency'] +
            autonomy * UPI_WEIGHTS['autonomy']
        )
        return round(min(100, max(0, upi)), 2)
    
    def validate_interface(self, agent: Agent) -> tuple[bool, Optional[str]]:
        """
        Validate that agent has a valid interface for testing.
        
        Returns:
            (is_valid, error_message)
        """
        if not agent.interface_code:
            return False, 'No interface code uploaded'
        
        if 'def decide(' not in agent.interface_code:
            return False, 'Interface must contain decide() function'
        
        return True, None
    
    def select_templates(self, keywords: List[str], template_map: Dict[str, List[str]], count: int = 3) -> List[str]:
        """
        Select templates based on agent keywords.
        
        Args:
            keywords: Agent's registered keywords
            template_map: Keyword to template mapping
            count: Number of templates to select
        
        Returns:
            List of template names
        """
        available_templates = []
        
        for keyword in keywords:
            if keyword in template_map:
                available_templates.extend(template_map[keyword])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_templates = []
        for t in available_templates:
            if t not in seen:
                seen.add(t)
                unique_templates.append(t)
        
        # Return up to 'count' templates
        return unique_templates[:count]


class ArenaOrchestrator:
    """
    Orchestrates arena runs across all agent types.
    Routes to appropriate engine based on arena_type.
    """
    
    def __init__(self):
        # Import here to avoid circular imports
        from .trading import TradingArenaEngine
        from .utility import UtilityArenaEngine
        from .coding import CodingArenaEngine
        
        self.engines = {
            'trading': TradingArenaEngine(),
            'utility': UtilityArenaEngine(),
            'coding': CodingArenaEngine(),
        }
    
    def run_arena(self, agent: Agent) -> ArenaResult:
        """
        Run appropriate arena for agent.
        
        Args:
            agent: Agent to test
        
        Returns:
            ArenaResult
        """
        arena_type = agent.arena_type or 'trading'
        
        if arena_type not in self.engines:
            raise ValueError(f"Unknown arena type: {arena_type}")
        
        return self.engines[arena_type].run(agent)
    
    def run_all_agents(self, agents: List[Agent]) -> List[ArenaResult]:
        """
        Run arena for multiple agents.
        
        Args:
            agents: List of agents to test
        
        Returns:
            List of ArenaResults
        """
        results = []
        for agent in agents:
            try:
                result = self.run_arena(agent)
                results.append(result)
            except Exception as e:
                # Create error result
                results.append(ArenaResult(
                    agent_id=agent.id,
                    arena_type=agent.arena_type or 'trading',
                    score=0,
                    raw_score=0,
                    errors=[str(e)]
                ))
        return results
