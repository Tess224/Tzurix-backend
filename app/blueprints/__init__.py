"""
Tzurix Blueprints
HTTP routes - thin wrappers around services.
"""

from .public import public_bp
from .agents import agents_bp
from .trading import trading_bp
from .users import users_bp
from .leaderboard import leaderboard_bp
from .scoring import scoring_bp
from .cron import cron_bp

__all__ = [
    'public_bp',
    'agents_bp',
    'trading_bp',
    'users_bp',
    'leaderboard_bp',
    'scoring_bp',
    'cron_bp',
]
