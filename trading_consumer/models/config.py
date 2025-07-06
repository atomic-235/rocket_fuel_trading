"""
Configuration Pydantic models.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class TelegramConfig(BaseModel):
    """Telegram bot configuration."""
    
    bot_token: str = Field(..., min_length=1)
    chat_ids: List[int] = Field(..., min_length=1)  # Support multiple chat IDs
    owner_telegram_id: Optional[int] = None  # Owner's Telegram ID for notifications
    allowed_users: Optional[List[str]] = None
    allowed_user_ids: Optional[List[int]] = None  # Filter by user IDs
    message_processing_delay: float = Field(default=1.0, ge=0.1)
    max_retries: int = Field(default=3, ge=1)
    retry_delay: float = Field(default=5.0, ge=1.0)
    
    @field_validator('bot_token')
    @classmethod
    def validate_bot_token(cls, v):
        """Validate bot token format."""
        if not v or ':' not in v:
            raise ValueError("Invalid bot token format")
        return v
    
    @field_validator('chat_ids')
    @classmethod
    def validate_chat_ids(cls, v):
        """Validate chat IDs list."""
        if not v or len(v) == 0:
            raise ValueError("At least one chat ID is required")
        return v


class HyperliquidConfig(BaseModel):
    """Hyperliquid exchange configuration."""
    
    wallet_address: str = Field(..., min_length=1)
    private_key: str = Field(..., min_length=1)
    testnet: bool = Field(default=True)
    sandbox: bool = Field(default=False)
    timeout: int = Field(default=30, ge=5)
    rate_limit: int = Field(default=10, ge=1)  # requests per second
    
    @field_validator('wallet_address', 'private_key')
    @classmethod
    def validate_credentials(cls, v):
        """Validate API credentials."""
        if not v or len(v) < 10:
            raise ValueError("Invalid API credentials")
        return v


class TradingConfig(BaseModel):
    """Trading configuration."""
    
    default_position_size_usd: float = Field(default=12.0, gt=0)  # Default USD amount for orders
    default_leverage: int = Field(default=2, ge=1, le=100)  # Default leverage
    default_tp_percent: float = Field(default=0.05, gt=0, le=1)  # Default take profit %
    default_sl_percent: float = Field(default=0.02, gt=0, le=1)  # Default stop loss %
    max_leverage: int = Field(default=10, ge=1, le=100)
    min_confidence: float = Field(default=0.5, ge=0, le=1)
    
    @field_validator('min_confidence')
    @classmethod
    def validate_percentages(cls, v):
        """Validate percentage values."""
        if not 0 < v <= 1:
            raise ValueError("Percentages must be between 0 and 1")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = Field(default="INFO")
    file: Optional[str] = Field(default="trading_consumer.log")
    max_file_size: str = Field(default="10 MB")
    backup_count: int = Field(default=5, ge=1)
    format: str = Field(
        default="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
    )
    
    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()


class AppConfig(BaseModel):
    """Main application configuration."""
    
    telegram: TelegramConfig
    hyperliquid: HyperliquidConfig
    trading: TradingConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    model_config = {
        "env_nested_delimiter": "__"
    } 