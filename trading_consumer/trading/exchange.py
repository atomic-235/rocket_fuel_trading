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
            
            # Log vault address if configured
            if self.config.vault_address:
                logger.info(f"🏦 Vault/Subaccount address: {self.config.vault_address}")
                logger.info("📋 All trades will be executed on behalf of the vault/subaccount")
            else:
                logger.info("👤 Trading with main wallet address (no vault configured)")
            
            # Create CCXT exchange instance with Hyperliquid configuration
            self.exchange = ccxt.hyperliquid({
                'walletAddress': self.config.wallet_address,
                'privateKey': self.config.private_key,
                'timeout': self.config.timeout * 1000,  # CCXT uses milliseconds
                'enableRateLimit': True,
                'rateLimit': 1000 // self.config.rate_limit,  # Convert to ms per request
                'options': {
                    'defaultSlippage': 0.05,  # 5% default slippage protection
                    'slippage': 0.05  # Alternative key
                }
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
        """Set leverage for a symbol using correct Hyperliquid API."""
        if not self._connected:
            await self.initialize()
        
        try:
            symbol_formatted = f"{symbol}/USDC:USDC"
            
            logger.info(f"⚡ Setting {leverage}x leverage for {symbol} with {margin_mode} margin...")
            
            # Use correct Hyperliquid API - set_margin_mode with leverage parameter
            self.exchange.set_margin_mode(
                margin_mode, 
                    symbol_formatted, 
                params={"leverage": leverage}
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
            
            # Load markets to get current price (for logging/metadata only)
            markets = self.exchange.load_markets()
            current_price = float(markets[symbol]["info"]["midPx"])
            # Fetch ticker for bid/ask to support fallbacks
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                best_bid = float(ticker.get('bid') or 0) or current_price
                best_ask = float(ticker.get('ask') or 0) or current_price
            except Exception:
                best_bid = current_price
                best_ask = current_price
            
            # Map side
            side_map = {
                SignalType.BUY: 'buy',
                SignalType.LONG: 'buy',
                SignalType.SELL: 'sell',
                SignalType.SHORT: 'sell',
            }
            side = side_map.get(order.side, 'buy')
            
            # Create the order - Hyperliquid requires price for market orders (slippage calc)
            params = {}
            if self.config.vault_address:
                params['vaultAddress'] = self.config.vault_address
                logger.debug(f"🏦 Trading on behalf of vault/subaccount: {self.config.vault_address}")
            
            # Add leverage to params if specified in order
            if order.leverage:
                params['leverage'] = order.leverage
                logger.debug(f"⚡ Using {order.leverage}x leverage for order")
            
            if order.order_type.value == 'market':
                # Market orders need price for slippage calculation on Hyperliquid
                result = self.exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=side,
                    amount=float(order.quantity),
                    price=current_price,  # Required for slippage calculation
                    params=params
                )
                logger.info(f"🚀 Market order created at ~${current_price:.4f}")
            elif order.order_type.value == 'limit':
                limit_price = float(order.price) if order.price else current_price
                result = self.exchange.create_order(
                    symbol=symbol,
                    type='limit',
                    side=side,
                    amount=float(order.quantity),
                    price=limit_price,
                    params=params
                )
                logger.info(f"📌 Limit order created at ${limit_price:.4f}")
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
            # Fallback: if market order couldn't immediately match, try aggressive LIMIT IOC
            error_str = str(e)
            logger.error(f"❌ Failed to create order: {error_str}")
            try:
                if order.order_type.value == 'market' and (
                    'could not immediately match' in error_str.lower() or 'invalidorder' in error_str.lower()
                ):
                    logger.info("🔁 Falling back to aggressive LIMIT IOC order")
                    # Recompute side and params
                    side_map = {
                        SignalType.BUY: 'buy',
                        SignalType.LONG: 'buy',
                        SignalType.SELL: 'sell',
                        SignalType.SHORT: 'sell',
                    }
                    side_fallback = side_map.get(order.side, 'buy')
                    params_fb = {}
                    if self.config.vault_address:
                        params_fb['vaultAddress'] = self.config.vault_address
                    if order.leverage:
                        params_fb['leverage'] = order.leverage
                    # Price slightly beyond best to ensure take
                    slippage_buffer = 0.002  # 0.2%
                    if side_fallback == 'buy':
                        limit_price = best_ask * (1 + slippage_buffer)
                    else:
                        limit_price = best_bid * (1 - slippage_buffer)
                    # IOC to attempt immediate execution
                    params_fb['timeInForce'] = 'IOC'
                    result = self.exchange.create_order(
                        symbol=symbol,
                        type='limit',
                        side=side_fallback,
                        amount=float(order.quantity),
                        price=float(limit_price),
                        params=params_fb
                    )
                    logger.info(f"✅ Fallback LIMIT IOC order created at ${limit_price:.4f}")
                    # Update order from result
                    order.id = result['id']
                    order.status = self._map_order_status(result['status'])
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
                    return order
            except Exception as fb_e:
                logger.error(f"❌ Fallback LIMIT IOC also failed: {fb_e}")
            # If fallback not applicable or failed, mark rejected and re-raise
            order.status = OrderStatus.REJECTED
            order.metadata['error'] = error_str
            raise
    
    async def wait_for_order_fill(self, order_id: str, symbol: str, timeout_seconds: int = 30) -> bool:
        """Wait for an order to be filled with timeout."""
        symbol_formatted = f"{symbol}/USDC:USDC"

        for attempt in range(timeout_seconds):
            try:
                order_status = await self.get_order_status(order_id, symbol)
                logger.debug(f"Order {order_id} status: {order_status.value} (attempt {attempt + 1}/{timeout_seconds})")
                
                if order_status == OrderStatus.FILLED:
                    logger.info(f"✅ Order {order_id} filled successfully")
                    return True
                elif order_status in [OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                    logger.error(f"❌ Order {order_id} failed with status: {order_status.value}")
                    return False

                # Fallback: check positions to detect fill (market orders may not reflect immediately via fetch_order)
                try:
                    position_params = {}
                    if self.config.vault_address:
                        position_params["user"] = self.config.vault_address
                    else:
                        position_params["user"] = self.config.wallet_address

                    positions = self.exchange.fetch_positions([symbol_formatted], params=position_params)
                    if positions and positions[0].get('contracts', 0) != 0:
                        logger.info(f"✅ Position detected while waiting: {abs(positions[0]['contracts'])} {symbol}")
                        return True
                except Exception as e_pos:
                    logger.debug(f"Position check error while waiting for fill: {e_pos}")
                
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Error checking order status (attempt {attempt + 1}): {e}")
                await asyncio.sleep(1)
        
        logger.warning(f"⏰ Order {order_id} fill timeout after {timeout_seconds} seconds")
        return False

    async def create_tp_sl_orders(self, symbol: str, tp_price: Optional[float] = None, sl_price: Optional[float] = None) -> List[Dict[str, Any]]:
        """Create TP/SL orders for existing position (following user's examples)."""
        if not self._connected:
            await self.initialize()
        
        orders = []
        symbol_formatted = f"{symbol}/USDC:USDC"
        
        # Setup params for vault trading
        params = {}
        if self.config.vault_address:
            params['vaultAddress'] = self.config.vault_address
        
        try:
            # Wait for position to be established (retry up to 15 times with better logic)
            position_found = False
            position_size = 0
            position_side: Optional[str] = None  # long or short
            
            for attempt in range(15):
                try:
                    # Use consistent user parameter logic
                    position_params = {}
                    if self.config.vault_address:
                        position_params["user"] = self.config.vault_address  # Check vault positions
                        logger.debug(f"Checking positions for vault: {self.config.vault_address}")
                    else:
                        position_params["user"] = self.config.wallet_address  # Check main wallet positions
                        logger.debug(f"Checking positions for wallet: {self.config.wallet_address}")
                    
                    positions = self.exchange.fetch_positions([symbol_formatted], params=position_params)
                    logger.debug(f"Fetch positions response: {positions}")
                    
                    if positions and len(positions) > 0:
                        position = positions[0]
                        contracts = position.get('contracts', 0)
                        logger.debug(f"Position contracts: {contracts}")
                        
                        if contracts != 0:
                            position_size = abs(contracts)
                            position_side = position.get('side')
                            position_found = True
                            logger.info(f"✅ Position found: {position_size} contracts for {symbol} (side={position_side})")
                            break
                    
                    logger.info(f"⏳ Waiting for position... attempt {attempt + 1}/15")
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"Error checking position (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(1)
            
            if not position_found:
                # Try one more time with all positions to debug
                try:
                    all_positions = await self.get_positions()
                    logger.error(f"All current positions: {[f'{p.symbol}: {p.size}' for p in all_positions]}")
                    
                    # Check if position exists with different symbol format
                    for pos in all_positions:
                        if pos.symbol.upper() == symbol.upper():
                            position_size = float(pos.size)
                            position_found = True
                            logger.info(f"✅ Found position with alternative lookup: {position_size} {pos.symbol}")
                            break
                            
                except Exception as e:
                    logger.error(f"Failed to get all positions for debugging: {e}")
                    
                if not position_found:
                    error_msg = (
                        f"No position found for {symbol} after waiting 15 seconds. "
                        f"This usually means:\n"
                        f"1. Order was not filled due to insufficient liquidity or price movement\n"
                        f"2. There's a configuration issue with vault/wallet addresses\n"
                        f"3. Position was immediately closed by another process\n"
                        f"Check order status and exchange logs for more details."
                    )
                    raise ValueError(error_msg)
        
            # Load markets to get current price
            markets = self.exchange.load_markets()
            current_price = float(markets[symbol_formatted]["info"]["midPx"])

            # Determine the correct close side based on position side
            # long → close with 'sell'; short → close with 'buy'
            close_side = 'sell'
            if position_side == 'short':
                close_side = 'buy'
            
            # Create Take Profit order (following user's example)
            if tp_price:
                try:
                    tp_order = self.exchange.create_order(
                        symbol=symbol_formatted,
                        type='market',
                        side=close_side,
                        amount=position_size,
                        price=current_price,
                        params={**params, 'takeProfitPrice': tp_price, 'reduceOnly': True}
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
                            side=close_side,
                            amount=position_size,
                            price=tp_price,
                            params={**params, 'reduceOnly': True}
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
                        side=close_side,
                        amount=position_size,
                        price=current_price,
                        params={**params, 'stopLossPrice': sl_price, 'reduceOnly': True}
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
                            side=close_side,
                            amount=position_size,
                            price=None,
                            params={**params, 'stopPrice': sl_price, 'reduceOnly': True}
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
            
            # Setup params for vault trading
            params = {}
            if self.config.vault_address:
                params['vaultAddress'] = self.config.vault_address
            
            # Get position size if not provided
            if position_size is None:
                position_params = {"user": self.config.wallet_address}
                if self.config.vault_address:
                    position_params["user"] = self.config.vault_address
                    
                positions = self.exchange.fetch_positions([symbol_formatted], params=position_params)
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
                params={**params, 'reduceOnly': True}
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
            # Include user/vault in params to ensure correct account scope
            params = {"user": self.config.vault_address or self.config.wallet_address}
            result = self.exchange.fetch_order(order_id, f"{symbol}/USDC:USDC", params)
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