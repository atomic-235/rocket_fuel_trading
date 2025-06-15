#!/usr/bin/env python3
"""
Test Hyperliquid connection and basic functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from trading_consumer.config import load_config
from trading_consumer.trading import HyperliquidExchange
from loguru import logger


async def test_connection():
    """Test basic connection and balance."""
    print("🔌 Testing Hyperliquid Connection")
    print("=" * 50)
    
    try:
        # Load config
        config = load_config()
        
        # Initialize exchange
        exchange = HyperliquidExchange(config.hyperliquid)
        await exchange.initialize()
        print("✅ Exchange initialized successfully")
        
        # Test balance
        balance = await exchange.get_balance()
        print(f"✅ Balance fetched: {len(balance)} currencies")
        
        # Show non-zero balances
        for currency, amount in balance.items():
            if amount > 0:
                print(f"   💰 {currency}: {amount}")
        
        if not any(amount > 0 for amount in balance.values()):
            print("   📊 All balances are zero")
        
        # Test ticker
        ticker = await exchange.get_ticker("ETH")
        if ticker:
            print(f"✅ ETH ticker fetched:")
            print(f"   💲 Price: ${ticker['price']}")
            print(f"   📊 Mid Price: ${ticker['mid_price']}")
            print(f"   📈 Mark Price: ${ticker['mark_price']}")
            print(f"   ⚡ Max Leverage: {ticker['max_leverage']}x")
        
        # Test positions (check ETH specifically)
        eth_positions = await exchange.get_positions("ETH")
        all_positions = await exchange.get_positions()
        
        print(f"✅ Positions fetched: {len(all_positions)} total, {len(eth_positions)} ETH")
        
        if eth_positions:
            print("   🎯 ETH Positions:")
            for pos in eth_positions:
                print(f"      {pos.symbol}: {pos.size} ({pos.side.value})")
                print(f"      Entry: ${pos.entry_price}, Current: ${pos.current_price}")
                print(f"      PnL: ${pos.unrealized_pnl}")
        
        if all_positions:
            print("   📊 All Positions:")
            for pos in all_positions:
                print(f"      {pos.symbol}: {pos.size} ({pos.side.value})")
        
        if not all_positions:
            print("   📈 No active positions")
        
        await exchange.close()
        print("✅ Connection test completed successfully!")
        
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        print(f"❌ Connection test failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    asyncio.run(test_connection()) 