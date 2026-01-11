"""
Public Blueprint
Health checks, service info, and tier configurations.
"""

import time
from flask import Blueprint, jsonify

from app.config import (
    VERSION, VERSION_NAME, FEATURES, STARTING_SCORE, DAILY_POINT_CAP,
    TOTAL_SUPPLY, TIERS, ARENA_TYPES
)
from app.services.pricing import PricingService

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def home():
    """API root - shows service info."""
    return jsonify({
        'service': 'Tzurix MVP API',
        'version': VERSION,
        'version_name': VERSION_NAME,
        'description': 'AI Agent Performance Exchange - Where Price = Score',
        'network': 'Solana Devnet',
        'status': 'online',
        'features': FEATURES,
        'constants': {
            'starting_score': STARTING_SCORE,
            'daily_point_cap': DAILY_POINT_CAP,
            'total_supply': TOTAL_SUPPLY,
            'tiers': list(TIERS.keys()),
            'arena_types': ARENA_TYPES,
        },
        'endpoints': {
            'agents': '/api/agents',
            'tiers': '/api/tiers',
            'agent_detail': '/api/agents/<id>',
            'agent_arena': '/api/agents/<id>/arena',
            'register_agent': 'POST /api/agents',
            'set_github': 'POST /api/agents/<id>/github',
                        'validate_github': 'GET /api/agents/<id>/github/validate',
                        'preview_github': 'GET /api/agents/<id>/github/preview',
            'change_tier': 'POST /api/agents/<id>/tier',
            'leaderboard': '/api/leaderboard',
            'trading': '/api/trade/*',
        }
    })


@public_bp.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': int(time.time()),
        'database': 'connected',
        'sol_price_usd': PricingService.get_sol_price_usd(),
        'version': VERSION
    })


@public_bp.route('/api/tiers')
def get_tiers():
    """Get all tier configurations."""
    return jsonify({
        'success': True,
        'tiers': {
            name: {
                'name': config['name'],
                'emoji': config['emoji'],
                'difficulty': config['difficulty'],
                'max_score': config['max_score'],
                'description': config['description'],
            }
            for name, config in TIERS.items()
        }
    })


@public_bp.route('/api/arena-types')
def get_arena_types():
    """Get all arena type configurations."""
    from app.config import UTILITY_KEYWORD_TEMPLATES, CODING_KEYWORD_TEMPLATES
    
    return jsonify({
        'success': True,
        'arena_types': {
            'trading': {
                'name': 'Trading',
                'description': 'Tests trading performance against market scenarios',
                'keywords': ['trading', 'defi'],
            },
            'utility': {
                'name': 'Utility / Productivity',
                'description': 'Tests task completion for productivity agents',
                'keywords': list(UTILITY_KEYWORD_TEMPLATES.keys()),
            },
            'coding': {
                'name': 'Coding / Development',
                'description': 'Tests code quality and problem solving',
                'keywords': list(CODING_KEYWORD_TEMPLATES.keys()),
            },
        }
    })
