"""
Scoring Service
Handles all score calculation logic with NO HTTP dependencies.
"""

from typing import Tuple
from dataclasses import dataclass
from datetime import datetime

from app.config import (
    DAILY_POINT_CAP, DAILY_SCORE_CAP, MIN_SCORE, MAX_SCORE,
    get_tier_max_score, UPI_WEIGHTS
)


@dataclass
class ScoreResult:
    """Result of a score calculation."""
    new_score: float
    raw_change: float
    capped_change: float
    was_capped: bool
    tier_ceiling_hit: bool = False


class ScoringService:
    """
    Core scoring logic for all agent types.
    Pure functions, no database access.
    """
    
    @staticmethod
    def apply_v1_score_change(
        current_score: float,
        raw_change: float,
        tier: str = 'alpha'
    ) -> ScoreResult:
        """
        V1: Apply ±5 point daily cap and tier ceiling.
        
        Args:
            current_score: Current score before change
            raw_change: Raw calculated change (can be any value)
            tier: Agent's tier for ceiling
        
        Returns:
            ScoreResult with new score and metadata
        """
        # Cap the change at ±5 points
        capped_change = max(-DAILY_POINT_CAP, min(DAILY_POINT_CAP, raw_change))
        was_capped = abs(raw_change) > DAILY_POINT_CAP
        
        # Calculate new score
        new_score = current_score + capped_change
        
        # Apply tier ceiling
        tier_ceiling_hit = False
        tier_max = get_tier_max_score(tier)
        if new_score > tier_max:
            new_score = tier_max
            tier_ceiling_hit = True
        
        # Apply floor
        if new_score < MIN_SCORE:
            new_score = MIN_SCORE
        
        return ScoreResult(
            new_score=round(new_score, 1),
            raw_change=raw_change,
            capped_change=capped_change,
            was_capped=was_capped or tier_ceiling_hit,
            tier_ceiling_hit=tier_ceiling_hit
        )
    
    @staticmethod
    def apply_legacy_cap(current_score: int, new_raw_score: int) -> int:
        """
        Legacy: Apply ±35% daily cap to score changes.
        Kept for backward compatibility.
        """
        if current_score == 0:
            return max(1, new_raw_score)
        
        change_percent = (new_raw_score - current_score) / current_score
        capped_change = max(-DAILY_SCORE_CAP, min(DAILY_SCORE_CAP, change_percent))
        new_score = int(current_score * (1 + capped_change))
        
        return max(1, new_score)
    
    @staticmethod
    def calculate_upi(
        effectiveness: float,
        efficiency: float,
        autonomy: float
    ) -> float:
        """
        Calculate Universal Performance Index for utility/coding agents.
        
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
    
    @staticmethod
    def calculate_tier_change_score(
        current_score: float,
        carry_percent: float = 0.5
    ) -> float:
        """
        Calculate score after tier change (50% carry by default).
        """
        return round(current_score * carry_percent, 1)
    
    @staticmethod
    def normalize_metric(value: float, min_val: float, max_val: float) -> float:
        """
        Normalize a metric to 0-100 range.
        """
        if max_val == min_val:
            return 50.0
        normalized = (value - min_val) / (max_val - min_val) * 100
        return round(min(100, max(0, normalized)), 2)
