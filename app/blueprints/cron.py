"""
Cron Blueprint
Endpoints for scheduled tasks triggered by external cron services.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging

from app.models import db, Agent, Holding, Trade, ScoreHistory
from app.config import CRON_SECRET
from app.services.pricing import PricingService
from app.services.agent import AgentService
from app.services.arena import ArenaOrchestrator

logger = logging.getLogger(__name__)

cron_bp = Blueprint('cron', __name__, url_prefix='/api/cron')


def verify_cron_secret():
    """Verify cron secret from header or body."""
    auth_header = request.headers.get('Authorization', '')
    body_data = request.get_json(silent=True) or {}
    
    provided_secret = None
    if auth_header.startswith('Bearer '):
        provided_secret = auth_header[7:]
    elif body_data.get('cron_secret'):
        provided_secret = body_data.get('cron_secret')
    
    return provided_secret == CRON_SECRET


@cron_bp.route('/update-stats', methods=['POST'])
def cron_update_stats():
    """Cron endpoint: Update holder counts and volume stats."""
    if not verify_cron_secret():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        update_agent_stats()
        return jsonify({
            'success': True,
            'message': 'Stats updated',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cron_bp.route('/run-arena', methods=['POST'])
def cron_run_arena():
    """
    Cron endpoint: Run daily arena for all agents with validated interfaces.
    """
    if not verify_cron_secret():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        # Get all agents with validated interfaces
        agents = Agent.query.filter_by(
            is_active=True,
            interface_validated=True
        ).all()
        
        if not agents:
            # Also run for agents with interface_code but not validated yet
            agents = Agent.query.filter(
                Agent.is_active == True,
                Agent.interface_code != None
            ).all()
        
        results = {
            'updated': [],
            'failed': [],
            'skipped': []
        }
        
        orchestrator = ArenaOrchestrator()
        
        for agent in agents:
            if not agent.interface_code:
                results['skipped'].append({
                    'id': agent.id,
                    'name': agent.name,
                    'reason': 'No interface code'
                })
                continue
            
            try:
                # Run arena
                arena_result = orchestrator.run_arena(agent)
                
                # Calculate score change
                old_score = agent.current_score
                
                # Apply score change based on arena result
                from app.services.scoring import ScoringService
                raw_change = (arena_result.score - 50) / 10  # Convert 0-100 to -5 to +5
                score_result = ScoringService.apply_v1_score_change(
                    agent.current_score,
                    raw_change,
                    agent.tier or 'alpha'
                )
                
                # Update agent
                agent.previous_score = old_score
                agent.current_score = score_result.new_score
                agent.was_capped = score_result.was_capped
                agent.last_arena_run = datetime.utcnow()
                agent.last_score_update = datetime.utcnow()
                agent.interface_validated = True
                
                # Update UPI breakdown for utility/coding
                if agent.arena_type in ['utility', 'coding']:
                    agent.effectiveness_score = arena_result.effectiveness
                    agent.efficiency_score = arena_result.efficiency
                    agent.autonomy_score = arena_result.autonomy
                
                # Save arena result
                from app.models import ArenaResult as ArenaResultModel
                arena_record = ArenaResultModel(
                    agent_id=agent.id,
                    arena_type=agent.arena_type,
                    score=arena_result.score,
                    raw_score=arena_result.raw_score,
                    effectiveness=arena_result.effectiveness,
                    efficiency=arena_result.efficiency,
                    autonomy=arena_result.autonomy,
                    templates_run=arena_result.templates_run,
                    template_scores=arena_result.template_scores,
                    execution_time_ms=arena_result.execution_time_ms,
                    errors=arena_result.errors
                )
                db.session.add(arena_record)
                
                # Save score history
                price_data = PricingService.calculate_price(score_result.new_score)
                history = ScoreHistory(
                    agent_id=agent.id,
                    score=score_result.new_score,
                    raw_score=arena_result.score,
                    price_usd=price_data.price_usd,
                    price_sol=price_data.price_sol
                )
                db.session.add(history)
                
                results['updated'].append({
                    'id': agent.id,
                    'name': agent.name,
                    'arena_type': agent.arena_type,
                    'previous': old_score,
                    'new': score_result.new_score,
                    'arena_score': arena_result.score,
                    'capped': score_result.was_capped
                })
                
                logger.info(f"✅ Arena: {agent.name} [{agent.arena_type}] {old_score} → {score_result.new_score}")
                
            except Exception as e:
                results['failed'].append({
                    'id': agent.id,
                    'name': agent.name,
                    'error': str(e)
                })
                logger.error(f"❌ Arena failed for {agent.name}: {e}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Arena run completed',
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {
                'total_agents': len(agents),
                'updated': len(results['updated']),
                'failed': len(results['failed']),
                'skipped': len(results['skipped'])
            },
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Arena cron job failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cron_bp.route('/update-all-scores', methods=['POST'])
def cron_update_all_scores():
    """
    Cron endpoint: Update scores for all active agents with wallet addresses.
    Uses external scoring engine for on-chain data.
    """
    if not verify_cron_secret():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        from scoring_engine import calculate_agent_score, HELIUS_API_KEY as SCORING_HELIUS_KEY
        
        if not SCORING_HELIUS_KEY:
            return jsonify({
                'success': False,
                'error': 'Helius API key not configured'
            }), 500
        
        agents = Agent.query.filter_by(is_active=True).all()
        
        results = {
            'updated': [],
            'failed': [],
            'skipped': []
        }
        
        for agent in agents:
            if not agent.wallet_address:
                results['skipped'].append({
                    'id': agent.id,
                    'name': agent.name,
                    'reason': 'No wallet_address'
                })
                continue
            
            try:
                result = calculate_agent_score(
                    wallet_address=agent.wallet_address,
                    previous_score=agent.current_score
                )
                
                agent.previous_score = agent.current_score
                agent.raw_score = result.raw_score
                agent.current_score = result.final_score
                agent.was_capped = result.capped
                agent.last_score_update = datetime.utcnow()
                
                price_data = PricingService.calculate_price(result.final_score)
                
                history = ScoreHistory(
                    agent_id=agent.id,
                    score=result.final_score,
                    raw_score=result.raw_score,
                    price_usd=price_data.price_usd,
                    price_sol=price_data.price_sol
                )
                db.session.add(history)
                
                results['updated'].append({
                    'id': agent.id,
                    'name': agent.name,
                    'previous': agent.previous_score,
                    'new': result.final_score,
                    'capped': result.capped
                })
                
                logger.info(f"✅ Cron: {agent.name} {agent.previous_score} → {result.final_score}")
                
            except Exception as e:
                results['failed'].append({
                    'id': agent.id,
                    'name': agent.name,
                    'error': str(e)
                })
                logger.error(f"❌ Cron failed for {agent.name}: {e}")
        
        db.session.commit()
        update_agent_stats()
        
        return jsonify({
            'success': True,
            'message': 'Cron job completed',
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {
                'total_agents': len(agents),
                'updated': len(results['updated']),
                'failed': len(results['failed']),
                'skipped': len(results['skipped'])
            },
            'results': results
        })
        
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Scoring engine not available'
        }), 500
    except Exception as e:
        logger.error(f"Cron job failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def update_agent_stats():
    """Update holder counts and 24h volume for all agents."""
    try:
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        sol_price_usd = PricingService.get_sol_price_usd()
        
        agents = Agent.query.filter_by(is_active=True).all()
        for agent in agents:
            holders = Holding.query.filter(
                Holding.agent_id == agent.id,
                Holding.token_amount > 0
            ).count()
            agent.holders = holders
            
            recent_trades = Trade.query.filter(
                Trade.agent_id == agent.id,
                Trade.created_at >= twenty_four_hours_ago
            ).all()
            volume_24h = sum(t.sol_amount for t in recent_trades) / 1_000_000_000 * sol_price_usd
            agent.volume_24h = volume_24h
        
        db.session.commit()
        logger.info(f"📊 Updated stats for {len(agents)} agents")
    except Exception as e:
        logger.error(f"Error updating agent stats: {e}")
        db.session.rollback()
