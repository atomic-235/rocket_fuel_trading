#!/usr/bin/env python3
"""
Test symbol checking logic for a specific token.
Check if PEPE exists, if not check kPEPE, etc.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from trading_consumer.config import load_config
from trading_consumer.trading import HyperliquidExchange


async def check_symbol_exists(exchange, symbol):
    """Check if a symbol exists on Hyperliquid."""
    try:
        markets = exchange.exchange.load_markets()
        
        # Extract symbols (remove /USDC:USDC suffix)
        available_symbols = set()
        for market_symbol in markets.keys():
            if '/USDC:USDC' in market_symbol:
                clean_symbol = market_symbol.split('/')[0]
                available_symbols.add(clean_symbol)
        
        return symbol in available_symbols, available_symbols
        
    except Exception as e:
        print(f"❌ Error checking symbols: {e}")
        return False, set()


async def test_symbol_logic(test_symbol="PEPE"):
    """Test the symbol checking logic."""
    print(f"🧪 Testing symbol logic for: {test_symbol}")
    print("=" * 50)
    
    try:
        # Load config and initialize exchange
        config = load_config()
        exchange = HyperliquidExchange(config.hyperliquid)
        await exchange.initialize()
        print("✅ Exchange connected")
        
        # Get all available symbols
        symbol_exists, all_symbols = await check_symbol_exists(exchange, test_symbol)
        
        print(f"\n📊 Found {len(all_symbols)} total symbols on Hyperliquid")
        
        # Test the logic
        print(f"\n🔍 Testing symbol: {test_symbol}")
        
        # Step 1: Check if original symbol exists
        if symbol_exists:
            print(f"✅ {test_symbol} exists - can trade directly")
            result = test_symbol
        else:
            print(f"❌ {test_symbol} does not exist")
            
            # Step 2: Check if k-prefixed version exists
            k_symbol = f"k{test_symbol}"
            k_exists, _ = await check_symbol_exists(exchange, k_symbol)
            
            if k_exists:
                print(f"✅ {k_symbol} exists - use k-prefixed version")
                result = k_symbol
            else:
                print(f"❌ {k_symbol} does not exist either")
                print(f"🚫 Cannot trade {test_symbol} - no valid symbol found")
                result = None
        
        # Show some sample symbols for reference
        print("\n📋 Sample available symbols:")
        sample_symbols = sorted(list(all_symbols))[:20]
        for symbol in sample_symbols:
            print(f"  {symbol}")
        if len(all_symbols) > 20:
            print(f"  ... and {len(all_symbols) - 20} more")
        
        # Check for k-prefix patterns
        k_symbols = [s for s in all_symbols if s.startswith('k')]
        print(f"\n🔍 Symbols with 'k' prefix: {len(k_symbols)}")
        if k_symbols:
            print("Sample k-symbols:")
            for symbol in sorted(k_symbols)[:10]:
                print(f"  {symbol}")
        
        await exchange.close()
        
        # Final result
        print("\n🎯 RESULT:")
        if result:
            print(f"✅ Trade symbol: {result}")
            print("📊 Can proceed with trading")
        else:
            print(f"❌ Cannot trade {test_symbol}")
            print("🚫 Skip this trade")
        
        return result
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return None


if __name__ == "__main__":
    # Test with different symbols
    test_symbols = ["PEPE", "ETH", "BTC", "FLOKI", "SHIB"]
    
    if len(sys.argv) > 1:
        # Use symbol from command line
        test_symbols = [sys.argv[1].upper()]
    
    async def run_tests():
        for symbol in test_symbols:
            _ = await test_symbol_logic(symbol)
            print(f"\n{'='*60}\n")
    
    asyncio.run(run_tests()) 