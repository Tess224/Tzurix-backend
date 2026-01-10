"""
Leaderboard Blueprint
Top agents by various metrics.
"""

from flask import Blueprint, jsonify, request

from app.models import Agent
from app.config import VALID_AGENT_TYPES, ARENA_TYPES
from app.services.agent import AgentService

leaderboard_bp = Blueprint('leaderboard', __name__, url_prefix='/api/leaderboard')


@leaderboard_bp.route('', methods=['GET'])
def get_leaderboard():
    """
    Get top agents by various metrics.
    
    Query params:
        - metric: 'score', 'gainers', 'volume', 'holders' (default: score)
        - type: filter by agent type (optional)
        - arena_type: filter by arena type (optional)
        - tier: filter by tier (optional)
        - limit: number of results (default: 10, max: 50)
    """
    metric = request.args.get('metric', 'score')
    agent_type = request.args.get('type')
    arena_type = request.args.get('arena_type')
    tier = request.args.get('tier')
    limit = min(int(request.args.get('limit', 10)), 50)
    
    query = Agent.query.filter_by(is_active=True)
    
    # Apply filters
    if agent_type and agent_type in VALID_AGENT_TYPES:
        query = query.filter_by(agent_type=agent_type)
    
    if arena_type and arena_type in ARENA_TYPES:
        query = query.filter_by(arena_type=arena_type)
    
    if tier and tier.lower() in ['alpha', 'beta', 'omega']:
        query = query.filter_by(tier=tier.lower())
    
    # Handle special metrics
    if metric == 'gainers':
        agents = query.all()
        agents_with_gain = []
        for a in agents:
            if a.previous_score and a.previous_score > 0:
                gain = (a.current_score - a.previous_score) / a.previous_score * 100
            else:
                gain = 0
            agents_with_gain.append((a, gain))
        agents_with_gain.sort(key=lambda x: x[1], reverse=True)
        top_agents = [a for a, _ in agents_with_gain[:limit]]
        
        return jsonify({
            'success': True,
            'metric': metric,
            'count': len(top_agents),
            'agents': [AgentService.agent_to_dict(a) for a in top_agents]
        })
    
    elif metric == 'losers':
        agents = query.all()
        agents_with_loss = []
        for a in agents:
            if a.previous_score and a.previous_score > 0:
                loss = (a.current_score - a.previous_score) / a.previous_score * 100
            else:
                loss = 0
            agents_with_loss.append((a, loss))
        agents_with_loss.sort(key=lambda x: x[1])  # Ascending (most negative first)
        top_agents = [a for a, _ in agents_with_loss[:limit]]
        
        return jsonify({
            'success': True,
            'metric': metric,
            'count': len(top_agents),
            'agents': [AgentService.agent_to_dict(a) for a in top_agents]
        })
    
    # Standard sorting
    if metric == 'score':
        query = query.order_by(Agent.current_score.desc())
    elif metric == 'volume':
        query = query.order_by(Agent.volume_24h.desc())
    elif metric == 'holders':
        query = query.order_by(Agent.holders.desc())
    else:
        query = query.order_by(Agent.current_score.desc())
    
    agents = query.limit(limit).all()
    
    return jsonify({
        'success': True,
        'metric': metric,
        'count': len(agents),
        'agents': [AgentService.agent_to_dict(a) for a in agents]
    })


@leaderboard_bp.route('/by-arena', methods=['GET'])
def get_leaderboard_by_arena():
    """Get top agents for each arena type."""
    limit = min(int(request.args.get('limit', 5)), 20)
    
    result = {}
    
    for arena in ARENA_TYPES:
        agents = Agent.query.filter_by(
            is_active=True,
            arena_type=arena
        ).order_by(Agent.current_score.desc()).limit(limit).all()
        
        result[arena] = [AgentService.agent_to_dict(a) for a in agents]
    
    return jsonify({
        'success': True,
        'leaderboards': result
    })


@leaderboard_bp.route('/by-tier', methods=['GET'])
def get_leaderboard_by_tier():
    """Get top agents for each tier."""
    limit = min(int(request.args.get('limit', 5)), 20)
    
    result = {}
    
    for tier in ['alpha', 'beta', 'omega']:
        agents = Agent.query.filter_by(
            is_active=True,
            tier=tier
        ).order_by(Agent.current_score.desc()).limit(limit).all()
        
        result[tier] = [AgentService.agent_to_dict(a) for a in agents]
    
    return jsonify({
        'success': True,
        'leaderboards': result
    })
