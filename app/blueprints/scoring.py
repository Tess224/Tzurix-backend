"""
Scoring Blueprint
Score retrieval and refresh endpoints.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging

from app.models import db, Agent, ScoreHistory
from app.services.agent import AgentService
from app.services.pricing import PricingService
from app.config import get_tier_config

logger = logging.getLogger(__name__)

scoring_bp = Blueprint('scoring', __name__, url_prefix='/api')


@scoring_bp.route('/agents/<int:agent_id>/score', methods=['GET'])
def get_agent_score(agent_id):
    """Get current score and price for an agent."""
    agent = AgentService.get_agent(agent_id)
    
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    price_data = PricingService.calculate_price(agent.current_score)
    tier_config = get_tier_config(agent.tier or 'alpha')
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'name': agent.name,
        'tier': agent.tier or 'alpha',
        'score_ceiling': tier_config['max_score'],
        **PricingService.to_dict(price_data),
        'previous_score': agent.previous_score,
        'score_change_percent': ((agent.current_score - agent.previous_score) / agent.previous_score * 100) if agent.previous_score else 0
    })


@scoring_bp.route('/agents/<int:agent_id>/history', methods=['GET'])
def get_agent_history(agent_id):
    """Get score history for an agent."""
    agent = AgentService.get_agent(agent_id)
    
    if not agent:
        return jsonify({
            'success': False,
            'error': 'Agent not found'
        }), 404
    
    days = int(request.args.get('days', 30))
    since = datetime.utcnow() - timedelta(days=days)
    
    history = ScoreHistory.query.filter(
        ScoreHistory.agent_id == agent_id,
        ScoreHistory.calculated_at >= since
    ).order_by(ScoreHistory.calculated_at.asc()).all()
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'name': agent.name,
        'history': [{
            'id': h.id,
            'score': h.score,
            'raw_score': h.raw_score,
            'price_usd': h.price_usd,
            'price_sol': h.price_sol,
            'calculated_at': h.calculated_at.isoformat() if h.calculated_at else None
        } for h in history]
    })


@scoring_bp.route('/score/<wallet_address>', methods=['GET'])
def get_wallet_score(wallet_address):
    """
    Calculate and return score for a wallet using the scoring engine.
    This endpoint uses the external scoring_engine module.
    """
    try:
        from scoring_engine import calculate_agent_score, generate_mock_score, HELIUS_API_KEY
        
        if HELIUS_API_KEY:
            logger.info(f"Calculating score for {wallet_address[:8]}... using Helius API")
            result = calculate_agent_score(wallet_address)
            using_real_data = True
        else:
            logger.info(f"No HELIUS_API_KEY - using mock data for {wallet_address[:8]}...")
            result = generate_mock_score(wallet_address)
            using_real_data = False
        
        return jsonify({
            'success': True,
            'wallet_address': result.wallet_address,
            'raw_score': result.raw_score,
            'final_score': result.final_score,
            'previous_score': result.previous_score,
            'capped': result.capped,
            'calculated_at': result.calculated_at.isoformat(),
            'using_real_data': using_real_data,
            'metrics': {
                'total_trades': result.metrics.total_trades,
                'winning_trades': result.metrics.winning_trades,
                'losing_trades': result.metrics.losing_trades,
                'win_rate': result.metrics.win_rate,
                'total_pnl_sol': result.metrics.total_pnl_sol,
                'total_volume_sol': result.metrics.total_volume_sol,
                'avg_trade_pnl': result.metrics.avg_trade_pnl,
                'avg_hold_time_hours': result.metrics.avg_hold_time_hours,
                'trades_per_day': result.metrics.trades_per_day,
                'unique_tokens_traded': result.metrics.unique_tokens_traded,
                'largest_win_sol': result.metrics.largest_win_sol,
                'largest_loss_sol': result.metrics.largest_loss_sol,
                'risk_adjusted_return': result.metrics.risk_adjusted_return
            }
        })
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Scoring engine not available'
        }), 500
    except Exception as e:
        logger.error(f"Error calculating score: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scoring_bp.route('/agent/<int:agent_id>/refresh-score', methods=['POST'])
def refresh_agent_score(agent_id):
    """
    Refresh an agent's score from on-chain data.
    Requires wallet_address to be set.
    """
    try:
        from scoring_engine import calculate_agent_score, HELIUS_API_KEY
        
        agent = AgentService.get_agent(agent_id)
        if not agent:
            return jsonify({'success': False, 'error': 'Agent not found'}), 404
        
        if not agent.wallet_address:
            return jsonify({
                'success': False,
                'error': 'Agent has no wallet_address - use arena scoring instead'
            }), 400
        
        if not HELIUS_API_KEY:
            return jsonify({
                'success': False,
                'error': 'Helius API key not configured'
            }), 500
        
        result = calculate_agent_score(
            wallet_address=agent.wallet_address,
            previous_score=agent.current_score
        )
        
        agent.previous_score = agent.current_score
        agent.current_score = result.final_score
        agent.last_score_update = datetime.utcnow()
        
        price_data = PricingService.calculate_price(result.final_score)
        
        history = ScoreHistory(
            agent_id=agent_id,
            score=result.final_score,
            raw_score=result.raw_score,
            price_usd=price_data.price_usd,
            price_sol=price_data.price_sol
        )
        db.session.add(history)
        db.session.commit()
        
        logger.info(f"📊 Score refreshed: {agent.name} {agent.previous_score} → {result.final_score}")
        
        return jsonify({
            'success': True,
            'message': 'Score refreshed from on-chain data',
            'agent': AgentService.agent_to_dict(agent),
            'scoring_details': {
                'raw_score': result.raw_score,
                'final_score': result.final_score,
                'capped': result.capped,
            }
        })
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Scoring engine not available'
        }), 500
    except Exception as e:
        logger.error(f"Error refreshing score: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
