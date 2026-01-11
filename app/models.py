"""
Tzurix Database Models
Pure SQLAlchemy models with no HTTP dependencies.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Agent(db.Model):
    """
    Represents a registered AI agent.
    Each agent gets a tokenized stock with price tied to their score.
    
    V1 CHANGES:
    - wallet_address is now optional (nullable=True)
    - Added tier system fields
    - Added interface_code for arena testing
    - Added arena_type for utility/coding arenas
    - Added keywords for template routing
    - Added social links
    """
    __tablename__ = 'agents'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # V1: wallet_address is now OPTIONAL
    wallet_address = db.Column(db.String(44), unique=True, nullable=True)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    creator_wallet = db.Column(db.String(44), nullable=False)
    
    # Score data (V1: default is now 20)
    current_score = db.Column(db.Float, default=20)
    previous_score = db.Column(db.Float, default=20)
    raw_score = db.Column(db.Float, default=20)
    was_capped = db.Column(db.Boolean, default=False)
    
    # Agent classification
    agent_type = db.Column(db.String(20), default='trading')
    category = db.Column(db.String(20), default='agent')
    
    # V1: Arena type (trading/utility/coding)
    arena_type = db.Column(db.String(20), default='trading')
    
    # V1: Keywords for template routing (JSON array)
    keywords = db.Column(db.JSON, default=list)
    
    # V1: Tier system
    tier = db.Column(db.String(10), default='alpha')
    
    # V1: GitHub-based decision interface
    github_repo_url = db.Column(db.String(255))  # https://github.com/user/repo
    github_branch = db.Column(db.String(100), default='main')
    github_entry_file = db.Column(db.String(255), default='agent.py')
    github_validated = db.Column(db.Boolean, default=False)
    github_last_commit = db.Column(db.String(40))  # Short SHA
    github_last_validated_at = db.Column(db.DateTime)
    
    # V1: UPI breakdown (for utility/coding arenas)
    effectiveness_score = db.Column(db.Float)
    efficiency_score = db.Column(db.Float)
    autonomy_score = db.Column(db.Float)
    
    # V1: Arena tracking
    last_arena_run = db.Column(db.DateTime)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # V1: Social links
    twitter_handle = db.Column(db.String(50))
    website_url = db.Column(db.String(200))
    
    # Token data
    token_mint = db.Column(db.String(44))
    total_supply = db.Column(db.BigInteger, default=100_000_000)
    reserve_lamports = db.Column(db.BigInteger, default=0)

    # Stats (updated by cron)
    holders = db.Column(db.Integer, default=0)
    volume_24h = db.Column(db.Float, default=0)
    total_volume = db.Column(db.Float, default=0)
    last_score_update = db.Column(db.DateTime, default=datetime.utcnow)
    last_trade_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    score_history = db.relationship('ScoreHistory', backref='agent', lazy='dynamic')
    trades = db.relationship('Trade', backref='agent', lazy='dynamic')
    arena_results = db.relationship('ArenaResult', backref='agent', lazy='dynamic')


class ScoreHistory(db.Model):
    """
    Tracks historical scores for each agent.
    Used for charts and trend analysis.
    """
    __tablename__ = 'score_history'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    
    score = db.Column(db.Float, nullable=False)
    raw_score = db.Column(db.Float)
    price_usd = db.Column(db.Float)
    price_sol = db.Column(db.Float)
    
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)


class Trade(db.Model):
    """
    Records all buy/sell transactions.
    """
    __tablename__ = 'trades'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    trader_wallet = db.Column(db.String(44), nullable=False)
    
    side = db.Column(db.String(4), nullable=False)
    token_amount = db.Column(db.BigInteger, nullable=False)
    sol_amount = db.Column(db.BigInteger, nullable=False)
    price_at_trade = db.Column(db.Float)
    score_at_trade = db.Column(db.Integer)
    
    tx_signature = db.Column(db.String(88))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class User(db.Model):
    """
    Simple user tracking by wallet address.
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    wallet_address = db.Column(db.String(44), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    holdings = db.relationship('Holding', backref='user', lazy='dynamic')


class Holding(db.Model):
    """
    Tracks how many tokens each user holds for each agent.
    """
    __tablename__ = 'holdings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    
    token_amount = db.Column(db.BigInteger, default=0)
    avg_buy_price = db.Column(db.Float)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'agent_id', name='unique_user_agent'),)


class ArenaResult(db.Model):
    """
    V1: Stores results from arena testing for all arena types.
    """
    __tablename__ = 'arena_results'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)
    
    arena_type = db.Column(db.String(20), nullable=False)  # trading/utility/coding
    
    # Overall score (UPI for utility/coding)
    score = db.Column(db.Float, nullable=False)
    raw_score = db.Column(db.Float)
    
    # UPI breakdown (for utility/coding)
    effectiveness = db.Column(db.Float)
    efficiency = db.Column(db.Float)
    autonomy = db.Column(db.Float)
    
    # Template/scenario info
    templates_run = db.Column(db.JSON)  # List of templates executed
    template_scores = db.Column(db.JSON)  # Per-template scores
    
    # Execution metadata
    execution_time_ms = db.Column(db.Integer)
    errors = db.Column(db.JSON)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
