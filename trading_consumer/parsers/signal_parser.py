"""
Signal parser for extracting trading signals from Telegram messages.
"""

# Removed regex and Decimal imports - only JSON parsing used
from typing import Optional, List, Dict, Any
from loguru import logger

from ..models.telegram import TelegramMessage
from ..models.trading import TradingSignal, SignalType
from ..utils.symbol_mapper import symbol_mapper
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
            
            logger.debug(f"Parsing JSON message: {content[:100]}...")
            
            # Parse JSON trade data from message analyzer
            return self._parse_from_json(content, message)
            
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None
    
    def _parse_from_json(self, content: str, message: TelegramMessage) -> Optional[TradingSignal]:
        """Parse JSON trade data from message analyzer."""
        try:
            import json
            
            # Try to parse as JSON
            data = json.loads(content)
            
            # Check if it has trade_extractions
            if not isinstance(data, dict) or 'trade_extractions' not in data:
                return None
            
            trade_extractions = data.get('trade_extractions', [])
            if not trade_extractions:
                return None
            
            # Get the first trade extraction
            trade = trade_extractions[0]
            if not trade:
                return None
            
            # Extract signal type from direction
            direction = trade.get('direction', '').lower()
            if direction == 'long':
                signal_type = SignalType.BUY
            elif direction == 'short':
                signal_type = SignalType.SELL
            else:
                # Check trade_type for close signals
                trade_type = trade.get('trade_type', '').lower()
                if trade_type == 'close':
                    signal_type = SignalType.CLOSE
                else:
                    logger.debug(f"Unknown direction/trade_type: {direction}/{trade_type}")
                    return None
            
            # Extract symbol (handle case properly)
            raw_symbol = trade.get('ticker', '').strip().upper()
            if not raw_symbol:
                logger.warning(f"No ticker found in JSON trade data - skipping signal")
                return None
            
            # Map symbol to exchange-specific format (e.g., PEPE -> kPEPE for Hyperliquid)
            symbol = symbol_mapper.map_to_hyperliquid(raw_symbol)
            
            # Extract other fields
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
                    "mapped_symbol": symbol,
                }
            )
            
            logger.info(
                f"🎯 Extracted signal from JSON: {signal.signal_type.value} {signal.symbol} "
                f"(confidence: {signal.confidence:.2f})"
            )
            
            return signal
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.debug(f"Not valid JSON trade data: {e}")
            return None
    
# All text parsing methods removed - only JSON parsing is used 