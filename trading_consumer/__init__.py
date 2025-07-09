"""
Trading Consumer Package

Independent trading consumer that reads Telegram messages and executes trades on Hyperliquid.
"""

__version__ = "0.1.2"
__author__ = "Trading Bot"

from .config import TradingConfig
from .models import TradingSignal, TradeOrder, TradeResult

__all__ = [
    "TradingConfig",
    "TradingSignal", 
    "TradeOrder",
    "TradeResult",
] 