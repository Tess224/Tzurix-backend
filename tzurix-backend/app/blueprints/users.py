"""
Users Blueprint
User profile and holdings endpoints.
"""

from flask import Blueprint, jsonify, request

from app.models import User, Holding, Trade
from app.services.trading import TradingService
from app.services.pricing import PricingService

users_bp = Blueprint('users', __name__, url_prefix='/api/user')


@users_bp.route('/<wallet_address>', methods=['GET'])
def get_user(wallet_address):
    """Get user profile by wallet address."""
    user = User.query.filter_by(wallet_address=wallet_address).first()
    
    if not user:
        return jsonify({
            'success': False,
            'error': 'User not found'
        }), 404
    
    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'wallet_address': user.wallet_address,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }
    })


@users_bp.route('/<wallet_address>/holdings', methods=['GET'])
def get_user_holdings(wallet_address):
    """Get all token holdings for a user."""
    user = User.query.filter_by(wallet_address=wallet_address).first()
    
    if not user:
        return jsonify({
            'success': True,
            'holdings': [],
            'total_value_sol': 0,
            'total_value_usd': 0
        })
    
    holdings = Holding.query.filter_by(user_id=user.id).all()
    holdings_data = [
        TradingService.holding_to_dict(h) 
        for h in holdings 
        if h.token_amount > 0
    ]
    
    total_value_sol = sum(h['current_value_sol'] for h in holdings_data)
    total_value_usd = sum(h['current_value_usd'] for h in holdings_data)
    
    return jsonify({
        'success': True,
        'wallet_address': wallet_address,
        'holdings': holdings_data,
        'total_value_sol': total_value_sol,
        'total_value_usd': total_value_usd
    })


@users_bp.route('/<wallet_address>/transactions', methods=['GET'])
def get_user_transactions(wallet_address):
    """Get transaction history for a user."""
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    agent_id = request.args.get('agent_id', type=int)
    
    query = Trade.query.filter_by(trader_wallet=wallet_address)
    
    if agent_id:
        query = query.filter_by(agent_id=agent_id)
    
    total = query.count()
    trades = query.order_by(Trade.created_at.desc()).offset(offset).limit(limit).all()
    
    return jsonify({
        'success': True,
        'wallet_address': wallet_address,
        'transactions': [TradingService.trade_to_dict(t) for t in trades],
        'total': total,
        'limit': limit,
        'offset': offset
    })


@users_bp.route('/<wallet_address>/created-agents', methods=['GET'])
def get_user_created_agents(wallet_address):
    """Get agents created by this wallet."""
    from app.models import Agent
    from app.services.agent import AgentService
    
    agents = Agent.query.filter_by(
        creator_wallet=wallet_address,
        is_active=True
    ).order_by(Agent.created_at.desc()).all()
    
    return jsonify({
        'success': True,
        'wallet_address': wallet_address,
        'agents': [AgentService.agent_to_dict(a) for a in agents],
        'count': len(agents)
    })
