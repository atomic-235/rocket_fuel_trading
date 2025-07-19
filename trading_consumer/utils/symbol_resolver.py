"""
Dynamic symbol resolver for Hyperliquid exchange.
Replaces hardcoded symbol mappings with live symbol checking.
"""

from typing import Optional, Set
from loguru import logger


class SymbolResolver:
    """Dynamic symbol resolver that checks symbol existence on exchange."""
    
    def __init__(self, exchange=None):
        """Initialize with exchange instance."""
        self.exchange = exchange
        self._available_symbols: Optional[Set[str]] = None
    
    def set_exchange(self, exchange):
        """Set the exchange instance."""
        self.exchange = exchange
        self._available_symbols = None  # Reset cache when exchange changes
    
    async def get_available_symbols(self) -> Set[str]:
        """Get all available symbols from exchange."""
        if not self.exchange:
            logger.warning("⚠️ No exchange set, cannot check symbols")
            return set()
        
        try:
            logger.debug("🔍 Loading markets from exchange...")
            markets = self.exchange.load_markets()
            logger.debug(f"📊 Found {len(markets)} total markets")
            
            # Extract symbols (remove /USDC:USDC suffix)
            symbols = set()
            for market_symbol in markets.keys():
                if '/USDC:USDC' in market_symbol:
                    symbol = market_symbol.split('/')[0]
                    symbols.add(symbol)
            
            logger.info(f"✅ Extracted {len(symbols)} perpetual symbols")
            
            # Log sample of available symbols for debugging
            if symbols:
                # Show k-prefixed tokens for reference
                k_symbols = [s for s in symbols if s.startswith('k')]
                if k_symbols:
                    logger.info(f"🔍 Available k-tokens: {sorted(k_symbols)[:10]}...")
                
                # Show sample of all symbols
                sample_symbols = sorted(list(symbols))[:15]
                logger.info(f"🔍 Sample symbols: {sample_symbols}")
            else:
                logger.warning("⚠️ No symbols extracted from markets!")
            
            self._available_symbols = symbols
            return symbols
            
        except Exception as e:
            logger.error(f"❌ Failed to get available symbols: {e}")
            return set()
    
    async def resolve_symbol(self, symbol: str) -> Optional[str]:
        """
        Resolve symbol to correct exchange format.
        
        Logic:
        1. Check if original symbol exists
        2. If not, check if k-prefixed version exists
        3. Return None if neither exists
        """
        if not symbol:
            return None
        
        symbol = symbol.upper().strip()
        logger.info(f"🔍 Resolving symbol: {symbol}")
        
        # Get available symbols (fresh each time - no caching due to new coins)
        available_symbols = await self.get_available_symbols()
        
        if not available_symbols:
            logger.warning(
                f"⚠️ Could not get symbols (available_symbols count: {len(available_symbols)}), "
                f"returning original: {symbol}"
            )
            return symbol
        
        logger.info(f"📋 Checking against {len(available_symbols)} available symbols")
        
        # Step 1: Check if original symbol exists
        if symbol in available_symbols:
            logger.info(f"✅ Symbol exists as-is: {symbol}")
            return symbol
        
        # Step 2: Check if k-prefixed version exists
        k_symbol = f"k{symbol}"
        if k_symbol in available_symbols:
            logger.info(f"🔄 Mapped symbol {symbol} → {k_symbol}")
            return k_symbol
        
        # Step 3: Symbol not found - log available symbols for debugging
        logger.warning(f"❌ Symbol not found: {symbol} (checked {symbol} and {k_symbol})")
        logger.debug(f"🔍 Available symbols: {sorted(list(available_symbols))[:20]}...")  # Show first 20
        return None
    
    async def symbol_exists(self, symbol: str) -> bool:
        """Check if symbol exists in any form."""
        resolved = await self.resolve_symbol(symbol)
        return resolved is not None


# Global resolver instance
_global_resolver = SymbolResolver()


def get_symbol_resolver() -> SymbolResolver:
    """Get the global symbol resolver instance."""
    return _global_resolver


async def resolve_symbol_for_trading(symbol: str, exchange=None) -> Optional[str]:
    """
    Convenience function to resolve a symbol for trading.
    
    Args:
        symbol: Symbol to resolve
        exchange: Exchange instance (optional, uses global if not provided)
    
    Returns:
        Resolved symbol or None if not found
    """
    resolver = get_symbol_resolver()
    
    if exchange:
        resolver.set_exchange(exchange)
    
    return await resolver.resolve_symbol(symbol) 