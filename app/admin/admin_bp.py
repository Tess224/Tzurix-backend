"""
Admin Blueprint
ISOLATED - This entire module can be disabled/removed for production.

Contains:
- Database migration endpoints
- Score manipulation (admin only)
- Debug utilities
- Scheduler controls

To disable: Don't register this blueprint (see main.py)
"""

from flask import Blueprint, jsonify, request
import random
from datetime import datetime, timedelta
from threading import Thread
import logging

from app.models import db, Agent, ScoreHistory
from app.config import ADMIN_KEY
from app.services.pricing import PricingService
from app.services.scoring import ScoringService
from app.services.agent import AgentService

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def verify_admin_key():
    """Verify admin key from header or body."""
    admin_key = request.headers.get('X-Admin-Key')
    if not admin_key:
        body = request.get_json(silent=True) or {}
        admin_key = body.get('admin_key')
    return admin_key == ADMIN_KEY


# =============================================================================
# MIGRATION ENDPOINTS
# =============================================================================

@admin_bp.route('/migrate-v1', methods=['POST'])
def run_v1_migration():
    """
    Run V1 database migration via API call.
    Adds new columns required for V1 features.
    """
    from sqlalchemy import text, inspect
    
    results = []
    
    def column_exists(table, column):
        inspector = inspect(db.engine)
        try:
            columns = [c['name'] for c in inspector.get_columns(table)]
            return column in columns
        except:
            return False
    
    def add_column(table, column, col_type, default=None):
        if column_exists(table, column):
            results.append(f"exists: {table}.{column}")
            return
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
        if default:
            sql += f" DEFAULT {default}"
        try:
            db.session.execute(text(sql))
            db.session.commit()
            results.append(f"added: {table}.{column}")
        except Exception as e:
            db.session.rollback()
            results.append(f"error: {table}.{column} - {str(e)}")
    
    # V1 Agent columns
    add_column('agents', 'tier', 'VARCHAR(10)', "'alpha'")
    add_column('agents', 'arena_type', 'VARCHAR(20)', "'trading'")
    add_column('agents', 'keywords', 'JSON', 'NULL')
    add_column('agents', 'interface_type', 'VARCHAR(20)', 'NULL')
    add_column('agents', 'interface_code', 'TEXT', 'NULL')
    add_column('agents', 'interface_version', 'INTEGER', '1')
    add_column('agents', 'interface_validated', 'BOOLEAN', 'FALSE')
    add_column('agents', 'interface_updated_at', 'TIMESTAMP', 'NULL')
    add_column('agents', 'effectiveness_score', 'FLOAT', 'NULL')
    add_column('agents', 'efficiency_score', 'FLOAT', 'NULL')
    add_column('agents', 'autonomy_score', 'FLOAT', 'NULL')
    add_column('agents', 'last_arena_run', 'TIMESTAMP', 'NULL')
    add_column('agents', 'last_activity_at', 'TIMESTAMP', 'NULL')
    add_column('agents', 'twitter_handle', 'VARCHAR(50)', 'NULL')
    add_column('agents', 'github_url', 'VARCHAR(200)', 'NULL')
    add_column('agents', 'website_url', 'VARCHAR(200)', 'NULL')
    
    # Update existing agents with defaults
    try:
        result = db.session.execute(text("UPDATE agents SET tier = 'alpha' WHERE tier IS NULL OR tier = ''"))
        db.session.commit()
        results.append(f"updated: {result.rowcount} agents with default tier")
    except Exception as e:
        db.session.rollback()
        results.append(f"error updating agents: {str(e)}")
    
    try:
        result = db.session.execute(text("UPDATE agents SET arena_type = 'trading' WHERE arena_type IS NULL OR arena_type = ''"))
        db.session.commit()
        results.append(f"updated: {result.rowcount} agents with default arena_type")
    except Exception as e:
        db.session.rollback()
        results.append(f"error updating arena_type: {str(e)}")
    
    # Create arena_results table if not exists
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS arena_results (
                id SERIAL PRIMARY KEY,
                agent_id INTEGER REFERENCES agents(id),
                arena_type VARCHAR(20) NOT NULL,
                score FLOAT NOT NULL,
                raw_score FLOAT,
                effectiveness FLOAT,
                efficiency FLOAT,
                autonomy FLOAT,
                templates_run JSON,
                template_scores JSON,
                execution_time_ms INTEGER,
                errors JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.commit()
        results.append("created/verified: arena_results table")
    except Exception as e:
        db.session.rollback()
        results.append(f"error creating arena_results: {str(e)}")
    
    return jsonify({
        'success': True,
        'message': 'V1 migration complete',
        'results': results
    })


# =============================================================================
# SCORE ADMIN ENDPOINTS
# =============================================================================

@admin_bp.route('/update-score', methods=['POST'])
def update_agent_score():
    """Update an agent's score (admin endpoint)."""
    if not verify_admin_key():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    agent_id = data.get('agent_id')
    new_raw_score = data.get('new_score')
    
    if not agent_id or new_raw_score is None:
        return jsonify({
            'success': False,
            'error': 'Missing agent_id or new_score'
        }), 400
    
    agent = AgentService.get_agent(agent_id)
    if not agent:
        return jsonify({'success': False, 'error': 'Agent not found'}), 404
    
    # Apply V1 scoring
    raw_change = new_raw_score - agent.current_score
    result = ScoringService.apply_v1_score_change(
        agent.current_score,
        raw_change,
        agent.tier or 'alpha'
    )
    
    agent.previous_score = agent.current_score
    agent.current_score = result.new_score
    agent.was_capped = result.was_capped
    agent.last_score_update = datetime.utcnow()
    
    price_data = PricingService.calculate_price(result.new_score)
    
    history = ScoreHistory(
        agent_id=agent_id,
        score=result.new_score,
        raw_score=new_raw_score,
        price_usd=price_data.price_usd,
        price_sol=price_data.price_sol
    )
    db.session.add(history)
    db.session.commit()
    
    logger.info(f"📊 Admin score update: {agent.name} {agent.previous_score} → {result.new_score} (raw: {new_raw_score})")
    
    return jsonify({
        'success': True,
        'message': 'Score updated',
        'agent_id': agent_id,
        'previous_score': agent.previous_score,
        'raw_score': new_raw_score,
        'new_score': result.new_score,
        'capped': result.was_capped,
        'new_price': PricingService.to_dict(price_data)
    })


@admin_bp.route('/set-interface-validated', methods=['POST'])
def set_interface_validated():
    """Manually validate an agent's interface."""
    if not verify_admin_key():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    agent_id = data.get('agent_id')
    validated = data.get('validated', True)
    
    agent = AgentService.get_agent(agent_id)
    if not agent:
        return jsonify({'success': False, 'error': 'Agent not found'}), 404
    
    agent.interface_validated = validated
    db.session.commit()
    
    return jsonify({
        'success': True,
        'agent_id': agent_id,
        'interface_validated': validated
    })


# =============================================================================
# SCHEDULER ADMIN ENDPOINTS
# =============================================================================

# Global scheduler reference (set by main.py)
_scheduler = None

def set_scheduler(scheduler):
    """Set scheduler reference for admin control."""
    global _scheduler
    _scheduler = scheduler


@admin_bp.route('/trigger-score-update', methods=['POST'])
def admin_trigger_score_update():
    """Manually trigger a score update cycle."""
    if not verify_admin_key():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        from app.blueprints.cron import cron_update_all_scores
        Thread(target=lambda: cron_update_all_scores()).start()
        
        return jsonify({
            'success': True,
            'message': 'Score update cycle started in background'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/trigger-arena', methods=['POST'])
def admin_trigger_arena():
    """Manually trigger an arena run."""
    if not verify_admin_key():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        from app.blueprints.cron import cron_run_arena
        Thread(target=lambda: cron_run_arena()).start()
        
        return jsonify({
            'success': True,
            'message': 'Arena run started in background'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/scheduler-status', methods=['GET'])
def admin_scheduler_status():
    """Check scheduler status."""
    global _scheduler
    
    if _scheduler is None:
        return jsonify({'status': 'not_running', 'jobs': []})
    
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'next_run': str(job.next_run_time) if job.next_run_time else None
        })
    
    return jsonify({
        'status': 'running',
        'jobs': jobs
    })

@admin_bp.route('/init-demo-data', methods=['POST'])
def init_all_demo_data():
    """Initialize all demo data for all agents."""
    if not verify_admin_key():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    import random
    from datetime import datetime, timedelta
    from app.models import db, Agent, ScoreHistory, Trade
    from app.services.pricing import PricingService
    
    agents = Agent.query.filter_by(is_active=True).all()
    now = datetime.utcnow()
    results = []
    
    for agent in agents:
        # Clear existing history
        ScoreHistory.query.filter_by(agent_id=agent.id).delete()
        
        # Generate 30 days of score history
        current_score = agent.current_score or 20.0
        scores = [current_score]
        
        for i in range(29):
            change = random.gauss(0, 2.5)
            change = max(-4.5, min(4.5, change))
            prev_score = scores[-1] - change
            prev_score = max(5, min(75, prev_score))
            scores.append(prev_score)
        
        scores.reverse()
        
        for i, score in enumerate(scores):
            days_ago = 30 - i - 1
            timestamp = now - timedelta(days=days_ago, hours=random.randint(0, 12))
            price_data = PricingService.calculate_price(score)
            
            history = ScoreHistory(
                agent_id=agent.id,
                score=round(score, 1),
                raw_score=round(score + random.uniform(-3, 5), 1),
                price_usd=price_data.price_usd,
                price_sol=price_data.price_sol,
                calculated_at=timestamp
            )
            db.session.add(history)
        
        # Generate 50 fake trades
        for i in range(50):
            random_hours = random.randint(0, 30 * 24)
            trade_time = now - timedelta(hours=random_hours)
            
            side = random.choice(['buy', 'sell'])
            token_amount = random.randint(100, 10000)
            estimated_score = current_score + random.uniform(-10, 10)
            price_per_token = estimated_score * 0.0001
            sol_amount = (token_amount * price_per_token) / 140
            
            chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
            fake_wallet = ''.join(random.choice(chars) for _ in range(44))
            fake_tx = ''.join(random.choice(chars) for _ in range(88))
            
            trade = Trade(
                agent_id=agent.id,
                trader_wallet=fake_wallet,
                side=side,
                token_amount=token_amount,
                sol_amount=round(sol_amount, 6),
                price_at_trade=round(price_per_token, 8),
                score_at_trade=round(estimated_score, 1),
                tx_signature=fake_tx,
                created_at=trade_time
            )
            db.session.add(trade)
        
        # Set realistic stats
        agent.holders = random.randint(15, 75)
        agent.volume_24h = round(random.uniform(200, 2000), 2)
        agent.total_volume = round(random.uniform(5000, 25000), 2)
        agent.last_score_update = now
        
        results.append({
            'agent_id': agent.id,
            'name': agent.name,
            'holders': agent.holders,
            'volume_24h': agent.volume_24h
        })
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Initialized demo data for {len(agents)} agents',
        'results': results
    })
# =============================================================================
# DEBUG / DEV ENDPOINTS
# =============================================================================

@admin_bp.route('/test-arena/<int:agent_id>', methods=['POST'])
def test_arena_for_agent(agent_id):
    """
    Test arena run for a single agent (dev only).
    Returns detailed results without saving to database.
    """
    if not verify_admin_key():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    agent = AgentService.get_agent(agent_id)
    if not agent:
        return jsonify({'success': False, 'error': 'Agent not found'}), 404
    
    if not agent.interface_code:
        return jsonify({
            'success': False,
            'error': 'Agent has no interface code'
        }), 400
    
    try:
        from app.services.arena import ArenaOrchestrator
        orchestrator = ArenaOrchestrator()
        result = orchestrator.run_arena(agent)
        
        return jsonify({
            'success': True,
            'agent': {
                'id': agent.id,
                'name': agent.name,
                'arena_type': agent.arena_type,
                'tier': agent.tier
            },
            'result': result.to_dict(),
            'note': 'This was a test run - no scores were saved'
        })
    except Exception as e:
        logger.error(f"Test arena failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/db-stats', methods=['GET'])
def get_db_stats():
    """Get database statistics."""
    if not verify_admin_key():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    from app.models import User, Trade, Holding, ArenaResult
    
    return jsonify({
        'success': True,
        'stats': {
            'agents': Agent.query.count(),
            'active_agents': Agent.query.filter_by(is_active=True).count(),
            'agents_with_interface': Agent.query.filter(Agent.interface_code != None).count(),
            'users': User.query.count(),
            'trades': Trade.query.count(),
            'holdings': Holding.query.count(),
            'score_history': ScoreHistory.query.count(),
            'arena_results': ArenaResult.query.count() if hasattr(ArenaResult, 'query') else 0,
            'agents_by_arena': {
                'trading': Agent.query.filter_by(arena_type='trading').count(),
                'utility': Agent.query.filter_by(arena_type='utility').count(),
                'coding': Agent.query.filter_by(arena_type='coding').count(),
            },
            'agents_by_tier': {
                'alpha': Agent.query.filter_by(tier='alpha').count(),
                'beta': Agent.query.filter_by(tier='beta').count(),
                'omega': Agent.query.filter_by(tier='omega').count(),
            }
        }
    })
