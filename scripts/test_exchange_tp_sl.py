#!/usr/bin/env python3
"""
Test TP/SL functionality using our exchange wrapper.
"""

import asyncio
import sys
import time
from pathlib import Path
from decimal import Decimal

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from trading_consumer.config import load_config
from trading_consumer.trading import HyperliquidExchange
from trading_consumer.models.trading import TradeOrder, OrderType, SignalType
from loguru import logger


async def test_exchange_tp_sl(execute_real_trade=False):
    """Test TP/SL using our exchange wrapper."""
    print("🎯 Testing Exchange Wrapper TP/SL")
    if execute_real_trade:
        print("⚠️  REAL MONEY MODE - ACTUAL TRADES WILL BE EXECUTED!")
    else:
        print("🔒 DEMO MODE - No real trades will be executed")
    print("=" * 60)
    
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
        
        # Calculate order size ($12 USD worth)
        usd_amount = 12.0
        eth_amount = round(usd_amount / current_price, 6)
        print(f"💰 Order size: {eth_amount} ETH (${usd_amount} USD)")
        
        # Calculate TP/SL prices
        tp_price = current_price * 1.05  # 5% profit
        sl_price = current_price * 0.98  # 2% loss
        
        print(f"\n🎯 TP/SL Prices:")
        print(f"   📈 Take Profit: ${tp_price:,.2f} (+5%)")
        print(f"   📉 Stop Loss: ${sl_price:,.2f} (-2%)")
        
        if not execute_real_trade:
            print("\n🔒 DEMO MODE: Would execute:")
            print("1. Set 2x leverage")
            print("2. Create market BUY order")
            print("3. Create TP/SL orders automatically")
            print("4. Monitor and close")
            print("\n💡 To execute real trades, run with --execute flag")
            return True
        
        # REAL TRADE EXECUTION
        print(f"\n⚠️  EXECUTING REAL TRADES!")
        print("⏳ Starting in 3 seconds... (Ctrl+C to cancel)")
        time.sleep(3)
        
        # Step 1: Set leverage
        print(f"\n⚡ Step 1: Setting 2x leverage...")
        leverage_set = await exchange.set_leverage("ETH", 2, "cross")
        if leverage_set:
            print("✅ Leverage set to 2x")
        else:
            print("❌ Failed to set leverage")
            return False
        
        # Step 2: Create market order
        print(f"\n🚀 Step 2: Creating market BUY order...")
        market_order = TradeOrder(
            symbol="ETH",
            side=SignalType.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal(str(eth_amount))
        )
        
        result = await exchange.create_order(market_order)
        
        if result and result.id:
            print(f"✅ Market order created: {result.id}")
            print(f"   Status: {result.status.value}")
            print(f"   Filled: {result.filled_quantity}")
        else:
            print("❌ Failed to create market order")
            return False
        
        # Step 3: Create TP/SL orders (our wrapper handles waiting for position)
        print(f"\n🎯 Step 3: Creating TP/SL orders...")
        
        tp_sl_orders = await exchange.create_tp_sl_orders(
            symbol="ETH",
            tp_price=tp_price,
            sl_price=sl_price
        )
        
        if tp_sl_orders:
            print(f"✅ Created {len(tp_sl_orders)} TP/SL orders:")
            for order in tp_sl_orders:
                print(f"   Order {order['id']}: {order['side']} @ ${order.get('price', 'conditional')}")
        else:
            print("❌ No TP/SL orders created")
        
        # Step 4: Monitor
        print(f"\n⏳ Step 4: Monitoring for 10 seconds...")
        time.sleep(10)
        
        # Check open orders
        open_orders = await exchange.get_open_orders("ETH")
        print(f"📋 Open orders: {len(open_orders)}")
        
        # Step 5: Close position
        print(f"\n🔄 Step 5: Closing position...")
        close_result = await exchange.close_position("ETH")
        
        if close_result:
            print(f"✅ Position closed: {close_result['id']}")
            
            # Cancel any remaining TP/SL orders
            time.sleep(2)
            remaining_orders = await exchange.get_open_orders("ETH")
            if remaining_orders:
                print(f"\n❌ Cancelling {len(remaining_orders)} remaining orders...")
                for order in remaining_orders:
                    cancelled = await exchange.cancel_order(order['id'], "ETH")
                    if cancelled:
                        print(f"   ✅ Cancelled {order['id']}")
        else:
            print("❌ Failed to close position")
        
        await exchange.close()
        print("\n✅ Exchange wrapper TP/SL test completed!")
        
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
        return False
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"❌ Test failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test exchange wrapper TP/SL")
    parser.add_argument("--execute", action="store_true", 
                       help="Execute real trades (REAL MONEY!)")
    
    args = parser.parse_args()
    
    asyncio.run(test_exchange_tp_sl(args.execute)) 