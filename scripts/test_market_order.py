#!/usr/bin/env python3
"""
Test Hyperliquid market orders (REAL MONEY - BE CAREFUL!).
"""

import asyncio
import sys
import time
from pathlib import Path
from decimal import Decimal

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(override=True)

from trading_consumer.config import load_config
from trading_consumer.trading import HyperliquidExchange
from trading_consumer.models.trading import TradeOrder, OrderType, SignalType
from loguru import logger


async def test_market_order(execute_real_trade=False):
    """Test market order execution."""
    print("🚀 Testing Hyperliquid Market Orders")
    if execute_real_trade:
        print("⚠️  REAL MONEY MODE - ACTUAL TRADES WILL BE EXECUTED!")
    else:
        print("🔒 DEMO MODE - No real trades will be executed")
    print("=" * 50)
    
    try:
        # Load config
        config = load_config()
        
        # Initialize exchange
        exchange = HyperliquidExchange(config.hyperliquid)
        await exchange.initialize()
        print("✅ Exchange initialized")
        
        # Get current ETH price
        ticker = await exchange.get_ticker("ETH")
        if not ticker:
            print("❌ Failed to get ETH ticker")
            return False
        
        current_price = float(ticker['mid_price'])
        print(f"📊 Current ETH price: ${current_price:,.2f}")
        
        # Calculate $12 USD worth of ETH (above minimum order size)
        usd_amount = 12.0
        eth_amount = round(usd_amount / current_price, 6)
        print(f"💰 $12 USD = {eth_amount} ETH")
        
        # Set 2x leverage first
        print(f"\n⚡ Setting 2x leverage...")
        leverage_set = await exchange.set_leverage("ETH", 2, "cross")
        if leverage_set:
            print("✅ Leverage set to 2x")
        else:
            print("❌ Failed to set leverage")
        
        if not execute_real_trade:
            print("\n🔒 DEMO MODE: Would create market BUY order:")
            print(f"   Amount: {eth_amount} ETH (~$12 USD)")
            print(f"   Price: ${current_price:,.2f}")
            print(f"   Leverage: 2x")
            print("\n💡 To execute real trades, run with --execute flag")
            return True
        
        # REAL TRADE EXECUTION
        print(f"\n⚠️  CREATING REAL MARKET ORDER!")
        print(f"   Amount: {eth_amount} ETH (~$12 USD)")
        print(f"   Price: ${current_price:,.2f}")
        print(f"   Leverage: 2x")
        
        # Confirm with user
        print("\n⏳ Executing in 3 seconds... (Ctrl+C to cancel)")
        time.sleep(3)
        
        market_order = TradeOrder(
            symbol="ETH",
            side=SignalType.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal(str(eth_amount)),
            leverage=2
        )
        
        # Execute market order
        result = await exchange.create_order(market_order)
        
        if result and result.id:
            print(f"✅ Market order executed: {result.id}")
            print(f"   Status: {result.status.value}")
            print(f"   Filled: {result.filled_quantity}")
            if result.average_price:
                print(f"   Avg Price: ${result.average_price}")
            
            # Wait and check positions
            print("\n⏳ Waiting 5 seconds for position update...")
            time.sleep(5)
            
            # Check ETH positions specifically (like user's examples)
            positions = await exchange.get_positions("ETH")
            print(f"positions: {positions}")
            eth_position = positions[0] if positions else None
            
            if eth_position:
                print(f"✅ Position opened:")
                print(f"   Size: {eth_position.size} ETH")
                print(f"   Side: {eth_position.side.value}")
                print(f"   Entry Price: ${eth_position.entry_price}")
                print(f"   Current Price: ${eth_position.current_price}")
                print(f"   Unrealized PnL: ${eth_position.unrealized_pnl}")
                print(f"   Leverage: {eth_position.leverage}x")
                
                # Ask if user wants to close position
                print(f"\n🔄 Position is now open. Close it immediately? (y/n)")
                # For automation, we'll close it after 10 seconds
                print("⏳ Auto-closing in 10 seconds...")
                time.sleep(10)
                
                close_result = await exchange.close_position("ETH")
                if close_result:
                    print(f"✅ Position closed: {close_result['id']}")
                else:
                    print("❌ Failed to close position")
            else:
                print("❌ No ETH position found after order")
        else:
            print("❌ Failed to execute market order")
            return False
        
        await exchange.close()
        print("\n✅ Market order test completed!")
        
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
        return False
    except Exception as e:
        logger.error(f"Market order test failed: {e}")
        print(f"❌ Market order test failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Hyperliquid market orders")
    parser.add_argument("--execute", action="store_true", 
                       help="Execute real trades (REAL MONEY!)")
    
    args = parser.parse_args()
    
    asyncio.run(test_market_order(args.execute)) 