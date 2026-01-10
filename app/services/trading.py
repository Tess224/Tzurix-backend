"""
Trading Service
Handles buy/sell logic with NO HTTP dependencies.
"""

from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

from app.models import db, Agent, User, Trade, Holding
from app.config import TRADE_FEE_PERCENT
from app.services.pricing import PricingService

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Result of a trade execution."""
    success: bool
    trade: Trade = None
    holding: Holding = None
    error: str = None


class TradingService:
    """
    Trading service for buy/sell operations.
    """
    
    @staticmethod
    def get_quote(
        agent_id: int,
        side: str,
        amount: float
    ) -> Dict[str, Any]:
        """
        Get a price quote for buying or selling.
        
        Args:
            agent_id: ID of agent to trade
            side: 'buy' or 'sell'
            amount: SOL amount (buy) or token amount (sell)
        
        Returns:
            Quote details
        """
        agent = Agent.query.get(agent_id)
        if not agent:
            return {'success': False, 'error': 'Agent not found'}
        
        price_data = PricingService.calculate_price(agent.current_score)
        
        if side == 'buy':
            sol_amount = amount
            sol_after_fee = sol_amount * (1 - TRADE_FEE_PERCENT)
            tokens_received = int(sol_after_fee / price_data.price_sol)
            
            return {
                'success': True,
                'side': 'buy',
                'agent_id': agent_id,
                'agent_name': agent.name,
                'sol_amount': sol_amount,
                'fee_sol': sol_amount * TRADE_FEE_PERCENT,
                'tokens_received': tokens_received,
                'price_per_token_lamports': price_data.price_lamports,
                'price_per_token_sol': price_data.price_sol,
                'price_per_token_usd': price_data.price_usd,
                'current_score': agent.current_score
            }
        else:  # sell
            token_amount = int(amount)
            sol_before_fee = token_amount * price_data.price_sol
            sol_received = sol_before_fee * (1 - TRADE_FEE_PERCENT)
            
            return {
                'success': True,
                'side': 'sell',
                'agent_id': agent_id,
                'agent_name': agent.name,
                'token_amount': token_amount,
                'sol_before_fee': sol_before_fee,
                'fee_sol': sol_before_fee * TRADE_FEE_PERCENT,
                'sol_received': sol_received,
                'price_per_token_lamports': price_data.price_lamports,
                'price_per_token_sol': price_data.price_sol,
                'price_per_token_usd': price_data.price_usd,
                'current_score': agent.current_score
            }
    
    @staticmethod
    def execute_buy(
        agent_id: int,
        trader_wallet: str,
        sol_amount: float,
        tx_signature: str = None
    ) -> TradeResult:
        """
        Execute a buy order.
        
        Args:
            agent_id: ID of agent to buy
            trader_wallet: Buyer's wallet address
            sol_amount: Amount of SOL to spend
            tx_signature: On-chain transaction signature
        
        Returns:
            TradeResult with trade details
        """
        agent = Agent.query.get(agent_id)
        if not agent:
            return TradeResult(success=False, error='Agent not found')
        
        price_data = PricingService.calculate_price(agent.current_score)
        sol_after_fee = sol_amount * (1 - TRADE_FEE_PERCENT)
        tokens_received = int(sol_after_fee / price_data.price_sol)
        sol_lamports = int(sol_amount * 1_000_000_000)
        
        # Get or create user
        user = User.query.filter_by(wallet_address=trader_wallet).first()
        if not user:
            user = User(wallet_address=trader_wallet)
            db.session.add(user)
            db.session.flush()
        
        # Create trade record
        trade = Trade(
            agent_id=agent_id,
            trader_wallet=trader_wallet,
            side='buy',
            token_amount=tokens_received,
            sol_amount=sol_lamports,
            price_at_trade=price_data.price_sol,
            score_at_trade=agent.current_score,
            tx_signature=tx_signature
        )
        db.session.add(trade)
        
        # Update or create holding
        holding = Holding.query.filter_by(user_id=user.id, agent_id=agent_id).first()
        if holding:
            total_cost = (holding.token_amount * holding.avg_buy_price) + (tokens_received * price_data.price_sol)
            total_tokens = holding.token_amount + tokens_received
            holding.avg_buy_price = total_cost / total_tokens if total_tokens > 0 else 0
            holding.token_amount = total_tokens
        else:
            holding = Holding(
                user_id=user.id,
                agent_id=agent_id,
                token_amount=tokens_received,
                avg_buy_price=price_data.price_sol
            )
            db.session.add(holding)
        
        # Update agent reserves
        agent.reserve_lamports += sol_lamports
        agent.last_trade_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ BUY: {trader_wallet[:8]}... bought {tokens_received} {agent.name} tokens for {sol_amount} SOL")
        
        return TradeResult(success=True, trade=trade, holding=holding)
    
    @staticmethod
    def execute_sell(
        agent_id: int,
        trader_wallet: str,
        token_amount: int,
        tx_signature: str = None
    ) -> TradeResult:
        """
        Execute a sell order.
        
        Args:
            agent_id: ID of agent to sell
            trader_wallet: Seller's wallet address
            token_amount: Number of tokens to sell
            tx_signature: On-chain transaction signature
        
        Returns:
            TradeResult with trade details
        """
        agent = Agent.query.get(agent_id)
        if not agent:
            return TradeResult(success=False, error='Agent not found')
        
        user = User.query.filter_by(wallet_address=trader_wallet).first()
        if not user:
            return TradeResult(success=False, error='User not found')
        
        holding = Holding.query.filter_by(user_id=user.id, agent_id=agent_id).first()
        if not holding or holding.token_amount < token_amount:
            return TradeResult(success=False, error='Insufficient tokens')
        
        price_data = PricingService.calculate_price(agent.current_score)
        sol_before_fee = token_amount * price_data.price_sol
        sol_received = sol_before_fee * (1 - TRADE_FEE_PERCENT)
        sol_lamports = int(sol_received * 1_000_000_000)
        
        if agent.reserve_lamports < sol_lamports:
            return TradeResult(success=False, error='Insufficient reserve liquidity')
        
        # Create trade record
        trade = Trade(
            agent_id=agent_id,
            trader_wallet=trader_wallet,
            side='sell',
            token_amount=token_amount,
            sol_amount=sol_lamports,
            price_at_trade=price_data.price_usd,
            score_at_trade=agent.current_score,
            tx_signature=tx_signature
        )
        db.session.add(trade)
        
        # Update holding and reserves
        holding.token_amount -= token_amount
        agent.reserve_lamports -= sol_lamports
        agent.last_trade_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"✅ SELL: {trader_wallet[:8]}... sold {token_amount} {agent.name} tokens for {sol_received:.4f} SOL")
        
        return TradeResult(success=True, trade=trade, holding=holding)
    
    @staticmethod
    def trade_to_dict(trade: Trade) -> dict:
        """Convert trade to dictionary."""
        agent = Agent.query.get(trade.agent_id)
        return {
            'id': trade.id,
            'agent_id': trade.agent_id,
            'agent_name': agent.name if agent else None,
            'trader_wallet': trade.trader_wallet,
            'side': trade.side,
            'token_amount': trade.token_amount,
            'sol_amount': trade.sol_amount,
            'sol_amount_display': trade.sol_amount / 1_000_000_000,
            'price_at_trade': trade.price_at_trade,
            'score_at_trade': trade.score_at_trade,
            'tx_signature': trade.tx_signature,
            'created_at': trade.created_at.isoformat() if trade.created_at else None
        }
    
    @staticmethod
    def holding_to_dict(holding: Holding) -> dict:
        """Convert holding to dictionary."""
        agent = Agent.query.get(holding.agent_id)
        
        price_data = PricingService.calculate_price(agent.current_score) if agent else None
        current_price_sol = price_data.price_sol if price_data else 0
        current_value_sol = holding.token_amount * current_price_sol
        
        sol_price_usd = PricingService.get_sol_price_usd()
        current_price_usd = current_price_sol * sol_price_usd
        current_value_usd = current_value_sol * sol_price_usd
        
        return {
            'id': holding.id,
            'user_id': holding.user_id,
            'agent_id': holding.agent_id,
            'agent_name': agent.name if agent else None,
            'token_amount': holding.token_amount,
            'avg_buy_price_sol': holding.avg_buy_price,
            'current_price_sol': current_price_sol,
            'current_price_usd': current_price_usd,
            'current_value_sol': current_value_sol,
            'current_value_usd': current_value_usd,
            'pnl_percent': ((current_price_sol - holding.avg_buy_price) / holding.avg_buy_price * 100) if holding.avg_buy_price else 0,
            'updated_at': holding.updated_at.isoformat() if holding.updated_at else None
        }
