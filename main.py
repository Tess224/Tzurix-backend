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
    """Tiered score updates based on trading activity."""
    from app.models import Agent
    from app.services.pricing import PricingService
    
    with app.app_context():
        try:
            now = datetime.utcnow()
            updated_count = 0
            
            all_agents = Agent.query.filter_by(is_active=True).all()
            
            for agent in all_agents:
                should_update = False
                
                last_trade = agent.last_trade_at or datetime(2000, 1, 1)
                last_update = agent.last_score_update or datetime(2000, 1, 1)
                
                hours_since_trade = (now - last_trade).total_seconds() / 3600
                minutes_since_update = (now - last_update).total_seconds() / 60
                
                if hours_since_trade <= 1:
                    should_update = True
                    tier = "HOT"
                elif hours_since_trade <= 24:
                    should_update = minutes_since_update >= 10
                    tier = "ACTIVE"
                else:
                    should_update = minutes_since_update >= 60
                    tier = "IDLE"
                
                if should_update:
                    # Arena-based scoring handles score updates via scheduled_arena_run()
                    # Wallet-based on-chain scoring (Helius) not yet implemented
                    pass
                
                import time
                time.sleep(0.5)
            
            db.session.commit()
            logger.info(f"[Scheduler] Tiered update complete: {updated_count}/{len(all_agents)} agents updated")
            
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
    """Run daily arena for all eligible agents."""
    with app.app_context():
        try:
            # Import here to avoid circular imports
            from app.models import Agent
            from app.services.arena import ArenaOrchestrator
            
            agents = Agent.query.filter(
                Agent.is_active == True,
                Agent.interface_code != None
            ).all()
            
            if not agents:
                logger.info("[Scheduler] No agents with interfaces to test")
                return
            
            orchestrator = ArenaOrchestrator()
            results = orchestrator.run_all_agents(agents)
            
            # Update scores based on results
            for i, agent in enumerate(agents):
                if i < len(results):
                    result = results[i]
                    # Apply score change...
                    logger.info(f"[Scheduler] Arena: {agent.name} scored {result.score}")
            
            logger.info(f"[Scheduler] Arena run complete: {len(results)} agents tested")
            
        except Exception as e:
            logger.error(f"[Scheduler] Arena run error: {e}")


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
