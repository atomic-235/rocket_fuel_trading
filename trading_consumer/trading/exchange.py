"""
Hyperliquid exchange integration using CCXT.
"""

import ccxt
import decimal
from decimal import Decimal
from typing import Optional, Dict, Any, List
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio

from ..models.config import HyperliquidConfig
from ..models.trading import TradeOrder, Position, OrderStatus, SignalType


class HyperliquidExchange:
    """Hyperliquid exchange client using CCXT."""
    
    def __init__(self, config: HyperliquidConfig):
        """Initialize Hyperliquid exchange client."""
        self.config = config
        self.exchange: Optional[ccxt.Exchange] = None
        self._connected = False
        
    async def initialize(self) -> None:
        """Initialize the exchange connection."""
        try:
            logger.info("🔗 Initializing Hyperliquid exchange connection...")
            logger.info(f"📍 Using wallet: {self.config.wallet_address}")
            logger.info(f"🧪 Testnet mode: {self.config.testnet}")
            
            # Create CCXT exchange instance with Hyperliquid configuration
            self.exchange = ccxt.hyperliquid({
                'walletAddress': self.config.wallet_address,
                'privateKey': self.config.private_key,
                'timeout': self.config.timeout * 1000,  # CCXT uses milliseconds
                'enableRateLimit': True,
                'rateLimit': 1000 // self.config.rate_limit,  # Convert to ms per request
            })
            
            if self.config.testnet:
                self.exchange.sandbox = True
            
            # Test connection
            logger.info("🔍 Testing Hyperliquid API connection...")
            await self._test_connection()
            self._connected = True
            
            # Initialize symbol resolver
            from ..utils.symbol_resolver import get_symbol_resolver
            resolver = get_symbol_resolver()
            resolver.set_exchange(self.exchange)
            
            logger.info("✅ Hyperliquid exchange initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Hyperliquid exchange: {e}")
            raise
    
    async def _test_connection(self) -> None:
        """Test the exchange connection."""
        try:
            logger.info("🔄 Testing Hyperliquid API connection...")
            self.exchange.fetch_balance()
            logger.info("✅ Hyperliquid API connection test successful")
        except Exception as e:
            logger.error(f"❌ Hyperliquid API connection test failed: {e}")
            raise
    
    async def set_leverage(self, symbol: str, leverage: int, margin_mode: str = "cross") -> bool:
        """Set leverage for a symbol."""
        if not self._connected:
            await self.initialize()
        
        try:
            symbol_formatted = f"{symbol}/USDC:USDC"
            
            logger.info(f"⚡ Setting {leverage}x leverage for {symbol}...")
            
            # Set leverage (following user's example)
            self.exchange.set_leverage(leverage, symbol_formatted)
            
            # Optionally set margin mode
            if margin_mode == "isolated":
                logger.info(f"🔒 Setting isolated margin mode for {symbol}")
                self.exchange.set_leverage(
                    leverage, 
                    symbol_formatted, 
                    params={"marginMode": "isolated"}
                )
            
            logger.info(
                f"✅ Leverage set to {leverage}x for {symbol} with {margin_mode} margin"
            )
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to set leverage for {symbol}: {e}")
            return False
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def create_order(self, order: TradeOrder) -> TradeOrder:
        """Create a new order on the exchange."""
        if not self._connected:
            await self.initialize()
        
        try:
            symbol = f"{order.symbol}/USDC:USDC"
            
            # Load markets to get current price
            markets = self.exchange.load_markets()
            current_price = float(markets[symbol]["info"]["midPx"])
            
            # Map side
            side_map = {
                SignalType.BUY: 'buy',
                SignalType.LONG: 'buy',
                SignalType.SELL: 'sell',
                SignalType.SHORT: 'sell',
            }
            side = side_map.get(order.side, 'buy')
            
            # Create the order (following user's examples)
            if order.order_type.value == 'market':
                result = self.exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=side,
                    amount=float(order.quantity),
                    price=current_price
                )
            elif order.order_type.value == 'limit':
                result = self.exchange.create_order(
                    symbol=symbol,
                    type='limit',
                    side=side,
                    amount=float(order.quantity),
                    price=float(order.price) if order.price else current_price
                )
            else:
                raise ValueError(f"Unsupported order type: {order.order_type}")
            
            # Update order with exchange response
            order.id = result['id']
            order.status = self._map_order_status(result['status'])
            
            # Safe decimal conversions with error handling
            try:
                avg_price = result.get('average', 0)
                order.average_price = (
                    Decimal(str(avg_price)) if avg_price is not None else None
                )
            except (ValueError, TypeError, decimal.InvalidOperation):
                order.average_price = None
                
            try:
                order.filled_quantity = Decimal(str(result.get('filled', 0)))
            except (ValueError, TypeError, decimal.InvalidOperation):
                order.filled_quantity = Decimal('0')
                
            try:
                fee_cost = result.get('fee', {}).get('cost', 0) if result.get('fee') else 0
                order.fees = Decimal(str(fee_cost)) if fee_cost is not None else None
            except (ValueError, TypeError, decimal.InvalidOperation):
                order.fees = None
                
            order.metadata['exchange_response'] = result
            
            logger.info(f"📈 Order created: {order.id} - {order.side.value} {order.quantity} {order.symbol}")
            
            return order
            
        except Exception as e:
            logger.error(f"❌ Failed to create order: {e}")
            order.status = OrderStatus.REJECTED
            order.metadata['error'] = str(e)
            raise
    
    async def create_tp_sl_orders(self, symbol: str, tp_price: Optional[float] = None, sl_price: Optional[float] = None) -> List[Dict[str, Any]]:
        """Create TP/SL orders for existing position (following user's examples)."""
        if not self._connected:
            await self.initialize()
        
        orders = []
        symbol_formatted = f"{symbol}/USDC:USDC"
        
        try:
            # Wait for position to be established (retry up to 10 times)
            position_found = False
            position_size = 0
            
            for attempt in range(10):
                try:
                    positions = self.exchange.fetch_positions([symbol_formatted], params={"user": self.config.wallet_address})
                    if positions and positions[0].get('contracts', 0) != 0:
                        position_size = abs(positions[0]['contracts'])
                        position_found = True
                        logger.info(f"Position found: {position_size} contracts for {symbol}")
                        break
                    else:
                        logger.info(f"Waiting for position... attempt {attempt + 1}/10")
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Error checking position (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(1)
            
            if not position_found:
                raise ValueError(f"No position found for {symbol} after waiting 10 seconds")
        
            # Load markets to get current price
            markets = self.exchange.load_markets()
            current_price = float(markets[symbol_formatted]["info"]["midPx"])
            
            # Create Take Profit order (following user's example)
            if tp_price:
                try:
                    tp_order = self.exchange.create_order(
                        symbol=symbol_formatted,
                        type='market',
                        side='sell',
                        amount=position_size,
                        price=current_price,
                        params={'takeProfitPrice': tp_price, 'reduceOnly': True}
                    )
                    orders.append(tp_order)
                    logger.info(f"TP order created: {tp_order['id']} @ {tp_price}")
                except Exception as e:
                    logger.error(f"Failed to create TP order: {e}")
                    # Try alternative TP format (limit order)
                    try:
                        tp_order_alt = self.exchange.create_order(
                            symbol=symbol_formatted,
                            type='limit',
                            side='sell',
                            amount=position_size,
                            price=tp_price,
                            params={'reduceOnly': True}
                        )
                        orders.append(tp_order_alt)
                        logger.info(f"Alternative TP order created: {tp_order_alt['id']} @ {tp_price}")
                    except Exception as e2:
                        logger.error(f"Both TP order formats failed: {e}, {e2}")
        
            # Create Stop Loss order (following user's example)
            if sl_price:
                try:
                    sl_order = self.exchange.create_order(
                        symbol=symbol_formatted,
                        type='market',
                        side='sell',
                        amount=position_size,
                        price=current_price,
                        params={'stopLossPrice': sl_price, 'reduceOnly': True}
                    )
                    orders.append(sl_order)
                    logger.info(f"SL order created: {sl_order['id']} @ {sl_price}")
                except Exception as e:
                    logger.error(f"Failed to create SL order: {e}")
                    # Try alternative SL format (stop_market)
                    try:
                        sl_order_alt = self.exchange.create_order(
                            symbol=symbol_formatted,
                            type='stop_market',
                            side='sell',
                            amount=position_size,
                            price=None,
                            params={'stopPrice': sl_price, 'reduceOnly': True}
                        )
                        orders.append(sl_order_alt)
                        logger.info(f"Alternative SL order created: {sl_order_alt['id']} @ {sl_price}")
                    except Exception as e2:
                        logger.error(f"Both SL order formats failed: {e}, {e2}")
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to create TP/SL orders: {e}")
            raise
    
    async def close_position(self, symbol: str, position_size: Optional[float] = None) -> Dict[str, Any]:
        """Close a position using reduceOnly."""
        if not self._connected:
            await self.initialize()
        
        try:
            symbol_formatted = f"{symbol}/USDC:USDC"
            
            # Get position size if not provided
            if position_size is None:
                positions = self.exchange.fetch_positions([symbol_formatted], params={"user": self.config.wallet_address})
                if not positions or positions[0].get('contracts', 0) == 0:
                    raise ValueError(f"No position found for {symbol}")
                position_size = abs(positions[0]['contracts'])
            
            # Load markets to get current price
            markets = self.exchange.load_markets()
            current_price = float(markets[symbol_formatted]["info"]["midPx"])
            
            # Create close order (following user's example)
            result = self.exchange.create_order(
                symbol=symbol_formatted,
                type='market',
                side='sell',
                amount=position_size,
                price=current_price,
                params={'reduceOnly': True}
            )
            
            logger.info(f"Position closed: {result['id']} - {position_size} {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            raise
    
    async def get_order_status(self, order_id: str, symbol: str) -> OrderStatus:
        """Get order status from exchange."""
        if not self._connected:
            await self.initialize()
        
        try:
            result = self.exchange.fetch_order(order_id, f"{symbol}/USDC:USDC")
            return self._map_order_status(result['status'])
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return OrderStatus.REJECTED
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        if not self._connected:
            await self.initialize()
        
        try:
            self.exchange.cancel_order(order_id, f"{symbol}/USDC:USDC")
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    async def get_balance(self) -> Dict[str, Decimal]:
        """Get account balance."""
        if not self._connected:
            await self.initialize()
        
        try:
            balance = self.exchange.fetch_balance()
            
            # Convert to our format
            formatted_balance = {}
            for currency, amounts in balance.items():
                if isinstance(amounts, dict) and 'free' in amounts:
                    formatted_balance[currency] = Decimal(str(amounts['free']))
            
            logger.info("💰 Fetched account balance")
            return formatted_balance
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {}
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get open positions."""
        if not self._connected:
            await self.initialize()
        
        try:
            # Add user parameter to params for Hyperliquid
            params = {"user": self.config.wallet_address}
            
            if symbol:
                # Fetch positions for specific symbol (like user's examples)
                symbol_formatted = f"{symbol}/USDC:USDC"
                positions = self.exchange.fetch_positions([symbol_formatted], params=params)
            else:
                # Fetch all positions
                positions = self.exchange.fetch_positions(params=params)
            
            formatted_positions = []
            for pos in positions:
                if pos.get('contracts', 0) != 0:  # Only positions with size
                    # Convert symbol back from "ETH/USDC:USDC" to "ETH"
                    pos_symbol = pos['symbol'].replace('/USDC:USDC', '')
                    
                    position = Position(
                        symbol=pos_symbol,
                        side=SignalType.LONG if pos['side'] == 'long' else SignalType.SHORT,
                        size=Decimal(str(abs(pos['contracts']))),  # Use absolute value
                        entry_price=Decimal(str(pos['entryPrice'])),
                        current_price=Decimal(str(pos['markPrice'])) if pos.get('markPrice') else None,
                        unrealized_pnl=Decimal(str(pos['unrealizedPnl'])) if pos.get('unrealizedPnl') else None,
                        leverage=int(pos.get('leverage', 1)),
                        liquidation_price=Decimal(str(pos['liquidationPrice'])) if pos.get('liquidationPrice') else None,
                        metadata={'exchange_data': pos}
                    )
                    formatted_positions.append(position)
            
            logger.info(f"📊 Fetched {len(formatted_positions)} open positions.")
            return formatted_positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    async def get_open_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Get open orders for a symbol."""
        if not self._connected:
            await self.initialize()
        
        try:
            orders = self.exchange.fetch_open_orders(f"{symbol}/USDC:USDC")
            return orders
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []
    
    async def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get ticker information for a symbol."""
        if not self._connected:
            await self.initialize()
        
        try:
            ticker = self.exchange.fetch_ticker(f"{symbol}/USDC:USDC")
            return {
                'symbol': symbol,
                'price': Decimal(str(ticker['close'])) if ticker.get('close') else None,
                'last': Decimal(str(ticker['last'])) if ticker.get('last') else None,
                'bid': Decimal(str(ticker['bid'])) if ticker.get('bid') else None,
                'ask': Decimal(str(ticker['ask'])) if ticker.get('ask') else None,
                'volume': Decimal(str(ticker['quoteVolume'])) if ticker.get('quoteVolume') else None,
                'change_24h': ticker.get('percentage'),
                'previous_close': Decimal(str(ticker['previousClose'])) if ticker.get('previousClose') else None,
                # Add Hyperliquid-specific fields from the info section
                'mark_price': Decimal(str(ticker['info']['markPx'])) if ticker.get('info', {}).get('markPx') else None,
                'mid_price': Decimal(str(ticker['info']['midPx'])) if ticker.get('info', {}).get('midPx') else None,
                'oracle_price': Decimal(str(ticker['info']['oraclePx'])) if ticker.get('info', {}).get('oraclePx') else None,
                'funding_rate': Decimal(str(ticker['info']['funding'])) if ticker.get('info', {}).get('funding') else None,
                'open_interest': Decimal(str(ticker['info']['openInterest'])) if ticker.get('info', {}).get('openInterest') else None,
                'max_leverage': int(ticker['info']['maxLeverage']) if ticker.get('info', {}).get('maxLeverage') else None,
            }
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol}: {e}")
            return None
    
    def _map_order_status(self, ccxt_status: str) -> OrderStatus:
        """Map CCXT order status to our enum."""
        status_map = {
            'open': OrderStatus.OPEN,
            'closed': OrderStatus.FILLED,
            'canceled': OrderStatus.CANCELLED,
            'cancelled': OrderStatus.CANCELLED,
            'rejected': OrderStatus.REJECTED,
            'expired': OrderStatus.CANCELLED,
        }
        return status_map.get(ccxt_status, OrderStatus.PENDING)
    
    async def close(self) -> None:
        """Close exchange connection."""
        if self.exchange:
            try:
                # CCXT Hyperliquid doesn't have a close() method
                # Just mark as disconnected
                self._connected = False
                logger.info("Exchange connection closed")
            except Exception as e:
                logger.error(f"Error closing exchange connection: {e}") 