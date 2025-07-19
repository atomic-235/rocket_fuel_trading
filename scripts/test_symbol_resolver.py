#!/usr/bin/env python3
"""
Test script to check Hyperliquid symbol resolution and see what's available.
"""

import os
import sys
import asyncio

# Add the trading_consumer module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from trading_consumer.trading.exchange import HyperliquidExchange
from trading_consumer.utils.symbol_resolver import get_symbol_resolver
from trading_consumer.config import load_config


async def test_hyperliquid_markets():
    """Test what markets are available on Hyperliquid."""
    print("🔍 Testing Hyperliquid Market Access")
    print("=" * 50)
    
    try:
        # Load config
        config = load_config()
        
        # Initialize exchange
        exchange = HyperliquidExchange(config.hyperliquid)
        await exchange.initialize()
        
        print("✅ Exchange connection successful")
        
        # Get raw markets
        print("\n📊 Loading raw markets...")
        markets = exchange.exchange.load_markets()
        print(f"✅ Found {len(markets)} total markets")
        
        # Show sample markets
        print("\n🔍 Sample markets:")
        sample_markets = list(markets.keys())[:15]
        for market in sample_markets:
            print(f"   {market}")
        
        # Look for PEPE-related markets specifically
        print("\n🐸 Searching for PEPE-related markets...")
        pepe_markets = [m for m in markets.keys() if 'PEPE' in m.upper()]
        
        if pepe_markets:
            print(f"✅ Found PEPE markets: {pepe_markets}")
        else:
            print("❌ No PEPE markets found!")
            
            # Look for similar
            similar = [m for m in markets.keys() if 'PEP' in m.upper() or 'FROG' in m.upper()]
            if similar:
                print(f"🔍 Similar markets: {similar}")
        
        # Look for k-prefixed tokens
        print("\n🔍 Looking for k-prefixed tokens...")
        k_markets = [m for m in markets.keys() if m.startswith('k') and '/USDC:USDC' in m]
        print(f"✅ Found {len(k_markets)} k-prefixed markets:")
        for market in k_markets[:10]:  # Show first 10
            print(f"   {market}")
        if len(k_markets) > 10:
            print(f"   ... and {len(k_markets) - 10} more")
            
        await exchange.close()
        return True
        
    except Exception as e:
        print(f"❌ Error testing markets: {e}")
        return False


async def test_symbol_resolver():
    """Test the symbol resolver specifically."""
    print("\n🧪 Testing Symbol Resolver")
    print("=" * 50)
    
    try:
        # Load config and setup
        config = load_config()
        exchange = HyperliquidExchange(config.hyperliquid)
        await exchange.initialize()
        
        # Get symbol resolver
        resolver = get_symbol_resolver()
        resolver.set_exchange(exchange.exchange)
        
        # Test symbols
        test_symbols = ['PEPE', 'BTC', 'ETH', 'XRP', 'DOGE']
        
        print("🔍 Testing symbol resolution:")
        for symbol in test_symbols:
            print(f"\n   Testing: {symbol}")
            resolved = await resolver.resolve_symbol(symbol)
            if resolved:
                print(f"   ✅ {symbol} → {resolved}")
            else:
                print(f"   ❌ {symbol} → Not found")
        
        # Get all available symbols
        print("\n📋 Getting all available symbols...")
        available = await resolver.get_available_symbols()
        print(f"✅ Found {len(available)} total symbols")
        
        # Show PEPE-related symbols
        pepe_symbols = [s for s in available if 'PEPE' in s.upper()]
        if pepe_symbols:
            print(f"🐸 PEPE symbols: {pepe_symbols}")
        else:
            print("❌ No PEPE symbols found in available list")
        
        # Show k-prefixed symbols
        k_symbols = [s for s in available if s.startswith('k')]
        print(f"\n🔍 k-prefixed symbols ({len(k_symbols)} total):")
        for symbol in sorted(k_symbols)[:15]:  # Show first 15
            print(f"   {symbol}")
        if len(k_symbols) > 15:
            print(f"   ... and {len(k_symbols) - 15} more")
            
        await exchange.close()
        return True
        
    except Exception as e:
        print(f"❌ Error testing symbol resolver: {e}")
        return False


async def main():
    """Main test function."""
    print("🧪 Hyperliquid Symbol Resolution Test")
    print("=" * 60)
    
    success = True
    
    try:
        # Test market access
        success &= await test_hyperliquid_markets()
        
        # Test symbol resolver
        success &= await test_symbol_resolver()
        
        if success:
            print("\n🎉 All tests completed successfully!")
            print("\n💡 If PEPE is missing, it might have been:")
            print("   - Delisted from Hyperliquid")
            print("   - Renamed to a different symbol")
            print("   - Moved to a different market format")
        else:
            print("\n❌ Some tests failed!")
            
    except Exception as e:
        print(f"\n💥 Test suite failed: {e}")
        success = False
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 