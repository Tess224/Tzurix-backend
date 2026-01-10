"""
Agent Service
Handles agent CRUD operations with NO HTTP dependencies.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

from app.models import db, Agent, ScoreHistory
from app.config import (
    STARTING_SCORE, VALID_AGENT_TYPES, ARENA_TYPES, TIERS,
    get_tier_config, LAMPORTS_PER_SCORE_POINT, SOL_PRICE_USD
)
from app.services.pricing import PricingService

logger = logging.getLogger(__name__)


@dataclass
class CreateAgentRequest:
    """Data required to create an agent."""
    name: str
    creator_wallet: str
    wallet_address: Optional[str] = None
    description: Optional[str] = None
    agent_type: str = 'trading'
    arena_type: str = 'trading'
    category: str = 'agent'
    tier: str = 'alpha'
    keywords: Optional[List[str]] = None
    twitter_handle: Optional[str] = None
    github_url: Optional[str] = None
    website_url: Optional[str] = None


@dataclass
class CreateAgentResult:
    """Result of agent creation."""
    success: bool
    agent: Optional[Agent] = None
    error: Optional[str] = None


class AgentService:
    """
    Agent CRUD service.
    Handles database operations for agents.
    """
    
    @staticmethod
    def create_agent(request: CreateAgentRequest) -> CreateAgentResult:
        """
        Create a new agent.
        
        Args:
            request: CreateAgentRequest with agent data
        
        Returns:
            CreateAgentResult with agent or error
        """
        # Validate agent type
        if request.agent_type not in VALID_AGENT_TYPES:
            return CreateAgentResult(
                success=False,
                error=f'Invalid agent type. Must be one of: {VALID_AGENT_TYPES}'
            )
        
        # Validate arena type
        if request.arena_type not in ARENA_TYPES:
            return CreateAgentResult(
                success=False,
                error=f'Invalid arena type. Must be one of: {ARENA_TYPES}'
            )
        
        # Validate category
        if request.category not in ['agent', 'individual']:
            return CreateAgentResult(
                success=False,
                error='Invalid category. Must be "agent" or "individual"'
            )
        
        # Validate tier
        tier = request.tier.lower() if request.tier else 'alpha'
        if tier not in ['alpha', 'beta', 'omega']:
            tier = 'alpha'
        
        # Check for duplicate wallet_address if provided
        if request.wallet_address:
            existing = Agent.query.filter_by(wallet_address=request.wallet_address).first()
            if existing:
                return CreateAgentResult(
                    success=False,
                    error='Agent with this wallet address already registered'
                )
        
        # Check for duplicate name
        existing_name = Agent.query.filter_by(name=request.name).first()
        if existing_name:
            return CreateAgentResult(
                success=False,
                error='Agent with this name already exists'
            )
        
        # Create agent
        agent = Agent(
            name=request.name,
            description=request.description or '',
            creator_wallet=request.creator_wallet,
            wallet_address=request.wallet_address,
            agent_type=request.agent_type,
            arena_type=request.arena_type,
            category=request.category,
            tier=tier,
            keywords=request.keywords or [],
            twitter_handle=request.twitter_handle,
            github_url=request.github_url,
            website_url=request.website_url,
            current_score=STARTING_SCORE,
            previous_score=STARTING_SCORE,
            raw_score=STARTING_SCORE
        )
        
        db.session.add(agent)
        
        # Create initial score history entry
        price_data = PricingService.calculate_price(STARTING_SCORE)
        history = ScoreHistory(
            agent=agent,
            score=STARTING_SCORE,
            raw_score=STARTING_SCORE,
            price_usd=price_data.price_usd,
            price_sol=price_data.price_sol
        )
        db.session.add(history)
        
        db.session.commit()
        
        logger.info(f"✅ New agent registered: {agent.name} [Arena: {agent.arena_type}, Tier: {tier}] (Score: {STARTING_SCORE})")
        
        return CreateAgentResult(success=True, agent=agent)
    
    @staticmethod
    def get_agent(agent_id: int) -> Optional[Agent]:
        """Get agent by ID."""
        return Agent.query.get(agent_id)
    
    @staticmethod
    def get_agent_by_wallet(wallet_address: str) -> Optional[Agent]:
        """Get agent by wallet address."""
        return Agent.query.filter_by(wallet_address=wallet_address).first()
    
    @staticmethod
    def get_agents(
        sort: str = 'score',
        agent_type: Optional[str] = None,
        arena_type: Optional[str] = None,
        category: Optional[str] = None,
        tier: Optional[str] = None,
        limit: int = 50
    ) -> List[Agent]:
        """
        Get list of agents with filters and sorting.
        """
        query = Agent.query.filter_by(is_active=True)
        
        # Apply filters
        if agent_type and agent_type in VALID_AGENT_TYPES:
            query = query.filter_by(agent_type=agent_type)
        
        if arena_type and arena_type in ARENA_TYPES:
            query = query.filter_by(arena_type=arena_type)
        
        if category and category in ['agent', 'individual']:
            query = query.filter_by(category=category)
        
        if tier and tier.lower() in ['alpha', 'beta', 'omega']:
            query = query.filter_by(tier=tier.lower())
        
        # Apply sorting
        if sort == 'score':
            query = query.order_by(Agent.current_score.desc())
        elif sort == 'newest':
            query = query.order_by(Agent.created_at.desc())
        elif sort == 'name':
            query = query.order_by(Agent.name.asc())
        elif sort == 'volume':
            query = query.order_by(Agent.volume_24h.desc())
        elif sort == 'holders':
            query = query.order_by(Agent.holders.desc())
        else:
            query = query.order_by(Agent.current_score.desc())
        
        return query.limit(min(limit, 100)).all()
    
    @staticmethod
    def update_interface(
        agent_id: int,
        creator_wallet: str,
        interface_code: str,
        interface_type: str = 'simple'
    ) -> Dict[str, Any]:
        """
        Upload/update decision interface for an agent.
        
        Returns:
            Dict with success status and details
        """
        agent = Agent.query.get(agent_id)
        if not agent:
            return {'success': False, 'error': 'Agent not found'}
        
        # Verify ownership
        if agent.creator_wallet != creator_wallet:
            return {'success': False, 'error': 'Not authorized. Must be agent creator.'}
        
        # Basic validation - check for decide() function
        if 'def decide(' not in interface_code:
            return {
                'success': False,
                'error': 'Interface must contain a decide(market_data, portfolio) function'
            }
        
        # Store interface
        agent.interface_code = interface_code
        agent.interface_type = interface_type
        agent.interface_version = (agent.interface_version or 0) + 1
        agent.interface_updated_at = datetime.utcnow()
        agent.interface_validated = False
        
        db.session.commit()
        
        logger.info(f"📝 Interface uploaded: {agent.name} v{agent.interface_version}")
        
        return {
            'success': True,
            'agent_id': agent_id,
            'interface_version': agent.interface_version,
            'validated': False
        }
    
    @staticmethod
    def change_tier(
        agent_id: int,
        creator_wallet: str,
        new_tier: str,
        carry_percent: float = 0.5
    ) -> Dict[str, Any]:
        """
        Change an agent's tier with score carry.
        
        Returns:
            Dict with success status and details
        """
        new_tier = new_tier.lower()
        if new_tier not in ['alpha', 'beta', 'omega']:
            return {'success': False, 'error': 'Invalid tier. Must be alpha, beta, or omega'}
        
        agent = Agent.query.get(agent_id)
        if not agent:
            return {'success': False, 'error': 'Agent not found'}
        
        # Verify ownership
        if agent.creator_wallet != creator_wallet:
            return {'success': False, 'error': 'Not authorized. Must be agent creator.'}
        
        old_tier = agent.tier or 'alpha'
        
        if old_tier == new_tier:
            return {'success': False, 'error': f'Agent is already in {new_tier} tier'}
        
        # Apply tier change with score carry
        old_score = agent.current_score
        agent.tier = new_tier
        agent.previous_score = old_score
        agent.current_score = round(old_score * carry_percent, 1)
        
        db.session.commit()
        
        logger.info(f"🔄 Tier changed: {agent.name} {old_tier} → {new_tier} (Score: {old_score} → {agent.current_score})")
        
        return {
            'success': True,
            'old_tier': old_tier,
            'new_tier': new_tier,
            'old_score': old_score,
            'new_score': agent.current_score,
            'score_carry': f'{int(carry_percent * 100)}%'
        }
    
    @staticmethod
    def agent_to_dict(agent: Agent) -> dict:
        """
        Convert agent to dictionary for JSON response.
        """
        price_lamports = agent.current_score * LAMPORTS_PER_SCORE_POINT
        price_sol = price_lamports / 1_000_000_000
        market_cap_sol = price_sol * agent.total_supply
        
        # USD values for display
        sol_price_usd = PricingService.get_sol_price_usd()
        price_usd = price_sol * sol_price_usd
        market_cap_usd = market_cap_sol * sol_price_usd
        display_price = agent.current_score * 0.01
        
        # Get tier configuration
        tier_config = get_tier_config(agent.tier) if agent.tier else TIERS['alpha']
        
        return {
            'id': agent.id,
            'wallet_address': agent.wallet_address,
            'name': agent.name,
            'description': agent.description,
            'creator_wallet': agent.creator_wallet,
            'current_score': agent.current_score,
            'previous_score': agent.previous_score,
            'raw_score': agent.raw_score,
            'was_capped': agent.was_capped,
            'type': agent.agent_type,
            'arena_type': agent.arena_type,
            'category': agent.category,
            'keywords': agent.keywords or [],
            
            # Tier info
            'tier': agent.tier or 'alpha',
            'tier_info': {
                'name': tier_config['name'],
                'emoji': tier_config['emoji'],
                'difficulty': tier_config['difficulty'],
                'max_score': tier_config['max_score'],
            },
            'score_ceiling': tier_config['max_score'],
            
            # UPI breakdown (for utility/coding)
            'effectiveness_score': agent.effectiveness_score,
            'efficiency_score': agent.efficiency_score,
            'autonomy_score': agent.autonomy_score,
            
            # Interface status
            'has_interface': bool(agent.interface_code),
            'interface_validated': agent.interface_validated or False,
            
            # Social links
            'twitter_handle': agent.twitter_handle,
            'github_url': agent.github_url,
            'website_url': agent.website_url,
            
            # Arena info
            'last_arena_run': agent.last_arena_run.isoformat() if agent.last_arena_run else None,
            
            # Stats
            'holders': agent.holders,
            'volume_24h': agent.volume_24h,
            'total_volume': agent.total_volume,
            'last_score_update': agent.last_score_update.isoformat() if agent.last_score_update else None,
            
            # Pricing
            'price_lamports': price_lamports,
            'price_sol': price_sol,
            'price_usd': price_usd,
            'display_price': display_price,
            'market_cap_sol': market_cap_sol,
            'market_cap_usd': market_cap_usd,
            
            # Token data
            'token_mint': agent.token_mint,
            'total_supply': agent.total_supply,
            'reserve_lamports': agent.reserve_lamports,
            
            # Status
            'is_active': agent.is_active,
            
            # Timestamps
            'created_at': agent.created_at.isoformat() if agent.created_at else None,
            'updated_at': agent.updated_at.isoformat() if agent.updated_at else None
        }
