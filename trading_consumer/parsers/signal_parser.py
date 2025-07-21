"""
Signal parser for extracting trading signals from Telegram messages.
"""

# Removed regex and Decimal imports - only JSON parsing used
from typing import Optional
from loguru import logger

from ..models.telegram import TelegramMessage
from ..models.trading import TradingSignal, SignalType
from .pattern_matcher import PatternMatcher


class SignalParser:
    """Parser for extracting trading signals from messages."""
    
    def __init__(self):
        """Initialize signal parser."""
        self.pattern_matcher = PatternMatcher()
        
    def parse_message(self, message: TelegramMessage) -> Optional[TradingSignal]:
        """Parse a Telegram message and extract trading signal from JSON."""
        try:
            content = message.content.strip()
            if not content:
                return None
            
            logger.info(f"📥 Processing message: {content[:200]}...")
            
            # Check if this looks like an error message (for informational logging only)
            if "Pipeline Error" in content or "TLObject" in content:
                logger.warning("🚨 Upstream service error detected in message")
                return None
            elif content.startswith("❌") and ("Error:" in content or "Exception:" in content):
                logger.warning("🚨 Error message format detected")
                return None
            
            # Always try to parse - don't filter anything out
            logger.debug("📥 Attempting to parse as JSON...")
            
            # Parse JSON trade data from message analyzer
            return self._parse_from_json(content, message)
            
        except Exception as e:
            logger.error(f"❌ Error parsing message: {e}")
            return None
    
    def _parse_from_json(self, content: str, message: TelegramMessage) -> Optional[TradingSignal]:
        """Parse JSON trade data from message analyzer."""
        try:
            import json
            
            # Try to parse as JSON
            data = json.loads(content)
            
            # Check if it has trade_extractions
            if not isinstance(data, dict) or 'trade_extractions' not in data:
                logger.debug("📄 Valid JSON but no trade_extractions field found")
                return None
            
            trade_extractions = data.get('trade_extractions', [])
            if not trade_extractions:
                logger.debug("📄 JSON has trade_extractions but it's empty")
                return None
            
            # Get the first trade extraction
            trade = trade_extractions[0]
            if not trade:
                logger.debug("📄 Empty trade extraction found")
                return None
            
            logger.info(f"🎯 Processing trade extraction: {trade.get('ticker', 'UNKNOWN')}")
            
            # Extract signal type from direction and trade_type
            trade_type = trade.get('trade_type', '').lower()
            direction = trade.get('direction', '').lower()
            
            if trade_type == 'close':
                signal_type = SignalType.CLOSE
                logger.info(f"🔄 Close signal detected for {trade.get('ticker', 'UNKNOWN')}")
            elif direction == 'long':
                signal_type = SignalType.BUY
            elif direction == 'short':
                signal_type = SignalType.SELL
            else:
                logger.debug(f"❓ Unknown direction/trade_type: {direction}/{trade_type}")
                return None
            
            # Extract symbol (handle case properly)
            raw_symbol = trade.get('ticker', '').strip().upper()
            if not raw_symbol:
                logger.warning("⚠️ No ticker found in JSON trade data - skipping signal")
                return None
            
            # Store original symbol - resolution will happen at trade execution time
            symbol = raw_symbol
            
            # Extract price based on trade type
            price = None
            if trade_type == 'close':
                # For close trades, look for exit_price
                price = trade.get('exit_price')
                if price is not None:
                    price = float(price)
                else:
                    # If no exit_price, log close percentage for info
                    close_pct = trade.get('close_percentage')
                    if close_pct:
                        logger.info(f"📊 Closing {close_pct}% of {symbol} position")
            else:
                # For open trades, look for entry_price
                price = trade.get('entry_price')
                if price is not None:
                    price = float(price)
            
            stop_loss = trade.get('stop_loss')
            if stop_loss is not None:
                stop_loss = float(stop_loss)
            
            take_profit = trade.get('take_profit')
            if take_profit is not None:
                # Handle both single value and list
                if isinstance(take_profit, list) and take_profit:
                    take_profit = float(take_profit[0])  # Use first TP level
                else:
                    take_profit = float(take_profit)
            
            leverage = trade.get('leverage')
            if leverage is not None:
                leverage = int(float(leverage))
            
            # Use confidence from JSON (much higher than text parsing)
            confidence = trade.get('confidence', 0.9)
            
            # Extract trader conviction level (low, medium, high, etc.)
            trader_conviction = trade.get('trader_conviction')
            
            # Create trading signal
            signal = TradingSignal(
                signal_type=signal_type,
                symbol=symbol,
                price=price,
                quantity=None,  # Not typically provided in JSON
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=leverage,
                confidence=confidence,
                trader_conviction=trader_conviction,
                source_message=content,
                metadata={
                    "sender": message.sender_name,
                    "chat_id": message.chat.id,
                    "message_id": message.message_id,
                    "timestamp": message.date.isoformat(),
                    "source": "json",
                    "trade_type": trade.get('trade_type'),
                    "asset_name": trade.get('asset_name'),
                    "original_symbol": raw_symbol,
                    "symbol_needs_resolution": True,  # Flag for later resolution
                    "close_percentage": trade.get('close_percentage'),  # Store for close trades
                }
            )
            
            # Enhanced logging based on signal type
            if signal_type == SignalType.CLOSE:
                price_info = f"@ ${price}" if price else "market price"
                conviction_info = f", conviction: {trader_conviction}" if trader_conviction else ""
                logger.info(
                    f"✅ Extracted CLOSE signal: {signal.symbol} {price_info} "
                    f"(confidence: {signal.confidence:.2f}{conviction_info})"
                )
            else:
                price_info = f"@ ${price}" if price else "market price"
                conviction_info = f", conviction: {trader_conviction}" if trader_conviction else ""
                logger.info(
                    f"✅ Extracted {signal.signal_type.value.upper()} signal: {signal.symbol} "
                    f"{price_info} (confidence: {signal.confidence:.2f}{conviction_info})"
                )
            
            return signal
            
        except json.JSONDecodeError as e:
            logger.debug(f"📄 Not valid JSON (normal for text messages): {str(e)[:100]}")
            return None
        except Exception as e:
            logger.error(f"❌ Error parsing signal: {e}")
            logger.error(f"🔍 Content: {content[:200]}...")
            return None

# All text parsing methods removed - only JSON parsing is used 