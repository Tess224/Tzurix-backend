"""
Agents Blueprint
Agent registration, retrieval, and management.
"""

from flask import Blueprint, jsonify, request

from app.models import Agent
from app.config import get_tier_config, VALID_AGENT_TYPES, ARENA_TYPES
from app.services.agent import AgentService, CreateAgentRequest
from app.services.pricing import PricingService

agents_bp = Blueprint('agents', __name__, url_prefix='/api/agents')


@agents_bp.route('', methods=['GET'])
def get_agents():
    """
    List all registered agents.
    
    Query params:
        - sort: 'score', 'newest', 'name', 'volume', 'holders' (default: score)
        - type: filter by agent type (trading, social, defi, utility, coding)
        - arena_type: filter by arena type (trading, utility, coding)
        - category: filter by category (agent, individual)
        - tier: filter by tier (alpha, beta, omega)
        - limit: number of results (default: 50)
    """
    sort = request.args.get('sort', 'score')
    agent_type = request.args.get('type')
    arena_type = request.args.get('arena_type')
    category = request.args.get('category')
    tier = request.args.get('tier')
    limit = min(int(request.args.get('limit', 50)), 100)
    
    agents = AgentService.get_agents(
        sort=sort,
        agent_type=agent_type,
        arena_type=arena_type,
        category=category,
        tier=tier,
        limit=limit
    )
    
    return jsonify({
        'success': True,
        'count': len(agents),
        'agents': [AgentService.agent_to_dict(a) for a in agents]
    })


@agents_bp.route('/<int:agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get detailed info for a specific agent."""
    agent = AgentService.get_agent(agent_id)
    
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    return jsonify({
        'success': True,
        'agent': AgentService.agent_to_dict(agent)
    })


@agents_bp.route('/wallet/<wallet_address>', methods=['GET'])
def get_agent_by_wallet(wallet_address):
    """Get agent by their trading wallet address."""
    agent = AgentService.get_agent_by_wallet(wallet_address)
    
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    return jsonify({
        'success': True,
        'agent': AgentService.agent_to_dict(agent)
    })


@agents_bp.route('', methods=['POST'])
def register_agent():
    """
    Register a new AI agent.
    
    Request body:
    {
        "name": "My Trading Bot",                  # REQUIRED
        "creator_wallet": "CreatorWalletAddress",  # REQUIRED
        "wallet_address": "AgentWalletAddress",    # OPTIONAL
        "description": "Description",              # optional
        "type": "trading",                         # optional (trading, social, defi, utility, coding)
        "arena_type": "trading",                   # optional (trading, utility, coding)
        "tier": "alpha",                           # optional (alpha, beta, omega)
        "keywords": ["scheduling", "email"],       # optional - for utility/coding arenas
        "twitter_handle": "@mybot",                # optional
        "github_url": "https://github.com/...",    # optional
        "website_url": "https://..."               # optional
    }
    """
    data = request.get_json()
    
    # Validate required fields
    if not data.get('name'):
        return jsonify({'success': False, 'error': 'Missing required field: name'}), 400
    if not data.get('creator_wallet'):
        return jsonify({'success': False, 'error': 'Missing required field: creator_wallet'}), 400
    
    # Create request object
    create_request = CreateAgentRequest(
        name=data['name'],
        creator_wallet=data['creator_wallet'],
        wallet_address=data.get('wallet_address'),
        description=data.get('description'),
        agent_type=data.get('type', 'trading'),
        arena_type=data.get('arena_type', 'trading'),
        category=data.get('category', 'agent'),
        tier=data.get('tier', 'alpha'),
        keywords=data.get('keywords'),
        twitter_handle=data.get('twitter_handle'),
        github_url=data.get('github_url'),
        website_url=data.get('website_url'),
    )
    
    result = AgentService.create_agent(create_request)
    
    if not result.success:
        return jsonify({'success': False, 'error': result.error}), 400
    
    return jsonify({
        'success': True,
        'message': 'Agent registered successfully',
        'agent': AgentService.agent_to_dict(result.agent)
    }), 201


@agents_bp.route('/<int:agent_id>/arena', methods=['GET'])
def get_agent_arena_results(agent_id):
    """Get arena status and results for an agent."""
    agent = AgentService.get_agent(agent_id)
    
    if not agent:
        return jsonify({'success': False, 'error': 'Agent not found'}), 404
    
    tier_config = get_tier_config(agent.tier or 'alpha')
    
    # Determine arena status
    if agent.interface_validated:
        arena_status = 'ready'
    elif agent.interface_code:
        arena_status = 'pending_validation'
    else:
        arena_status = 'needs_interface'
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'agent_name': agent.name,
        'arena_type': agent.arena_type or 'trading',
        'keywords': agent.keywords or [],
        'tier': agent.tier or 'alpha',
        'tier_info': {
            'name': tier_config['name'],
            'max_score': tier_config['max_score'],
            'difficulty': tier_config['difficulty'],
        },
        'current_score': agent.current_score,
        'score_ceiling': tier_config['max_score'],
        'upi_breakdown': {
            'effectiveness': agent.effectiveness_score,
            'efficiency': agent.efficiency_score,
            'autonomy': agent.autonomy_score,
        } if agent.arena_type in ['utility', 'coding'] else None,
        'last_arena_run': agent.last_arena_run.isoformat() if agent.last_arena_run else None,
        'has_interface': bool(agent.interface_code),
        'interface_validated': agent.interface_validated or False,
        'interface_version': agent.interface_version,
        'arena_status': arena_status,
        'message': _get_arena_status_message(arena_status, agent.arena_type)
    })


@agents_bp.route('/<int:agent_id>/tier', methods=['POST'])
def change_agent_tier(agent_id):
    """
    Change an agent's tier.
    50% score carry on tier change.
    
    Request body:
    {
        "tier": "beta",
        "creator_wallet": "CreatorWalletAddress"
    }
    """
    data = request.get_json()
    
    new_tier = data.get('tier', '')
    creator_wallet = data.get('creator_wallet')
    
    if not creator_wallet:
        return jsonify({'success': False, 'error': 'Missing creator_wallet'}), 400
    
    result = AgentService.change_tier(agent_id, creator_wallet, new_tier)
    
    if not result['success']:
        status_code = 403 if 'authorized' in result['error'] else 400
        return jsonify(result), status_code
    
    agent = AgentService.get_agent(agent_id)
    
    return jsonify({
        'success': True,
        'message': f"Tier changed from {result['old_tier']} to {result['new_tier']}",
        **result,
        'agent': AgentService.agent_to_dict(agent)
    })


@agents_bp.route('/<int:agent_id>/interface', methods=['POST'])
def upload_agent_interface(agent_id):
    """
    Upload decision interface code for arena testing.
    
    Request body:
    {
        "creator_wallet": "CreatorWalletAddress",
        "interface_code": "def decide(market_data, portfolio):\\n    ...",
        "interface_type": "simple"
    }
    """
    data = request.get_json()
    
    creator_wallet = data.get('creator_wallet')
    interface_code = data.get('interface_code')
    interface_type = data.get('interface_type', 'simple')
    
    if not creator_wallet:
        return jsonify({'success': False, 'error': 'Missing creator_wallet'}), 400
    if not interface_code:
        return jsonify({'success': False, 'error': 'Missing interface_code'}), 400
    
    result = AgentService.update_interface(
        agent_id, creator_wallet, interface_code, interface_type
    )
    
    if not result['success']:
        status_code = 403 if 'authorized' in result['error'] else 400
        return jsonify(result), status_code
    
    return jsonify({
        **result,
        'next_step': 'Interface will be validated and tested in the next arena run'
    })


@agents_bp.route('/<int:agent_id>/keywords', methods=['POST'])
def update_agent_keywords(agent_id):
    """
    Update agent keywords for template routing.
    
    Request body:
    {
        "creator_wallet": "CreatorWalletAddress",
        "keywords": ["scheduling", "email", "task_tracking"]
    }
    """
    from app.models import db
    
    data = request.get_json()
    
    creator_wallet = data.get('creator_wallet')
    keywords = data.get('keywords', [])
    
    if not creator_wallet:
        return jsonify({'success': False, 'error': 'Missing creator_wallet'}), 400
    
    if not isinstance(keywords, list) or len(keywords) > 5:
        return jsonify({'success': False, 'error': 'Keywords must be a list of up to 5 items'}), 400
    
    agent = AgentService.get_agent(agent_id)
    if not agent:
        return jsonify({'success': False, 'error': 'Agent not found'}), 404
    
    if agent.creator_wallet != creator_wallet:
        return jsonify({'success': False, 'error': 'Not authorized. Must be agent creator.'}), 403
    
    agent.keywords = keywords
    db.session.commit()
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'keywords': keywords
    })


def _get_arena_status_message(status: str, arena_type: str) -> str:
    """Get user-friendly message for arena status."""
    if status == 'ready':
        return 'Arena runs daily at 00:00 UTC'
    elif status == 'pending_validation':
        return 'Interface will be validated in the next arena run'
    else:
        if arena_type == 'utility':
            return 'Upload a decide() function to enable productivity testing'
        elif arena_type == 'coding':
            return 'Upload a decide() function to enable code challenge testing'
        else:
            return 'Upload a decide() function to enable arena testing'
