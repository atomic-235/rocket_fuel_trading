"""
Message handlers for Telegram integration.
"""

from typing import Callable, Optional
from loguru import logger

from ..models.telegram import TelegramMessage


class MessageHandler:
    """Handler for processing Telegram messages."""
    
    def __init__(self, callback: Optional[Callable[[TelegramMessage], None]] = None):
        """Initialize message handler."""
        self.callback = callback
        
    async def handle_message(self, message: TelegramMessage) -> None:
        """Handle a Telegram message."""
        try:
            logger.debug(f"Handling message: {message.message_id}")
            
            if self.callback:
                if hasattr(self.callback, '__call__'):
                    await self.callback(message)
                else:
                    logger.warning("Invalid callback provided")
            else:
                logger.debug("No callback set for message handler")
                
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
    
    def set_callback(self, callback: Callable[[TelegramMessage], None]) -> None:
        """Set the message callback."""
        self.callback = callback 