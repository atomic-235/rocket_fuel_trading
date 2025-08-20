"""
Main entry point for the trading consumer - Production Pipeline.
"""

import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional, List
# Removed Decimal import - using float throughout
from loguru import logger

from .config import load_config, validate_config
from .telegram import TelegramClient
from .parsers import SignalParser
from .trading import HyperliquidExchange
from .models.telegram import TelegramMessage
from .models.trading import TradingSignal, TradeOrder, OrderType, SignalType, OrderStatus
from .utils.symbol_resolver import resolve_symbol_for_trading
from decimal import Decimal


class RecentTrade:
    """Recent trade data for deduplication."""
    
    def __init__(self, symbol: str, signal_type: SignalType, entry_price: Optional[float], 
                 leverage: Optional[int], timestamp: datetime):
        self.symbol = symbol
        self.signal_type = signal_type
        self.entry_price = entry_price  # Entry price from the signal
        self.leverage = leverage
        self.timestamp = timestamp


class TradingConsumer:
    """Main trading consumer application - Production Pipeline."""
    
    def __init__(self):
        """Initialize trading consumer."""
        self.config = None
        self.telegram_client: Optional[TelegramClient] = None
        self.signal_parser: Optional[SignalParser] = None
        self.exchange: Optional[HyperliquidExchange] = None
        self._running = False
        self._recent_trades: List[RecentTrade] = []  # Track recent trades for deduplication
        self._trade_dedupe_window = timedelta(minutes=10)  # 10 minute window
    
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
            logger.info(
                f"📊 Default Settings: {self.config.trading.default_leverage}x leverage, "
                f"{self.config.trading.default_tp_percent*100}% TP, "
                f"{self.config.trading.default_sl_percent*100}% SL"
            )
            
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
                logger.debug("📄 No trading signal found in message")
                return
            
            logger.info("🎯 Valid trading signal found!")
            
            # Check confidence threshold (skip for specific chat)
            bypass_chat_id = -4928770997
            current_chat_id = message.chat.id
            
            if current_chat_id == bypass_chat_id:
                logger.info(f"🚀 Bypassing confidence filter for chat {bypass_chat_id}")
            elif signal.confidence < self.config.trading.min_confidence:
                logger.info(
                    f"⚠️ Signal confidence {signal.confidence:.2f} below threshold "
                    f"{self.config.trading.min_confidence:.2f}, skipping"
                )
                return
            
            # Execute trade
            await self._execute_signal(signal)
            
        except Exception as e:
            logger.error(f"❌ Error handling message: {e}")
            
    def _cleanup_old_trades(self) -> None:
        """Remove trades older than the deduplication window."""
        cutoff_time = datetime.now() - self._trade_dedupe_window
        self._recent_trades = [
            trade for trade in self._recent_trades 
            if trade.timestamp > cutoff_time
        ]
    
    def _is_duplicate_trade(self, signal: TradingSignal) -> bool:
        """Check if this trade is a duplicate of a recent trade."""
        self._cleanup_old_trades()
        
        # Check against recent trades
        for recent_trade in self._recent_trades:
            if (recent_trade.symbol == signal.symbol and 
                    recent_trade.signal_type == signal.signal_type):
                
                # Check if key parameters match
                price_match = (
                    (recent_trade.entry_price is None and signal.price is None) or
                    (recent_trade.entry_price is not None and signal.price is not None and
                     abs(recent_trade.entry_price - signal.price) < 0.01)  # Small tolerance
                )
                
                leverage_match = recent_trade.leverage == signal.leverage
                
                if price_match and leverage_match:
                    time_diff = datetime.now() - recent_trade.timestamp
                    logger.info(
                        f"⚠️ Duplicate trade detected: {signal.symbol} {signal.signal_type.value} "
                        f"(last trade {time_diff.total_seconds():.0f}s ago)"
                    )
                    return True
        
        return False
    
    def _record_trade(self, signal: TradingSignal) -> None:
        """Record a trade for deduplication tracking."""
        trade = RecentTrade(
            symbol=signal.symbol,
            signal_type=signal.signal_type,
            entry_price=signal.price,
            leverage=signal.leverage,
            timestamp=datetime.now()
        )
        self._recent_trades.append(trade)
        logger.debug(f"📝 Recorded trade: {signal.symbol} {signal.signal_type.value}")

    async def _execute_signal(self, signal: TradingSignal) -> None:
        """Execute trading signal - Full Production Implementation."""
        try:
            conviction_info = f", conviction: {signal.trader_conviction}" if signal.trader_conviction else ""
            logger.info(
                f"🎯 Executing Signal: {signal.signal_type.value} {signal.symbol} "
                f"(confidence: {signal.confidence:.2f}{conviction_info})"
            )
            
            # Send notification to owner about valid signal
            await self._notify_owner_signal_received(signal)
            
            # Check for duplicate trades
            if self._is_duplicate_trade(signal):
                logger.info("🚫 Skipping duplicate trade")
                return
            
            # Resolve symbol if needed
            resolved_symbol = signal.symbol
            if signal.metadata.get("symbol_needs_resolution", False):
                logger.info(f"🔍 Resolving symbol: {signal.symbol}")
                resolved_symbol = await resolve_symbol_for_trading(
                    signal.symbol, self.exchange.exchange
                )
                
                if not resolved_symbol:
                    logger.error(f"❌ Cannot trade {signal.symbol} - symbol not available on exchange")
                    logger.info("🚫 Skipping trade due to invalid symbol")
                    # Notify owner about failed symbol resolution
                    await self._notify_owner_trade_failed(signal, "Symbol not available on exchange")
                    return
                
                if resolved_symbol != signal.symbol:
                    logger.info(f"🔄 Symbol resolved: {signal.symbol} → {resolved_symbol}")
                    
                    # Check if we mapped from non-k token to k-token (price scaling needed)
                    original_symbol = signal.symbol
                    if (not original_symbol.upper().startswith('K') and 
                            resolved_symbol.upper().startswith('K') and 
                            resolved_symbol[1:].upper() == original_symbol.upper()):
                        
                        logger.info(f"💰 Scaling prices for k-token: {original_symbol} → {resolved_symbol}")
                        
                        # Multiply prices by 1000 for k-tokens
                        if signal.price is not None:
                            old_price = signal.price
                            signal.price = signal.price * 1000
                            logger.info(f"📈 Entry price: ${old_price} → ${signal.price}")
                        
                        if signal.stop_loss is not None:
                            old_sl = signal.stop_loss
                            signal.stop_loss = signal.stop_loss * 1000
                            logger.info(f"🛡️ Stop loss: ${old_sl} → ${signal.stop_loss}")
                        
                        if signal.take_profit is not None:
                            old_tp = signal.take_profit
                            signal.take_profit = signal.take_profit * 1000
                            logger.info(f"🎯 Take profit: ${old_tp} → ${signal.take_profit}")
                
                # Update signal with resolved symbol
                signal.symbol = resolved_symbol
            
            # Record the trade before execution
            self._record_trade(signal)
            
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
            # Notify owner about execution error
            await self._notify_owner_trade_failed(signal, str(e))
    
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
            
            # Calculate position size based on trader conviction
            if signal.quantity:
                quantity = float(signal.quantity)
                usd_amount = quantity * current_price
            else:
                # Use conviction-based position sizing
                usd_amount = self.config.trading.get_position_size_for_conviction(signal.trader_conviction)
                quantity = round(usd_amount / current_price, 6)
            
            # Log position sizing with conviction info
            conviction_info = f" (conviction: {signal.trader_conviction})" if signal.trader_conviction else ""
            logger.info(f"💰 Position size: {quantity} {symbol} (~${usd_amount:.2f} USD{conviction_info})")
            
            # Set leverage (use signal leverage or default)
            leverage = signal.leverage if signal.leverage else self.config.trading.default_leverage
            logger.info(f"⚡ Setting {leverage}x leverage...")
            
            leverage_set = await self.exchange.set_leverage(symbol, leverage, "cross")
            if not leverage_set:
                logger.error(f"❌ Failed to set leverage for {symbol}")
                return
            
            # Calculate TP/SL prices using signal values if provided, otherwise defaults
            entry_price = float(signal.price) if signal.price else current_price
            
            # Use signal TP/SL if provided
            if signal.take_profit and signal.stop_loss:
                # Both TP and SL provided in signal
                tp_price = float(signal.take_profit)
                sl_price = float(signal.stop_loss)
                logger.info("🎯 Using TP/SL from signal")
            elif signal.stop_loss and not signal.take_profit:
                # Only SL provided - calculate TP as 2x SL percent based on CURRENT market price
                sl_price = float(signal.stop_loss)
                sl_percent = abs(sl_price - current_price) / current_price
                tp_percent = sl_percent * 2
                tp_price = current_price * (1 + tp_percent)  # TP above market for LONG
                logger.info(f"🎯 Using SL from signal, calculated TP as 2x SL percentage from market ({tp_percent*100:.1f}%)")
            elif signal.take_profit and not signal.stop_loss:
                # Only TP provided - use default SL
                tp_price = float(signal.take_profit)
                sl_price = entry_price * (1 - self.config.trading.default_sl_percent)
                logger.info("🎯 Using TP from signal, default SL")
            else:
                # Use default TP/SL percentages
                tp_price = entry_price * (1 + self.config.trading.default_tp_percent)  # 5% profit
                sl_price = entry_price * (1 - self.config.trading.default_sl_percent)  # 2% loss
                logger.info("🎯 Using default TP/SL percentages")
            
            logger.info("🎯 TP/SL Prices:")
            percent_base = entry_price
            if signal.stop_loss and not signal.take_profit:
                percent_base = current_price  # ensure 2:1 asymmetry based on market as requested
            logger.info(
                f"   📈 Take Profit: ${tp_price:,.2f} (+{((tp_price/percent_base)-1)*100:.1f}%)"
            )
            logger.info(
                f"   📉 Stop Loss: ${sl_price:,.2f} ({((sl_price/percent_base)-1)*100:.1f}%)"
            )
            
            # Determine order type based on price difference
            use_limit_order = False
            order_price = None
            
            if signal.price:
                signal_price = float(signal.price)
                price_diff_pct = abs(current_price - signal_price) / signal_price
                
                if price_diff_pct <= 0.05:  # Within 5%
                    logger.info(
                        f"📊 Signal price ${signal_price:.3f} within 5% of market ${current_price:.3f} "
                        f"({price_diff_pct*100:.1f}% diff) - using MARKET order"
                    )
                    use_limit_order = False
                else:
                    logger.info(
                        f"📊 Signal price ${signal_price:.3f} differs {price_diff_pct*100:.1f}% from market "
                        f"${current_price:.3f} - using LIMIT order at signal price"
                    )
                    use_limit_order = True
                    order_price = signal_price
            else:
                logger.info("📊 No signal price provided - using MARKET order")
                use_limit_order = False
            
            # Create order based on price difference
            if use_limit_order:
                logger.info(f"🎯 Creating LIMIT BUY order @ ${order_price:.3f}...")
                
                order = TradeOrder(
                    symbol=symbol,
                    side=SignalType.BUY,
                    order_type=OrderType.LIMIT,
                    quantity=quantity,
                    price=Decimal(str(order_price)),
                    leverage=leverage
                )
                
                result = await self.exchange.create_order(order)
                logger.info(f"✅ Limit order created: {result.id} @ ${order_price:.3f}")
                
            else:
                logger.info("🚀 Creating MARKET BUY order...")
                
                order = TradeOrder(
                    symbol=symbol,
                    side=SignalType.BUY,
                    order_type=OrderType.MARKET,
                    quantity=quantity,
                    leverage=leverage
                )
                
                result = await self.exchange.create_order(order)
                logger.info(f"✅ Market order created: {result.id}")
            
            # Order execution successful - wait for fill and continue with TP/SL and notifications
            if result and result.id:
                logger.info(f"📋 Order Status: {result.status.value}")
                logger.info(f"📊 Filled: {result.filled_quantity}")
                
                # Wait for order to be filled before creating TP/SL orders
                if result.status != OrderStatus.FILLED:
                    logger.info("⏳ Waiting for order to be filled...")
                    order_filled = await self.exchange.wait_for_order_fill(result.id, symbol, timeout_seconds=30)
                    
                    if not order_filled:
                        logger.error(f"❌ Order {result.id} was not filled within timeout")
                        await self._notify_owner_trade_failed(signal, "Order was not filled within timeout")
                        return
                    else:
                        logger.info(f"✅ Order {result.id} filled successfully")
                else:
                    logger.info("✅ Order already filled")
                
                # Create TP/SL orders after confirming order is filled
                logger.info("🎯 Creating TP/SL orders...")
                
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
                logger.info("📋 Trade Summary:")
                logger.info(f"   Symbol: {symbol}")
                logger.info("   Side: BUY/LONG")
                logger.info(f"   Size: {quantity} {symbol}")
                logger.info(f"   Entry: ${entry_price:,.2f}")
                logger.info(f"   Leverage: {leverage}x")
                logger.info(f"   TP: ${tp_price:,.2f}")
                logger.info(f"   SL: ${sl_price:,.2f}")
                
                # Notify owner about successful trade
                await self._notify_owner_trade_success(signal, result, tp_price, sl_price)
                
            else:
                logger.error("❌ Failed to create market order")
                await self._notify_owner_trade_failed(signal, "Failed to create market order")
                
        except Exception as e:
            logger.error(f"❌ Error executing buy signal: {e}")
            await self._notify_owner_trade_failed(signal, str(e))
    
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
            
            # Calculate position size based on trader conviction
            if signal.quantity:
                quantity = float(signal.quantity)
                usd_amount = quantity * current_price
            else:
                # Use conviction-based position sizing
                usd_amount = self.config.trading.get_position_size_for_conviction(signal.trader_conviction)
                quantity = round(usd_amount / current_price, 6)
            
            # Log position sizing with conviction info
            conviction_info = f" (conviction: {signal.trader_conviction})" if signal.trader_conviction else ""
            logger.info(f"💰 Position size: {quantity} {symbol} (~${usd_amount:.2f} USD{conviction_info})")
            
            # Set leverage (use signal leverage or default)
            leverage = signal.leverage if signal.leverage else self.config.trading.default_leverage
            logger.info(f"⚡ Setting {leverage}x leverage...")
            
            leverage_set = await self.exchange.set_leverage(symbol, leverage, "cross")
            if not leverage_set:
                logger.error(f"❌ Failed to set leverage for {symbol}")
                return
            
            # Calculate TP/SL prices for SHORT using signal values if provided, otherwise defaults
            entry_price = float(signal.price) if signal.price else current_price
            
            # Use signal TP/SL if provided (for SHORT positions)
            if signal.take_profit and signal.stop_loss:
                # Both TP and SL provided in signal
                tp_price = float(signal.take_profit)
                sl_price = float(signal.stop_loss)
                logger.info("🎯 Using TP/SL from signal (SHORT)")
            elif signal.stop_loss and not signal.take_profit:
                # Only SL provided - calculate TP as 2x SL percent based on CURRENT market price (SHORT)
                sl_price = float(signal.stop_loss)
                sl_percent = abs(sl_price - current_price) / current_price
                tp_percent = sl_percent * 2
                tp_price = current_price * (1 - tp_percent)  # TP below market for SHORT
                logger.info(f"🎯 Using SL from signal, calculated TP as 2x SL percentage from market ({tp_percent*100:.1f}%) (SHORT)")
            elif signal.take_profit and not signal.stop_loss:
                # Only TP provided - use default SL
                tp_price = float(signal.take_profit)
                sl_price = entry_price * (1 + self.config.trading.default_sl_percent)
                logger.info("🎯 Using TP from signal, default SL (SHORT)")
            else:
                # Use default TP/SL percentages for SHORT positions
                tp_price = entry_price * (1 - self.config.trading.default_tp_percent)  # 5% profit (price goes down)
                sl_price = entry_price * (1 + self.config.trading.default_sl_percent)  # 2% loss (price goes up)
                logger.info("🎯 Using default TP/SL percentages (SHORT)")
            
            logger.info("🎯 TP/SL Prices (SHORT):")
            percent_base_short = entry_price
            if signal.stop_loss and not signal.take_profit:
                percent_base_short = current_price  # ensure 2:1 asymmetry based on market
            logger.info(
                f"   📈 Take Profit: ${tp_price:,.2f} ({((tp_price/percent_base_short)-1)*100:.1f}%)"
            )
            logger.info(
                f"   📉 Stop Loss: ${sl_price:,.2f} (+{((sl_price/percent_base_short)-1)*100:.1f}%)"
            )
            
            # Determine order type based on price difference
            use_limit_order = False
            order_price = None
            
            if signal.price:
                signal_price = float(signal.price)
                price_diff_pct = abs(current_price - signal_price) / signal_price
                
                if price_diff_pct <= 0.05:  # Within 5%
                    logger.info(
                        f"📊 Signal price ${signal_price:.3f} within 5% of market ${current_price:.3f} "
                        f"({price_diff_pct*100:.1f}% diff) - using MARKET order"
                    )
                    use_limit_order = False
                else:
                    logger.info(
                        f"📊 Signal price ${signal_price:.3f} differs {price_diff_pct*100:.1f}% from market "
                        f"${current_price:.3f} - using LIMIT order at signal price"
                    )
                    use_limit_order = True
                    order_price = signal_price
            else:
                logger.info("📊 No signal price provided - using MARKET order")
                use_limit_order = False
            
            # Create order based on price difference
            if use_limit_order:
                logger.info(f"🎯 Creating LIMIT SELL order (SHORT) @ ${order_price:.3f}...")
                
                order = TradeOrder(
                    symbol=symbol,
                    side=SignalType.SELL,
                    order_type=OrderType.LIMIT,
                    quantity=quantity,
                    price=Decimal(str(order_price)),
                    leverage=leverage
                )
                
                result = await self.exchange.create_order(order)
                logger.info(f"✅ Limit order created: {result.id} @ ${order_price:.3f}")
                
            else:
                logger.info("🚀 Creating MARKET SELL order (SHORT)...")
                
                order = TradeOrder(
                    symbol=symbol,
                    side=SignalType.SELL,
                    order_type=OrderType.MARKET,
                    quantity=quantity,
                    leverage=leverage
                )
                
                result = await self.exchange.create_order(order)
                logger.info(f"✅ Market order created: {result.id}")
            
            if result and result.id:
                logger.info(f"✅ Market order created: {result.id}")
                logger.info(f"   Status: {result.status.value}")
                logger.info(f"   Filled: {result.filled_quantity}")
                
                # Wait for order to be filled before creating TP/SL orders
                if result.status != OrderStatus.FILLED:
                    logger.info("⏳ Waiting for order to be filled...")
                    order_filled = await self.exchange.wait_for_order_fill(result.id, symbol, timeout_seconds=30)
                    
                    if not order_filled:
                        logger.error(f"❌ Order {result.id} was not filled within timeout")
                        await self._notify_owner_trade_failed(signal, "Order was not filled within timeout")
                        return
                    else:
                        logger.info(f"✅ Order {result.id} filled successfully")
                else:
                    logger.info("✅ Order already filled")
                
                # Create TP/SL orders for SHORT position after confirming order is filled
                logger.info("🎯 Creating TP/SL orders for SHORT...")
                
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
                logger.info("📋 Trade Summary:")
                logger.info(f"   Symbol: {symbol}")
                logger.info("   Side: SELL/SHORT")
                logger.info(f"   Size: {quantity} {symbol}")
                logger.info(f"   Entry: ${entry_price:,.2f}")
                logger.info(f"   Leverage: {leverage}x")
                logger.info(f"   TP: ${tp_price:,.2f}")
                logger.info(f"   SL: ${sl_price:,.2f}")
                
                # Notify owner about successful trade
                await self._notify_owner_trade_success(signal, result, tp_price, sl_price)
                
            else:
                logger.error("❌ Failed to create market order")
                await self._notify_owner_trade_failed(signal, "Failed to create market order")
                
        except Exception as e:
            logger.error(f"❌ Error executing sell signal: {e}")
            await self._notify_owner_trade_failed(signal, str(e))
    
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
    
    async def _notify_owner_signal_received(self, signal: TradingSignal) -> None:
        """Notify owner about valid signal received."""
        try:
            if not self.telegram_client:
                return
            
            # Format signal details
            signal_details = [
                "📊 <b>Signal Received</b>",
                f"🎯 <b>Type:</b> {signal.signal_type.value}",
                f"💰 <b>Symbol:</b> {signal.symbol}",
                f"📈 <b>Confidence:</b> {signal.confidence:.2f}",
            ]
            
            # Add trader conviction if available
            if signal.trader_conviction:
                signal_details.append(f"🎲 <b>Conviction:</b> {signal.trader_conviction}")
            
            # Add price details if available
            if signal.price:
                signal_details.append(f"💵 <b>Price:</b> ${signal.price:.4f}")
            
            if signal.leverage:
                signal_details.append(f"⚡ <b>Leverage:</b> {signal.leverage}x")
            
            if signal.take_profit:
                signal_details.append(f"🎯 <b>Take Profit:</b> ${signal.take_profit:.4f}")
            
            if signal.stop_loss:
                signal_details.append(f"🛑 <b>Stop Loss:</b> ${signal.stop_loss:.4f}")
            
            # Add metadata
            sender = signal.metadata.get("sender", "Unknown")
            signal_details.append(f"👤 <b>From:</b> {sender}")
            
            message = "\n".join(signal_details)
            
            await self.telegram_client.send_owner_notification(message)
            
        except Exception as e:
            logger.error(f"Failed to send owner notification: {e}")
    
    async def _notify_owner_trade_failed(self, signal: TradingSignal, error_message: str) -> None:
        """Notify owner about failed trade."""
        try:
            if not self.telegram_client:
                return
            
            # Sanitize error message for HTML parsing
            # Remove any HTML-like tags that might cause parsing issues
            import re
            sanitized_error = re.sub(r'<[^>]+>', '', str(error_message))
            # Also escape any remaining HTML characters
            sanitized_error = (sanitized_error
                                  .replace('&', '&amp;')
                                  .replace('<', '&lt;')
                                  .replace('>', '&gt;')
                                  .replace('"', '&quot;')
                                  .replace("'", '&#x27;'))
            
            message = (
                f"❌ <b>Trade Failed</b>\n\n"
                f"🎯 <b>Signal:</b> {signal.signal_type.value} {signal.symbol}\n"
                f"📈 <b>Confidence:</b> {signal.confidence:.2f}\n"
                f"💥 <b>Error:</b> {sanitized_error[:200]}..."
            )
            
            await self.telegram_client.send_owner_notification(message)
            
        except Exception as e:
            logger.error(f"Failed to send failure notification: {e}")
            # Try sending a simple notification without the problematic error details
            try:
                simple_message = (
                    f"❌ <b>Trade Failed</b>\n\n"
                    f"🎯 <b>Signal:</b> {signal.signal_type.value} {signal.symbol}\n"
                    f"📈 <b>Confidence:</b> {signal.confidence:.2f}\n"
                    f"💥 <b>Error:</b> Order execution failed (see logs for details)"
                )
                await self.telegram_client.send_owner_notification(simple_message)
            except Exception as e2:
                logger.error(f"Failed to send simple failure notification: {e2}")
    
    async def _notify_owner_trade_success(self, signal: TradingSignal, result, tp_price: float, sl_price: float) -> None:
        """Notify owner about successful trade."""
        try:
            if not self.telegram_client:
                return
            
            # Calculate entry price
            entry_price = float(signal.price) if signal.price else 0.0
            
            message = (
                f"✅ <b>Trade Executed</b>\n\n"
                f"🎯 <b>Signal:</b> {signal.signal_type.value} {signal.symbol}\n"
                f"📈 <b>Confidence:</b> {signal.confidence:.2f}\n"
                f"💰 <b>Order ID:</b> {result.id}\n"
                f"📊 <b>Status:</b> {result.status.value}\n"
                f"💵 <b>Entry Price:</b> ${entry_price:.4f}\n"
                f"🎯 <b>Take Profit:</b> ${tp_price:.4f}\n"
                f"🛑 <b>Stop Loss:</b> ${sl_price:.4f}\n"
                f"⚡ <b>Leverage:</b> {signal.leverage or 'Default'}x"
            )
            
            await self.telegram_client.send_owner_notification(message)
            
        except Exception as e:
            logger.error(f"Failed to send success notification: {e}")


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