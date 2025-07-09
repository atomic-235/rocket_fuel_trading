"""
Telegram client for message consumption.
"""

import asyncio
from typing import Optional, Callable
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models.telegram import TelegramMessage, TelegramUser, TelegramChat
from ..models.config import TelegramConfig


class TelegramClient:
    """Telegram client for consuming messages."""
    
    def __init__(self, config: TelegramConfig):
        """Initialize Telegram client."""
        self.config = config
        self.bot: Optional[Bot] = None
        self.application: Optional[Application] = None
        self.message_callback: Optional[Callable[[TelegramMessage], None]] = None
        self._running = False
        
    async def initialize(self) -> None:
        """Initialize the Telegram client."""
        try:
            # Create bot and application
            self.bot = Bot(token=self.config.bot_token)
            self.application = Application.builder().token(self.config.bot_token).build()
            
            # Test bot connection
            bot_info = await self.bot.get_me()
            logger.info(f"Connected to Telegram bot: @{bot_info.username}")
            
            # Add message handler
            message_handler = MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_message
            )
            self.application.add_handler(message_handler)
            
            logger.info("Telegram client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Telegram client: {e}")
            raise
    
    async def start(self, message_callback: Callable[[TelegramMessage], None]) -> None:
        """Start the Telegram client."""
        if not self.application:
            await self.initialize()
        
        self.message_callback = message_callback
        self._running = True
        
        try:
            logger.info("Starting Telegram client...")
            await self.application.initialize()
            await self.application.start()
            
            # Start polling for updates with debug logging
            logger.info("🔄 Starting Telegram polling...")
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "channel_post"],
                timeout=30,
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30
            )
            
            logger.info(f"📱 Telegram client started")
            logger.info(f"🎯 Monitoring chat IDs: {self.config.chat_ids}")
            if self.config.allowed_user_ids:
                logger.info(f"👥 Allowed user IDs: {self.config.allowed_user_ids}")
            elif self.config.allowed_users:
                logger.info(f"👥 Allowed usernames: {self.config.allowed_users}")
            else:
                logger.info(f"👥 No user filtering configured - accepting all users")
            
            # Keep running until stopped with periodic health checks
            health_check_counter = 0
            while self._running:
                await asyncio.sleep(60)  # Check every minute
                health_check_counter += 1
                if health_check_counter % 5 == 0:  # Log every 5 minutes
                    logger.info(f"🔄 Bot health check - running for {health_check_counter} minutes")
                    if hasattr(self.application.updater, 'running'):
                        logger.info(f"📡 Updater status: {self.application.updater.running}")
                        
        except Exception as e:
            logger.error(f"Error running Telegram client: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the Telegram client."""
        self._running = False
        
        if self.application:
            try:
                logger.info("Stopping Telegram client...")
                
                # Only stop updater if it was started
                if hasattr(self.application, 'updater') and self.application.updater.running:
                    await self.application.updater.stop()
                
                # Only stop application if it was started  
                if hasattr(self.application, '_running') and self.application._running:
                    await self.application.stop()
                
                await self.application.shutdown()
                logger.info("Telegram client stopped")
            except Exception as e:
                logger.error(f"Error stopping Telegram client: {e}")
    
    async def _handle_message(self, update: Update, context) -> None:
        """Handle incoming Telegram message."""
        try:
            if not update.effective_message:
                return
            
            message = update.effective_message
            
            # Log chat and user information for debugging
            chat_id = message.chat_id
            chat_name = message.chat.title or message.chat.first_name or message.chat.username or "Unknown"
            user_id = message.from_user.id if message.from_user else "Unknown"
            username = message.from_user.username if message.from_user else "Unknown"
            
            logger.info(f"📨 Message from User ID: {user_id} (@{username}) in Chat: {chat_id} ({chat_name})")
            
             # Filter by chat IDs if specified
            if self.config.chat_ids and message.chat_id not in self.config.chat_ids:
                logger.info(f"🚫 Ignoring message from chat {message.chat_id} ({chat_name}) - monitoring chats {self.config.chat_ids}")
                return
            
            # Filter by allowed user IDs if specified (priority over usernames)
            if self.config.allowed_user_ids and message.from_user:
                user_id = message.from_user.id
                if user_id not in self.config.allowed_user_ids:
                    logger.info(f"🚫 Ignoring message from user ID {user_id} (not in allowed list: {self.config.allowed_user_ids})")
                    return
                else:
                    logger.info(f"✅ Message from allowed user ID {user_id}")
            
            # Filter by allowed users (usernames) if specified and no user ID filter
            elif self.config.allowed_users and message.from_user:
                username = message.from_user.username
                if username not in self.config.allowed_users:
                    logger.info(f"🚫 Ignoring message from user @{username} (not in allowed list: {self.config.allowed_users})")
                    return
                else:
                    logger.info(f"✅ Message from allowed user @{username}")
            
            # Convert to our message model
            telegram_message = self._convert_message(message)
            
            logger.info(
                f"Received message from {telegram_message.sender_name}: "
                f"{telegram_message.content[:100]}..."
            )
            
            # Call the message callback
            if self.message_callback:
                await self._safe_callback(telegram_message)
            
        except Exception as e:
            logger.error(f"Error handling Telegram message: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _safe_callback(self, message: TelegramMessage) -> None:
        """Safely call the message callback with retry logic."""
        try:
            if asyncio.iscoroutinefunction(self.message_callback):
                await self.message_callback(message)
            else:
                self.message_callback(message)
        except Exception as e:
            logger.error(f"Error in message callback: {e}")
            raise
    
    def _convert_message(self, telegram_message) -> TelegramMessage:
        """Convert python-telegram-bot message to our model."""
        
        # Convert user
        from_user = None
        if telegram_message.from_user:
            from_user = TelegramUser(
                id=telegram_message.from_user.id,
                is_bot=telegram_message.from_user.is_bot,
                first_name=telegram_message.from_user.first_name,
                last_name=telegram_message.from_user.last_name,
                username=telegram_message.from_user.username,
                language_code=telegram_message.from_user.language_code,
            )
        
        # Convert chat
        chat = TelegramChat(
            id=telegram_message.chat.id,
            type=telegram_message.chat.type,
            title=telegram_message.chat.title,
            username=telegram_message.chat.username,
            first_name=telegram_message.chat.first_name,
            last_name=telegram_message.chat.last_name,
        )
        
        # Convert reply message if exists
        reply_to_message = None
        if telegram_message.reply_to_message:
            reply_to_message = self._convert_message(telegram_message.reply_to_message)
        
        # Convert forward from user
        forward_from = None
        if hasattr(telegram_message, 'forward_from') and telegram_message.forward_from:
            forward_from = TelegramUser(
                id=telegram_message.forward_from.id,
                is_bot=telegram_message.forward_from.is_bot,
                first_name=telegram_message.forward_from.first_name,
                last_name=telegram_message.forward_from.last_name,
                username=telegram_message.forward_from.username,
                language_code=telegram_message.forward_from.language_code,
            )
        
        return TelegramMessage(
            message_id=telegram_message.message_id,
            from_user=from_user,
            chat=chat,
            date=telegram_message.date,
            text=telegram_message.text,
            caption=telegram_message.caption,
            reply_to_message=reply_to_message,
            forward_from=forward_from,
            forward_date=getattr(telegram_message, 'forward_date', None),
            edit_date=getattr(telegram_message, 'edit_date', None),
        )
    
    async def send_message(self, text: str, chat_id: Optional[int] = None) -> None:
        """Send a message to Telegram."""
        if not self.bot:
            raise RuntimeError("Telegram client not initialized")
        
        target_chat_id = chat_id or (self.config.chat_ids[0] if self.config.chat_ids else None)
        
        if not target_chat_id:
            raise ValueError("No chat ID specified and no default chat ID configured")
        
        try:
            await self.bot.send_message(
                chat_id=target_chat_id,
                text=text,
                parse_mode="HTML"
            )
            logger.debug(f"Sent message to chat {target_chat_id}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    async def send_owner_notification(self, message: str) -> None:
        """Send notification to the owner."""
        if not self.config.owner_telegram_id:
            logger.debug("No owner Telegram ID configured, skipping notification")
            return
        
        try:
            await self.send_message(
                text=f"🔔 Trading Bot Notification\n\n{message}",
                chat_id=self.config.owner_telegram_id
            )
            logger.debug(f"Sent owner notification to {self.config.owner_telegram_id}")
        except Exception as e:
            logger.error(f"Failed to send owner notification: {e}")
            # Don't raise - notifications are not critical 