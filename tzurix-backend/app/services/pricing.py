"""
Pricing Service
Handles all price calculations with NO HTTP dependencies.
"""

from dataclasses import dataclass
from typing import Optional
import logging
import requests

from app.config import (
    LAMPORTS_PER_SCORE_POINT, TOTAL_SUPPLY, SOL_PRICE_USD, BIRDEYE_API_KEY
)

logger = logging.getLogger(__name__)


@dataclass
class PriceData:
    """Complete price information for an agent."""
    score: float
    price_lamports: int
    price_sol: float
    price_usd: float
    display_price: float  # score * 0.01
    market_cap_sol: float
    market_cap_usd: float
    sol_price_usd: float


class PricingService:
    """
    Price calculation service.
    Pure functions, minimal external dependencies.
    """
    
    _cached_sol_price: float = SOL_PRICE_USD
    
    @classmethod
    def get_sol_price_usd(cls, use_cache: bool = True) -> float:
        """
        Fetch current SOL price from BirdEye or return cached/default.
        
        Args:
            use_cache: If True and cache exists, return cached value
        """
        if use_cache and cls._cached_sol_price:
            return cls._cached_sol_price
        
        try:
            if BIRDEYE_API_KEY:
                response = requests.get(
                    "https://public-api.birdeye.so/defi/price",
                    params={"address": "So11111111111111111111111111111111111111112"},
                    headers={"X-API-KEY": BIRDEYE_API_KEY},
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        cls._cached_sol_price = data['data']['value']
                        logger.info(f"SOL price updated: ${cls._cached_sol_price:.2f}")
                        return cls._cached_sol_price
        except Exception as e:
            logger.warning(f"Could not fetch SOL price: {e}")
        
        return cls._cached_sol_price or SOL_PRICE_USD
    
    @classmethod
    def calculate_price(cls, score: float, sol_price_usd: Optional[float] = None) -> PriceData:
        """
        Calculate all price data for a given score.
        
        Args:
            score: Agent's current score
            sol_price_usd: Optional SOL price, fetches if not provided
        
        Returns:
            PriceData with all price information
        """
        if sol_price_usd is None:
            sol_price_usd = cls.get_sol_price_usd()
        
        price_lamports = int(score * LAMPORTS_PER_SCORE_POINT)
        price_sol = price_lamports / 1_000_000_000
        price_usd = price_sol * sol_price_usd
        market_cap_sol = price_sol * TOTAL_SUPPLY
        market_cap_usd = market_cap_sol * sol_price_usd
        display_price = score * 0.01
        
        return PriceData(
            score=score,
            price_lamports=price_lamports,
            price_sol=price_sol,
            price_usd=price_usd,
            display_price=display_price,
            market_cap_sol=market_cap_sol,
            market_cap_usd=market_cap_usd,
            sol_price_usd=sol_price_usd
        )
    
    @classmethod
    def to_dict(cls, price_data: PriceData) -> dict:
        """Convert PriceData to dictionary for JSON response."""
        return {
            'score': price_data.score,
            'price_lamports': price_data.price_lamports,
            'price_sol': price_data.price_sol,
            'price_usd': price_data.price_usd,
            'display_price': price_data.display_price,
            'market_cap_sol': price_data.market_cap_sol,
            'market_cap_usd': price_data.market_cap_usd,
            'sol_price_usd': price_data.sol_price_usd
        }
