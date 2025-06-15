"""
Symbol mapper for handling exchange-specific symbol differences.
"""

from typing import Dict, Optional
from loguru import logger


class SymbolMapper:
    """Maps symbols to exchange-specific formats."""
    
    def __init__(self):
        """Initialize symbol mapper with exchange-specific mappings."""
        
        # Hyperliquid-specific symbol mappings
        self.hyperliquid_mappings = {
            # 1000x tokens (kilo tokens)
            'PEPE': 'kPEPE',      # 1000 PEPE = 1 kPEPE
            'FLOKI': 'kFLOKI',    # 1000 FLOKI = 1 kFLOKI
            'SHIB': 'kSHIB',      # 1000 SHIB = 1 kSHIB
            'BONK': 'kBONK',      # 1000 BONK = 1 kBONK
            'LUNC': 'kLUNC',      # 1000 LUNC = 1 kLUNC
            'NEIRO': 'kNEIRO',    # 1000 NEIRO = 1 kNEIRO
            'DOGS': 'kDOGS',      # 1000 DOGS = 1 kDOGS
            # Other Hyperliquid-specific mappings can be added here
            # 'ORIGINAL': 'HYPERLIQUID_SYMBOL',
        }
        
        # Reverse mapping for display purposes
        self.hyperliquid_reverse = {v: k for k, v in self.hyperliquid_mappings.items()}
    
    def map_to_hyperliquid(self, symbol: str) -> str:
        """
        Map a standard symbol to Hyperliquid format.
        
        Args:
            symbol: Standard symbol (e.g., 'PEPE')
            
        Returns:
            Hyperliquid symbol (e.g., 'kPEPE') or original if no mapping exists
        """
        symbol = symbol.upper().strip()
        mapped = self.hyperliquid_mappings.get(symbol, symbol)
        
        if mapped != symbol:
            logger.info(f"🔄 Mapped symbol {symbol} → {mapped} for Hyperliquid")
        
        return mapped
    
    def map_from_hyperliquid(self, symbol: str) -> str:
        """
        Map a Hyperliquid symbol back to standard format.
        
        Args:
            symbol: Hyperliquid symbol (e.g., 'kPEPE')
            
        Returns:
            Standard symbol (e.g., 'PEPE') or original if no mapping exists
        """
        symbol = symbol.upper().strip()
        mapped = self.hyperliquid_reverse.get(symbol, symbol)
        
        if mapped != symbol:
            logger.info(f"🔄 Mapped symbol {symbol} → {mapped} from Hyperliquid")
        
        return mapped
    
    def get_quantity_multiplier(self, original_symbol: str, exchange_symbol: str) -> float:
        """
        Get the quantity multiplier when mapping between symbols.
        
        For kilo tokens (k prefix), 1 exchange unit = 1000 original units
        
        Args:
            original_symbol: Original symbol (e.g., 'PEPE')
            exchange_symbol: Exchange symbol (e.g., 'kPEPE')
            
        Returns:
            Multiplier to convert original quantity to exchange quantity
        """
        original_symbol = original_symbol.upper().strip()
        exchange_symbol = exchange_symbol.upper().strip()
        
        # Check if it's a kilo token mapping
        if (original_symbol in self.hyperliquid_mappings and 
            self.hyperliquid_mappings[original_symbol] == exchange_symbol and
            exchange_symbol.startswith('K')):
            return 0.001  # 1000 original = 1 exchange
        
        return 1.0  # No conversion needed
    
    def is_kilo_token(self, symbol: str) -> bool:
        """
        Check if a symbol is a kilo token (1000x).
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if it's a kilo token
        """
        symbol = symbol.upper().strip()
        return symbol.startswith('K') and symbol in self.hyperliquid_reverse
    
    def add_mapping(self, original: str, exchange: str) -> None:
        """
        Add a new symbol mapping.
        
        Args:
            original: Original symbol
            exchange: Exchange-specific symbol
        """
        original = original.upper().strip()
        exchange = exchange.upper().strip()
        
        self.hyperliquid_mappings[original] = exchange
        self.hyperliquid_reverse[exchange] = original
        
        logger.info(f"➕ Added symbol mapping: {original} → {exchange}")


# Global symbol mapper instance
symbol_mapper = SymbolMapper() 