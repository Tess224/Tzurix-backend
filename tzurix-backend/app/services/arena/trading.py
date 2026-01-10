"""
Trading Arena Engine
Tests trading agents against historical market scenarios.
"""

from typing import List, Dict, Any
from datetime import datetime
import random
import logging

from app.models import Agent
from app.config import get_tier_config
from .base import BaseArenaEngine, ArenaResult
from .sandbox import SandboxExecutor, MockSandbox

logger = logging.getLogger(__name__)


# Trading scenario templates
TRADING_SCENARIOS = {
    'flash_crash': {
        'name': 'Flash Crash Recovery',
        'description': 'Sudden 20% drop followed by recovery',
        'difficulty': 1.2,
        'input': {
            'scenario': 'flash_crash',
            'initial_price': 100,
            'drop_percent': 20,
            'recovery_time_minutes': 15,
            'portfolio': {'balance': 10000, 'positions': []},
        },
        'scoring': {
            'weight_preservation': 0.4,  # Did they preserve capital?
            'weight_recovery': 0.3,      # Did they catch the recovery?
            'weight_timing': 0.3,        # Timing of actions
        }
    },
    'liquidity_trap': {
        'name': 'Liquidity Trap',
        'description': 'Low liquidity scenario with wide spreads',
        'difficulty': 1.3,
        'input': {
            'scenario': 'liquidity_trap',
            'spread_percent': 5,
            'depth_ratio': 0.3,
            'portfolio': {'balance': 10000, 'positions': []},
        },
        'scoring': {
            'weight_slippage': 0.5,    # Slippage management
            'weight_patience': 0.3,    # Waiting for better fills
            'weight_sizing': 0.2,      # Position sizing
        }
    },
    'trending_market': {
        'name': 'Strong Trend',
        'description': 'Clear uptrend or downtrend scenario',
        'difficulty': 0.9,
        'input': {
            'scenario': 'trending',
            'trend_direction': 'up',
            'trend_strength': 0.7,
            'duration_minutes': 60,
            'portfolio': {'balance': 10000, 'positions': []},
        },
        'scoring': {
            'weight_trend_capture': 0.5,
            'weight_risk_management': 0.3,
            'weight_exit_timing': 0.2,
        }
    },
    'sideways_chop': {
        'name': 'Sideways Market',
        'description': 'Range-bound choppy price action',
        'difficulty': 1.1,
        'input': {
            'scenario': 'sideways',
            'range_percent': 5,
            'chop_frequency': 'high',
            'portfolio': {'balance': 10000, 'positions': []},
        },
        'scoring': {
            'weight_loss_avoidance': 0.5,
            'weight_patience': 0.3,
            'weight_range_recognition': 0.2,
        }
    },
    'news_spike': {
        'name': 'News Event Spike',
        'description': 'Sudden volatility from news event',
        'difficulty': 1.4,
        'input': {
            'scenario': 'news_spike',
            'spike_magnitude': 15,
            'spike_duration_seconds': 30,
            'follow_through': True,
            'portfolio': {'balance': 10000, 'positions': []},
        },
        'scoring': {
            'weight_reaction_time': 0.3,
            'weight_risk_management': 0.4,
            'weight_profit_capture': 0.3,
        }
    },
}

# Tier-based scenario selection
TIER_SCENARIOS = {
    'alpha': ['trending_market', 'sideways_chop', 'flash_crash'],
    'beta': ['trending_market', 'sideways_chop', 'flash_crash', 'liquidity_trap'],
    'omega': list(TRADING_SCENARIOS.keys()),  # All scenarios
}


class TradingArenaEngine(BaseArenaEngine):
    """
    Arena engine for trading agents.
    Tests against historical market scenarios.
    """
    
    arena_type = 'trading'
    
    def __init__(self, sandbox: SandboxExecutor = None):
        self.sandbox = sandbox or MockSandbox()
    
    def run(self, agent: Agent) -> ArenaResult:
        """
        Run trading arena for agent.
        
        Args:
            agent: Trading agent to test
        
        Returns:
            ArenaResult with score and details
        """
        start_time = datetime.utcnow()
        errors = []
        
        # Validate interface
        is_valid, error = self.validate_interface(agent)
        if not is_valid:
            return ArenaResult(
                agent_id=agent.id,
                arena_type=self.arena_type,
                score=0,
                raw_score=0,
                errors=[error]
            )
        
        # Select scenarios based on tier
        tier = agent.tier or 'alpha'
        available_scenarios = TIER_SCENARIOS.get(tier, TIER_SCENARIOS['alpha'])
        
        # Run 3-5 scenarios
        num_scenarios = random.randint(3, 5)
        selected_scenarios = random.sample(
            available_scenarios,
            min(num_scenarios, len(available_scenarios))
        )
        
        template_scores = {}
        total_score = 0
        total_difficulty = 0
        
        for scenario_name in selected_scenarios:
            scenario = TRADING_SCENARIOS[scenario_name]
            
            try:
                # Execute agent against scenario
                result = self.sandbox.execute(
                    code=agent.interface_code,
                    input_data=scenario['input'],
                    timeout=30
                )
                
                if result.success:
                    # Score the result
                    score = self._score_scenario_result(scenario, result.output)
                    difficulty = scenario['difficulty']
                    
                    # Apply difficulty modifier
                    adjusted_score = score * difficulty
                    
                    template_scores[scenario_name] = {
                        'raw_score': score,
                        'difficulty': difficulty,
                        'adjusted_score': adjusted_score,
                        'execution_time_ms': result.elapsed_ms
                    }
                    
                    total_score += adjusted_score
                    total_difficulty += difficulty
                else:
                    errors.append(f"{scenario_name}: {result.error}")
                    template_scores[scenario_name] = {
                        'raw_score': 0,
                        'error': result.error
                    }
                    
            except Exception as e:
                logger.error(f"Error running scenario {scenario_name}: {e}")
                errors.append(f"{scenario_name}: {str(e)}")
        
        # Calculate final score
        if total_difficulty > 0:
            raw_score = (total_score / total_difficulty) * 100
        else:
            raw_score = 0
        
        # Apply tier ceiling
        tier_config = get_tier_config(tier)
        final_score = min(raw_score, tier_config['max_score'])
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return ArenaResult(
            agent_id=agent.id,
            arena_type=self.arena_type,
            score=round(final_score, 2),
            raw_score=round(raw_score, 2),
            templates_run=selected_scenarios,
            template_scores=template_scores,
            execution_time_ms=execution_time_ms,
            errors=errors
        )
    
    def _score_scenario_result(
        self,
        scenario: Dict[str, Any],
        output: Dict[str, Any]
    ) -> float:
        """
        Score agent's output for a scenario.
        Uses scenario-specific scoring weights.
        """
        if not output:
            return 0
        
        scoring = scenario.get('scoring', {})
        total_score = 0
        total_weight = 0
        
        # Check for standard output fields
        if 'task_success' in output:
            success_weight = scoring.get('weight_preservation', 0.3)
            total_score += (1.0 if output['task_success'] else 0) * success_weight
            total_weight += success_weight
        
        if 'quality_score' in output:
            quality_weight = scoring.get('weight_recovery', 0.3)
            total_score += output['quality_score'] * quality_weight
            total_weight += quality_weight
        
        if 'steps_completed' in output:
            steps_weight = scoring.get('weight_timing', 0.2)
            # Normalize steps (assume max 5)
            normalized = min(output['steps_completed'] / 5, 1.0)
            total_score += normalized * steps_weight
            total_weight += steps_weight
        
        # Add randomness for mock (will be replaced with real scoring)
        if total_weight == 0:
            return random.uniform(0.5, 0.9)
        
        return total_score / total_weight if total_weight > 0 else 0
