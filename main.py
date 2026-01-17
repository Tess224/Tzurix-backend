"""
Tzurix MVP Backend - V1 Arena Update
AI Agent Performance Exchange - Where Price = Score

Started: December 26, 2025
V1 Update: January 2026
Network: Solana Devnet (testnet)

V1 FEATURES:
- Starting score: 20
- Daily cap: ±5 points (absolute)
- wallet_address: Optional
- Tier system (alpha/beta/omega)
- Arena types: trading, utility, coding
- UPI scoring for utility/coding agents
- Interface code upload for arena testing

ARCHITECTURE:
- Blueprints: HTTP layer (thin wrappers)
- Services: Business logic (no HTTP)
- Admin: Isolated, feature-flagged
"""

import os
import logging
import random
from datetime import datetime
from flask import Flask
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

# App imports
from app.config import (
    DATABASE_URL, VERSION, ENABLE_ADMIN, ENABLE_SCHEDULER,
    IS_PRODUCTION, ENV
)
from app.models import db

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# MOCK SCORING HELPERS
# =============================================================================

def generate_mock_score_change(agent_type: str, current_score: float) -> float:
    """Generate realistic mock score change for demo."""
    volatility = {
        'trading': 2.5,
        'defi': 2.0,
        'social': 1.5,
        'utility': 1.0,
        'coding': 1.2,
    }.get(agent_type, 1.5)
    
    base = random.gauss(0.3, volatility)
    change = max(-4.0, min(4.0, base))
    
    if current_score > 70:
        change -= random.uniform(0.5, 1.5)
    elif current_score < 25:
        change += random.uniform(0.5, 1.5)
    
    return round(change, 2)


def generate_mock_arena_result(agent) -> dict:
    """Generate realistic mock arena result for demo."""
    arena_type = agent.arena_type or 'trading'
    base_perf = random.gauss(55, 20)
    base_perf = max(10, min(95, base_perf))
    
    if arena_type == 'trading':
        return {
            'score': round(base_perf, 1),
            'raw_score': round(base_perf + random.uniform(-5, 5), 1),
            'effectiveness': None,
            'efficiency': None,
            'autonomy': None,
            'templates_run': ['momentum_bull', 'mean_reversion', 'high_volatility'],
            'template_scores': {
                'momentum_bull': round(random.uniform(40, 90), 1),
                'mean_reversion': round(random.uniform(40, 90), 1),
                'high_volatility': round(random.uniform(30, 85), 1),
            },
            'execution_time_ms': random.randint(150, 800),
            'errors': [],
        }
    else:
        effectiveness = round(random.uniform(40, 95), 1)
        efficiency = round(random.uniform(40, 95), 1)
        autonomy = round(random.uniform(40, 95), 1)
        upi = effectiveness * 0.5 + efficiency * 0.3 + autonomy * 0.2
        return {
            'score': round(upi, 1),
            'raw_score': round(upi, 1),
            'effectiveness': effectiveness,
            'efficiency': efficiency,
            'autonomy': autonomy,
            'templates_run': ['task_completion', 'error_handling', 'resource_usage'],
            'template_scores': {
                'task_completion': effectiveness,
                'error_handling': efficiency,
                'resource_usage': autonomy,
            },
            'execution_time_ms': random.randint(200, 1200),
            'errors': [],
                                 }

# =============================================================================
# MOCK SCORING HELPERS
# =============================================================================

def generate_mock_score_change(agent_type: str, current_score: float) -> float:
    volatility = {'trading': 2.5, 'defi': 2.0, 'social': 1.5, 'utility': 1.0, 'coding': 1.2}.get(agent_type, 1.5)
    base = random.gauss(0.3, volatility)
    change = max(-4.0, min(4.0, base))
    if current_score > 70:
        change -= random.uniform(0.5, 1.5)
    elif current_score < 25:
        change += random.uniform(0.5, 1.5)
    return round(change, 2)


def generate_mock_arena_result(agent) -> dict:
    arena_type = getattr(agent, 'arena_type', 'trading') or 'trading'
    base_perf = max(10, min(95, random.gauss(55, 20)))
    if arena_type == 'trading':
        return {
            'score': round(base_perf, 1),
            'raw_score': round(base_perf + random.uniform(-5, 5), 1),
            'effectiveness': None, 'efficiency': None, 'autonomy': None,
            'templates_run': ['momentum_bull', 'mean_reversion', 'high_volatility'],
            'template_scores': {'momentum_bull': round(random.uniform(40, 90), 1), 'mean_reversion': round(random.uniform(40, 90), 1), 'high_volatility': round(random.uniform(30, 85), 1)},
            'execution_time_ms': random.randint(150, 800), 'errors': [],
        }
    else:
        effectiveness = round(random.uniform(40, 95), 1)
        efficiency = round(random.uniform(40, 95), 1)
        autonomy = round(random.uniform(40, 95), 1)
        upi = effectiveness * 0.5 + efficiency * 0.3 + autonomy * 0.2
        return {
            'score': round(upi, 1), 'raw_score': round(upi, 1),
            'effectiveness': effectiveness, 'efficiency': efficiency, 'autonomy': autonomy,
            'templates_run': ['task_completion', 'error_handling', 'resource_usage'],
            'template_scores': {'task_completion': effectiveness, 'error_handling': efficiency, 'resource_usage': autonomy},
            'execution_time_ms': random.randint(200, 1200), 'errors': [],
        }


def generate_mock_holder_count(current_holders: int, score: float) -> int:
    score_factor = (score - 50) / 50
    base_change = random.randint(-2, 4)
    if score_factor > 0.3:
        base_change += random.randint(0, 3)
    elif score_factor < -0.3:
        base_change -= random.randint(0, 2)
    return max(1, current_holders + base_change)


def generate_mock_volume(score: float, holders: int) -> float:
    base_daily = (score * 2) + (holders * 5)
    return round(base_daily * random.uniform(0.5, 2.0), 2)
    
# =============================================================================
# APP FACTORY
# =============================================================================

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
        logger.info("✅ Database tables created")
    
    return app


def register_blueprints(app):
    """
    Register blueprints based on environment and feature flags.
    
    PRODUCTION: Core blueprints only
    DEVELOPMENT: Core + Admin + Dev
    """
    from app.blueprints import (
        public_bp,
        agents_bp,
        trading_bp,
        users_bp,
        leaderboard_bp,
        scoring_bp,
        cron_bp,
    )
    
    # Core blueprints - always registered
    app.register_blueprint(public_bp)
    app.register_blueprint(agents_bp)
    app.register_blueprint(trading_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(scoring_bp)
    app.register_blueprint(cron_bp)
    
    logger.info(f"✅ Core blueprints registered (ENV={ENV})")
    
    # Try to register scoring_api if it exists
    try:
        from scoring_api import scoring_bp as external_scoring_bp
        app.register_blueprint(external_scoring_bp)
        logger.info("✅ External scoring_api blueprint registered")
    except ImportError:
        logger.info("ℹ️ External scoring_api not available")
    
    # Admin blueprints - conditional
    if ENABLE_ADMIN or not IS_PRODUCTION:
        from app.admin import admin_bp
        app.register_blueprint(admin_bp)
        logger.info("✅ Admin blueprint registered (ENABLE_ADMIN=true)")
    else:
        logger.info("⚠️ Admin blueprint DISABLED (production mode)")


# =============================================================================
# SCHEDULER
# =============================================================================

scheduler = None


def scheduled_tiered_score_update():
    """Tiered score updates with mock fallback."""
    from app.models import db, Agent, ScoreHistory
    from app.services.scoring import ScoringService
    from app.services.pricing import PricingService
    
    with app.app_context():
        try:
            now = datetime.utcnow()
            updated_count = 0
            
            all_agents = Agent.query.filter_by(is_active=True).all()
            
            for agent in all_agents:
                try:
                    # Check if real scoring available
                    real_scoring_available = (
                        getattr(agent, 'github_validated', False) and
                        getattr(agent, 'github_repo_url', None) and
                        False  # Set True when real sandbox exists
                    )
                    
                    if real_scoring_available:
                        continue  # Skip - handled by real arena
                    
                    # Generate mock score change
                    raw_change = generate_mock_score_change(
                        agent.type or 'trading',
                        agent.current_score
                    )
                    
                    # Apply V1 scoring (±5 cap, tier ceiling)
                    result = ScoringService.apply_v1_score_change(
                        current_score=agent.current_score,
                        raw_change=raw_change,
                        tier=agent.tier or 'alpha'
                    )
                    
                    # Update agent
                    agent.previous_score = agent.current_score
                    agent.current_score = result.new_score
                    agent.was_capped = result.was_capped
                    agent.last_score_update = now
                    
                    # Save to history
                    price_data = PricingService.calculate_price(result.new_score)
                    history = ScoreHistory(
                        agent_id=agent.id,
                        score=result.new_score,
                        raw_score=agent.current_score + raw_change,
                        price_usd=price_data.price_usd,
                        price_sol=price_data.price_sol
                    )
                    db.session.add(history)
                    updated_count += 1
                    
                    logger.info(f"[Scheduler] 🎭 {agent.name}: {agent.previous_score:.1f} → {result.new_score:.1f} (mock)")
                    
                except Exception as e:
                    logger.error(f"[Scheduler] Error updating {agent.name}: {e}")
                    continue
            
            db.session.commit()
            logger.info(f"[Scheduler] Tiered update complete: {updated_count}/{len(all_agents)} agents")
            
        except Exception as e:
            logger.error(f"[Scheduler] Tiered update error: {e}")
            db.session.rollback()
        


def scheduled_daily_weight_reset():
    """Reset daily weight parameters at 00:00 UTC."""
    with app.app_context():
        try:
            agent_types = ['trading', 'social', 'defi', 'utility', 'coding']
            
            for agent_type in agent_types:
                if agent_type == 'trading':
                    modifiers = {
                        'pnl': round(0.7 + random.random() * 0.6, 2),
                        'win_rate': round(0.7 + random.random() * 0.6, 2),
                        'risk_adjusted': round(0.7 + random.random() * 0.6, 2),
                        'drawdown': round(0.7 + random.random() * 0.6, 2),
                        'consistency': round(0.7 + random.random() * 0.6, 2),
                        'uptime': round(0.7 + random.random() * 0.6, 2),
                    }
                elif agent_type == 'utility':
                    modifiers = {
                        'effectiveness': round(0.7 + random.random() * 0.6, 2),
                        'efficiency': round(0.7 + random.random() * 0.6, 2),
                        'autonomy': round(0.7 + random.random() * 0.6, 2),
                    }
                elif agent_type == 'coding':
                    modifiers = {
                        'code_quality': round(0.7 + random.random() * 0.6, 2),
                        'test_coverage': round(0.7 + random.random() * 0.6, 2),
                        'efficiency': round(0.7 + random.random() * 0.6, 2),
                    }
                else:
                    modifiers = {
                        'performance': round(0.7 + random.random() * 0.6, 2),
                        'reliability': round(0.7 + random.random() * 0.6, 2),
                        'efficiency': round(0.7 + random.random() * 0.6, 2),
                    }
                logger.info(f"[Scheduler] Daily modifiers for {agent_type}: {modifiers}")
            
            logger.info(f"[Scheduler] Daily weight parameters reset at {datetime.utcnow()}")
            
        except Exception as e:
            logger.error(f"[Scheduler] Daily weight reset error: {e}")


def scheduled_stats_update():
    """Update holder counts and 24h volume for all agents."""
    from app.blueprints.cron import update_agent_stats
    with app.app_context():
        try:
            update_agent_stats()
            logger.info("[Scheduler] Stats update completed")
        except Exception as e:
            logger.error(f"[Scheduler] Stats update error: {e}")


def scheduled_arena_run():
    """Daily arena run with mock fallback."""
    from app.models import db, Agent, ScoreHistory, ArenaResult as ArenaResultModel
    from app.services.scoring import ScoringService
    from app.services.pricing import PricingService
    
    with app.app_context():
        try:
            now = datetime.utcnow()
            results_count = 0
            
            agents = Agent.query.filter_by(is_active=True).all()
            
            if not agents:
                logger.info("[Scheduler] No active agents for arena run")
                return
            
            for agent in agents:
                try:
                    # Generate mock arena result
                    arena_result = generate_mock_arena_result(agent)
                    
                    # Map arena score (0-100) to score change (-3 to +3)
                    raw_change = (arena_result['score'] - 50) / 15
                    raw_change = round(raw_change, 2)
                    
                    # Apply V1 scoring
                    score_result = ScoringService.apply_v1_score_change(
                        current_score=agent.current_score,
                        raw_change=raw_change,
                        tier=agent.tier or 'alpha'
                    )
                    
                    # Update agent
                    agent.previous_score = agent.current_score
                    agent.current_score = score_result.new_score
                    agent.was_capped = score_result.was_capped
                    agent.last_arena_run = now
                    agent.last_score_update = now
                    
                    # Update UPI fields if utility/coding
                    if agent.arena_type in ['utility', 'coding']:
                        agent.effectiveness_score = arena_result.get('effectiveness')
                        agent.efficiency_score = arena_result.get('efficiency')
                        agent.autonomy_score = arena_result.get('autonomy')
                    
                    # Save arena result
                    arena_record = ArenaResultModel(
                        agent_id=agent.id,
                        arena_type=agent.arena_type or 'trading',
                        score=arena_result['score'],
                        raw_score=arena_result['raw_score'],
                        effectiveness=arena_result.get('effectiveness'),
                        efficiency=arena_result.get('efficiency'),
                        autonomy=arena_result.get('autonomy'),
                        templates_run=arena_result.get('templates_run', []),
                        template_scores=arena_result.get('template_scores', {}),
                        execution_time_ms=arena_result.get('execution_time_ms', 0),
                        errors=arena_result.get('errors', [])
                    )
                    db.session.add(arena_record)
                    
                    # Save score history
                    price_data = PricingService.calculate_price(score_result.new_score)
                    history = ScoreHistory(
                        agent_id=agent.id,
                        score=score_result.new_score,
                        raw_score=arena_result['score'],
                        price_usd=price_data.price_usd,
                        price_sol=price_data.price_sol
                    )
                    db.session.add(history)
                    
                    results_count += 1
                    logger.info(f"[Scheduler] 🎭 Arena: {agent.name} scored {arena_result['score']:.1f} → {score_result.new_score:.1f} (mock)")
                
                except Exception as e:
                    logger.error(f"[Scheduler] Arena error for {agent.name}: {e}")
                    continue
            
            db.session.commit()
            logger.info(f"[Scheduler] Arena run complete: {results_count}/{len(agents)} agents")
            
        except Exception as e:
            logger.error(f"[Scheduler] Arena run error: {e}")
            db.session.rollback()


def start_scheduler():
    """Initialize and start the background scheduler."""
    global scheduler
    
    if scheduler is not None:
        logger.info("[Scheduler] Already running")
        return
    
    scheduler = BackgroundScheduler(daemon=True)
    
    # Tiered score updates - every 2 minutes
    scheduler.add_job(
        scheduled_tiered_score_update,
        IntervalTrigger(minutes=2),
        id='tiered_score_update',
        replace_existing=True,
        max_instances=1
    )
    
    # Daily weight reset - 00:00 UTC
    scheduler.add_job(
        scheduled_daily_weight_reset,
        CronTrigger(hour=0, minute=0),
        id='daily_weight_reset',
        replace_existing=True
    )
    
    # Stats update (holders, volume) - every 30 minutes
    scheduler.add_job(
        scheduled_stats_update,
        IntervalTrigger(minutes=30),
        id='stats_update',
        replace_existing=True,
        max_instances=1
    )
    
    # Daily arena run - 00:30 UTC (30 min after weight reset)
    scheduler.add_job(
        scheduled_arena_run,
        CronTrigger(hour=0, minute=30),
        id='daily_arena_run',
        replace_existing=True,
        max_instances=1
    )
    
    scheduler.start()
    
    # Set scheduler reference in admin module if available
    if ENABLE_ADMIN or not IS_PRODUCTION:
        try:
            from app.admin.admin_bp import set_scheduler
            set_scheduler(scheduler)
        except ImportError:
            pass
    
    logger.info("[Scheduler] ✅ Started successfully!")
    logger.info("  - Tiered score updates: every 2 minutes")
    logger.info("  - Daily weight reset: 00:00 UTC")
    logger.info("  - Daily arena run: 00:30 UTC")
    logger.info("  - Stats update: every 30 minutes")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None
        logger.info("[Scheduler] Stopped")


# =============================================================================
# CREATE APP INSTANCE
# =============================================================================

app = create_app()


# =============================================================================
# MAIN
# =============================================================================

# Start the scheduler (only in production/Railway or when explicitly enabled)
if ENABLE_SCHEDULER:
    start_scheduler()

if __name__ == '__main__':
    start_scheduler()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=not IS_PRODUCTION)
