"""
Configuration management for trading consumer.
"""

import os
# Removed Decimal import - using float throughout
from typing import Optional
from dotenv import load_dotenv
from loguru import logger

from .models.config import (
    AppConfig,
    TelegramConfig,
    HyperliquidConfig,
    TradingConfig,
    LoggingConfig,
)


def load_config(env_file: Optional[str] = None) -> AppConfig:
    """Load configuration from environment variables."""
    
    # Load environment variables
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()
    
    try:
        # Telegram configuration
        telegram_config = TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            chat_ids=_parse_int_list(os.getenv("TELEGRAM_CHAT_IDS", "")),
            owner_telegram_id=int(os.getenv("OWNER_TELEGRAM_ID")) if os.getenv("OWNER_TELEGRAM_ID") else None,
            allowed_users=_parse_list(os.getenv("TELEGRAM_ALLOWED_USERS")),
            allowed_user_ids=_parse_int_list(os.getenv("TELEGRAM_ALLOWED_USER_IDS")),
            message_processing_delay=float(os.getenv("MESSAGE_PROCESSING_DELAY", "1.0")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("RETRY_DELAY", "5.0")),
        )
        
        # Hyperliquid configuration
        hyperliquid_config = HyperliquidConfig(
            wallet_address=os.getenv("HYPERLIQUID_API_ADDRESS", ""),
            private_key=os.getenv("HYPERLIQUID_API_KEY", ""),
            testnet=_parse_bool(os.getenv("HYPERLIQUID_TESTNET", "true")),
            sandbox=_parse_bool(os.getenv("HYPERLIQUID_SANDBOX", "false")),
            timeout=int(os.getenv("HYPERLIQUID_TIMEOUT", "30")),
            rate_limit=int(os.getenv("HYPERLIQUID_RATE_LIMIT", "10")),
        )
        
        # Trading configuration
        trading_config = TradingConfig(
            default_position_size_usd=float(os.getenv("DEFAULT_POSITION_SIZE_USD", "12")),
            default_leverage=int(os.getenv("DEFAULT_LEVERAGE", "2")),
            default_tp_percent=float(os.getenv("DEFAULT_TP_PERCENT", "0.05")),
            default_sl_percent=float(os.getenv("DEFAULT_SL_PERCENT", "0.02")),
            max_leverage=int(os.getenv("MAX_LEVERAGE", "10")),
            min_confidence=float(os.getenv("MIN_CONFIDENCE", "0.7")),
        )
        
        # Logging configuration
        logging_config = LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            file=os.getenv("LOG_FILE", "trading_consumer.log"),
            max_file_size=os.getenv("LOG_MAX_FILE_SIZE", "10 MB"),
            backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
            format=os.getenv(
                "LOG_FORMAT",
                "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
            ),
        )
        
        # Create main config
        config = AppConfig(
            telegram=telegram_config,
            hyperliquid=hyperliquid_config,
            trading=trading_config,
            logging=logging_config,
        )
        
        logger.info("Configuration loaded successfully")
        return config
        
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise


def _parse_bool(value: Optional[str]) -> bool:
    """Parse boolean value from string."""
    if not value:
        return False
    return value.lower() in ("true", "1", "yes", "on")


def _parse_list(value: Optional[str]) -> Optional[list]:
    """Parse list value from comma-separated string."""
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_int_list(value: Optional[str]) -> list:
    """Parse integer list value from comma-separated string."""
    if not value:
        return []
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def validate_config(config: AppConfig) -> None:
    """Validate configuration and log warnings for potential issues."""
    
    # Validate Telegram config
    if not config.telegram.bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    
    if not config.telegram.chat_ids:
        raise ValueError("TELEGRAM_CHAT_IDS is required")
    
    # Validate Hyperliquid config
    if not config.hyperliquid.wallet_address:
        raise ValueError("HYPERLIQUID_API_ADDRESS is required")
    
    if not config.hyperliquid.private_key:
        raise ValueError("HYPERLIQUID_API_KEY is required")
    
    # Validate trading config
    if config.trading.default_sl_percent >= config.trading.default_tp_percent:
        logger.warning(
            "DEFAULT_SL_PERCENT should be less than DEFAULT_TP_PERCENT"
        )
    
    # Log configuration summary
    logger.info("Configuration validation completed")
    logger.info(f"Telegram Chat IDs: {config.telegram.chat_ids}")
    logger.info(f"Allowed User IDs: {config.telegram.allowed_user_ids}")
    logger.info(f"Hyperliquid Testnet: {config.hyperliquid.testnet}")
    logger.info(f"Default Position Size USD: ${config.trading.default_position_size_usd}")
    logger.info(f"Default Leverage: {config.trading.default_leverage}x")
    logger.info(f"Default TP: {config.trading.default_tp_percent*100}%")
    logger.info(f"Default SL: {config.trading.default_sl_percent*100}%")
    logger.info(f"Max Leverage: {config.trading.max_leverage}") 