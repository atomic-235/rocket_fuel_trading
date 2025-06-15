"""
Main entry point for the trading consumer - Production Pipeline.
"""

import asyncio
import signal
import sys
from typing import Optional
# Removed Decimal import - using float throughout
from loguru import logger

from .config import load_config, validate_config
from .telegram import TelegramClient
from .parsers import SignalParser
from .trading import HyperliquidExchange
from .models.telegram import TelegramMessage
from .models.trading import TradingSignal, TradeOrder, OrderType, SignalType


class TradingConsumer:
    """Main trading consumer application - Production Pipeline."""
    
    def __init__(self):
        """Initialize trading consumer."""
        self.config = None
        self.telegram_client: Optional[TelegramClient] = None
        self.signal_parser: Optional[SignalParser] = None
        self.exchange: Optional[HyperliquidExchange] = None
        self._running = False
    
    async def initialize(self) -> None:
        """Initialize all components."""
        try:
            # Load configuration
            self.config = load_config()
            validate_config(self.config)
            
            # Setup logging
            self._setup_logging()
            
            # Initialize components
            self.telegram_client = TelegramClient(self.config.telegram)
            self.signal_parser = SignalParser()
            self.exchange = HyperliquidExchange(self.config.hyperliquid)
            
            # Initialize exchange connection
            await self.exchange.initialize()
            
            logger.info("🚀 Trading Consumer Production Pipeline Initialized")
            logger.info(f"📊 Default Settings: {self.config.trading.default_leverage}x leverage, {self.config.trading.default_tp_percent*100}% TP, {self.config.trading.default_sl_percent*100}% SL")
            
        except Exception as e:
            logger.error(f"Failed to initialize trading consumer: {e}")
            raise
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        logger.remove()  # Remove default handler
        
        # Add console handler
        logger.add(
            sys.stderr,
            level=self.config.logging.level,
            format=self.config.logging.format,
            colorize=True
        )
        
        # Add file handler if specified
        if self.config.logging.file:
            logger.add(
                self.config.logging.file,
                level=self.config.logging.level,
                format=self.config.logging.format,
                rotation=self.config.logging.max_file_size,
                retention=self.config.logging.backup_count
            )
    
    async def start(self) -> None:
        """Start the trading consumer."""
        if not self.config:
            await self.initialize()
        
        self._running = True
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        try:
            logger.info("🎯 Starting Trading Consumer Production Pipeline...")
            logger.info("📱 Listening for Telegram signals...")
            
            # Start Telegram client with message callback
            await self.telegram_client.start(self._handle_message)
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Error running trading consumer: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the trading consumer."""
        self._running = False
        
        logger.info("🛑 Stopping trading consumer...")
        
        # Stop components
        if self.telegram_client:
            await self.telegram_client.stop()
        
        if self.exchange:
            await self.exchange.close()
        
        logger.info("✅ Trading consumer stopped")
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self._running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _handle_message(self, message: TelegramMessage) -> None:
        """Handle incoming Telegram message."""
        try:
            user_info = ""
            if message.from_user:
                user_info = f" (User ID: {message.from_user.id})"
            
            logger.info(f"📨 Processing message from {message.sender_name}{user_info}")
            
            # Parse message for trading signals
            signal = self.signal_parser.parse_message(message)
            
            if not signal:
                logger.debug("No trading signal found in message")
                return
            
            # Check confidence threshold
            if signal.confidence < self.config.trading.min_confidence:
                logger.info(
                    f"⚠️ Signal confidence {signal.confidence:.2f} below threshold "
                    f"{self.config.trading.min_confidence:.2f}, skipping"
                )
                return
            
            # Execute trade
            await self._execute_signal(signal)
            
        except Exception as e:
            logger.error(f"❌ Error handling message: {e}")
    
    async def _execute_signal(self, signal: TradingSignal) -> None:
        """Execute trading signal - Full Production Implementation."""
        try:
            logger.info(f"🎯 Executing Signal: {signal.signal_type.value} {signal.symbol} (confidence: {signal.confidence:.2f})")
            
            # Handle different signal types
            if signal.signal_type in [SignalType.BUY, SignalType.LONG]:
                await self._execute_buy_signal(signal)
            elif signal.signal_type in [SignalType.SELL, SignalType.SHORT]:
                await self._execute_sell_signal(signal)
            elif signal.signal_type == SignalType.CLOSE:
                await self._execute_close_signal(signal)
            else:
                logger.warning(f"⚠️ Unknown signal type: {signal.signal_type}")
                
        except Exception as e:
            logger.error(f"❌ Error executing signal: {e}")
    
    async def _execute_buy_signal(self, signal: TradingSignal) -> None:
        """Execute buy/long signal."""
        try:
            symbol = signal.symbol
            
            # Get current price
            ticker = await self.exchange.get_ticker(symbol)
            if not ticker:
                logger.error(f"❌ Failed to get ticker for {symbol}")
                return
            
            current_price = float(ticker['mid_price'])
            logger.info(f"📊 Current {symbol} price: ${current_price:,.2f}")
            
            # Calculate position size
            if signal.quantity:
                quantity = float(signal.quantity)
            else:
                # Use default USD amount
                quantity = round(self.config.trading.default_position_size_usd / current_price, 6)
            
            logger.info(f"💰 Position size: {quantity} {symbol} (~${quantity * current_price:.2f} USD)")
            
            # Set leverage (use signal leverage or default)
            leverage = signal.leverage if signal.leverage else self.config.trading.default_leverage
            logger.info(f"⚡ Setting {leverage}x leverage...")
            
            leverage_set = await self.exchange.set_leverage(symbol, leverage, "cross")
            if not leverage_set:
                logger.error(f"❌ Failed to set leverage for {symbol}")
                return
            
            # Calculate TP/SL prices
            entry_price = float(signal.price) if signal.price else current_price
            
            if signal.take_profit:
                tp_price = float(signal.take_profit)
            else:
                tp_price = entry_price * (1 + self.config.trading.default_tp_percent)  # 5% profit
            
            if signal.stop_loss:
                sl_price = float(signal.stop_loss)
            else:
                sl_price = entry_price * (1 - self.config.trading.default_sl_percent)  # 2% loss
            
            logger.info(f"🎯 TP/SL Prices:")
            logger.info(f"   📈 Take Profit: ${tp_price:,.2f} (+{((tp_price/entry_price)-1)*100:.1f}%)")
            logger.info(f"   📉 Stop Loss: ${sl_price:,.2f} ({((sl_price/entry_price)-1)*100:.1f}%)")
            
            # Create market buy order
            logger.info(f"🚀 Creating market BUY order...")
            
            market_order = TradeOrder(
                symbol=symbol,
                side=SignalType.BUY,
                order_type=OrderType.MARKET,
                quantity=quantity
            )
            
            result = await self.exchange.create_order(market_order)
            
            if result and result.id:
                logger.info(f"✅ Market order created: {result.id}")
                logger.info(f"   Status: {result.status.value}")
                logger.info(f"   Filled: {result.filled_quantity}")
                
                # Create TP/SL orders
                logger.info(f"🎯 Creating TP/SL orders...")
                
                tp_sl_orders = await self.exchange.create_tp_sl_orders(
                    symbol=symbol,
                    tp_price=tp_price,
                    sl_price=sl_price
                )
                
                if tp_sl_orders:
                    logger.info(f"✅ Created {len(tp_sl_orders)} TP/SL orders:")
                    for order in tp_sl_orders:
                        logger.info(f"   Order {order['id']}: {order['side']} @ ${order.get('price', 'conditional')}")
                else:
                    logger.warning("⚠️ No TP/SL orders created")
                
                # Log trade summary
                logger.info(f"📋 Trade Summary:")
                logger.info(f"   Symbol: {symbol}")
                logger.info(f"   Side: BUY/LONG")
                logger.info(f"   Size: {quantity} {symbol}")
                logger.info(f"   Entry: ${entry_price:,.2f}")
                logger.info(f"   Leverage: {leverage}x")
                logger.info(f"   TP: ${tp_price:,.2f}")
                logger.info(f"   SL: ${sl_price:,.2f}")
                
            else:
                logger.error("❌ Failed to create market order")
                
        except Exception as e:
            logger.error(f"❌ Error executing buy signal: {e}")
    
    async def _execute_sell_signal(self, signal: TradingSignal) -> None:
        """Execute sell/short signal."""
        try:
            symbol = signal.symbol
            
            # Get current price
            ticker = await self.exchange.get_ticker(symbol)
            if not ticker:
                logger.error(f"❌ Failed to get ticker for {symbol}")
                return
            
            current_price = float(ticker['mid_price'])
            logger.info(f"📊 Current {symbol} price: ${current_price:,.2f}")
            
            # Calculate position size
            if signal.quantity:
                quantity = float(signal.quantity)
            else:
                # Use default USD amount
                quantity = round(self.config.trading.default_position_size_usd / current_price, 6)
            
            logger.info(f"💰 Position size: {quantity} {symbol} (~${quantity * current_price:.2f} USD)")
            
            # Set leverage (use signal leverage or default)
            leverage = signal.leverage if signal.leverage else self.config.trading.default_leverage
            logger.info(f"⚡ Setting {leverage}x leverage...")
            
            leverage_set = await self.exchange.set_leverage(symbol, leverage, "cross")
            if not leverage_set:
                logger.error(f"❌ Failed to set leverage for {symbol}")
                return
            
            # Calculate TP/SL prices for SHORT
            entry_price = float(signal.price) if signal.price else current_price
            
            if signal.take_profit:
                tp_price = float(signal.take_profit)
            else:
                tp_price = entry_price * (1 - self.config.trading.default_tp_percent)  # 5% profit (price goes down)
            
            if signal.stop_loss:
                sl_price = float(signal.stop_loss)
            else:
                sl_price = entry_price * (1 + self.config.trading.default_sl_percent)  # 2% loss (price goes up)
            
            logger.info(f"🎯 TP/SL Prices (SHORT):")
            logger.info(f"   📈 Take Profit: ${tp_price:,.2f} ({((tp_price/entry_price)-1)*100:.1f}%)")
            logger.info(f"   📉 Stop Loss: ${sl_price:,.2f} (+{((sl_price/entry_price)-1)*100:.1f}%)")
            
            # Create market sell order (short)
            logger.info(f"🚀 Creating market SELL order (SHORT)...")
            
            market_order = TradeOrder(
                symbol=symbol,
                side=SignalType.SELL,
                order_type=OrderType.MARKET,
                quantity=quantity
            )
            
            result = await self.exchange.create_order(market_order)
            
            if result and result.id:
                logger.info(f"✅ Market order created: {result.id}")
                logger.info(f"   Status: {result.status.value}")
                logger.info(f"   Filled: {result.filled_quantity}")
                
                # Create TP/SL orders for SHORT position
                logger.info(f"🎯 Creating TP/SL orders for SHORT...")
                
                tp_sl_orders = await self.exchange.create_tp_sl_orders(
                    symbol=symbol,
                    tp_price=tp_price,
                    sl_price=sl_price
                )
                
                if tp_sl_orders:
                    logger.info(f"✅ Created {len(tp_sl_orders)} TP/SL orders:")
                    for order in tp_sl_orders:
                        logger.info(f"   Order {order['id']}: {order['side']} @ ${order.get('price', 'conditional')}")
                else:
                    logger.warning("⚠️ No TP/SL orders created")
                
                # Log trade summary
                logger.info(f"📋 Trade Summary:")
                logger.info(f"   Symbol: {symbol}")
                logger.info(f"   Side: SELL/SHORT")
                logger.info(f"   Size: {quantity} {symbol}")
                logger.info(f"   Entry: ${entry_price:,.2f}")
                logger.info(f"   Leverage: {leverage}x")
                logger.info(f"   TP: ${tp_price:,.2f}")
                logger.info(f"   SL: ${sl_price:,.2f}")
                
            else:
                logger.error("❌ Failed to create market order")
                
        except Exception as e:
            logger.error(f"❌ Error executing sell signal: {e}")
    
    async def _execute_close_signal(self, signal: TradingSignal) -> None:
        """Execute close signal."""
        try:
            symbol = signal.symbol
            
            logger.info(f"🔄 Closing position for {symbol}...")
            
            # Check if we have a position
            positions = await self.exchange.get_positions(symbol)
            if not positions:
                logger.warning(f"⚠️ No position found for {symbol}")
                return
            
            position = positions[0]
            logger.info(f"📊 Found position: {position.size} {symbol} ({position.side.value})")
            
            # Close the position
            close_result = await self.exchange.close_position(symbol)
            
            if close_result:
                logger.info(f"✅ Position closed: {close_result['id']}")
                
                # Cancel any remaining TP/SL orders
                open_orders = await self.exchange.get_open_orders(symbol)
                if open_orders:
                    logger.info(f"❌ Cancelling {len(open_orders)} remaining orders...")
                    for order in open_orders:
                        cancelled = await self.exchange.cancel_order(order['id'], symbol)
                        if cancelled:
                            logger.info(f"   ✅ Cancelled {order['id']}")
            else:
                logger.error("❌ Failed to close position")
                
        except Exception as e:
            logger.error(f"❌ Error executing close signal: {e}")


async def main() -> None:
    """Main entry point."""
    consumer = TradingConsumer()
    
    try:
        await consumer.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


def cli_main() -> None:
    """CLI entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_main() 