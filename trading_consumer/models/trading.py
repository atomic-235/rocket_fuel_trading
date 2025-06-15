"""
Trading-related Pydantic models.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class SignalType(str, Enum):
    """Trading signal types."""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"


class OrderType(str, Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradingSignal(BaseModel):
    """Trading signal extracted from message."""
    
    signal_type: SignalType
    symbol: str
    price: Optional[Decimal] = None
    quantity: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    leverage: Optional[int] = Field(None, ge=1, le=100)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        """Validate trading symbol format."""
        if not v or len(v) < 2:
            raise ValueError("Symbol must be at least 2 characters")
        return v.upper()
    
    @field_validator('price', 'stop_loss', 'take_profit')
    @classmethod
    def validate_positive_prices(cls, v):
        """Validate that prices are positive."""
        if v is not None and v <= 0:
            raise ValueError("Prices must be positive")
        return v


class TradeOrder(BaseModel):
    """Trade order model."""
    
    id: Optional[str] = None
    symbol: str
    side: SignalType  # buy/sell/long/short
    order_type: OrderType = OrderType.MARKET
    quantity: Decimal = Field(gt=0)
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    leverage: Optional[int] = Field(None, ge=1, le=100)
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    filled_quantity: Decimal = Field(default=Decimal('0'))
    average_price: Optional[Decimal] = None
    fees: Optional[Decimal] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        """Validate trading symbol format."""
        return v.upper()
    
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.status == OrderStatus.FILLED
    
    @property
    def is_active(self) -> bool:
        """Check if order is active (pending or partially filled)."""
        return self.status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]


class Position(BaseModel):
    """Trading position model."""
    
    symbol: str
    side: SignalType  # long/short
    size: Decimal
    entry_price: Decimal = Field(gt=0)
    current_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    realized_pnl: Decimal = Field(default=Decimal('0'))
    leverage: Optional[int] = Field(None, ge=1, le=100)
    margin: Optional[Decimal] = None
    liquidation_price: Optional[Decimal] = None
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        """Validate trading symbol format."""
        return v.upper()
    
    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.side in [SignalType.LONG, SignalType.BUY]
    
    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.side in [SignalType.SHORT, SignalType.SELL]


class TradeResult(BaseModel):
    """Trade execution result."""
    
    success: bool
    order: Optional[TradeOrder] = None
    position: Optional[Position] = None
    error_message: Optional[str] = None
    execution_time: datetime = Field(default_factory=datetime.utcnow)
    exchange_response: Optional[Dict[str, Any]] = None
    fees: Optional[Decimal] = None
    slippage: Optional[Decimal] = None
    
    @property
    def is_successful(self) -> bool:
        """Check if trade was successful."""
        return self.success and self.order is not None


class RiskParameters(BaseModel):
    """Risk management parameters."""
    
    max_position_size: Decimal = Field(gt=0)
    max_leverage: int = Field(default=10, ge=1, le=100)
    stop_loss_percentage: float = Field(default=0.05, gt=0, le=1)
    take_profit_percentage: float = Field(default=0.10, gt=0, le=1)
    risk_per_trade: float = Field(default=0.02, gt=0, le=1)
    max_daily_loss: Decimal = Field(gt=0)
    max_open_positions: int = Field(default=5, ge=1)
    
    @field_validator('stop_loss_percentage', 'take_profit_percentage', 'risk_per_trade')
    @classmethod
    def validate_percentages(cls, v):
        """Validate percentage values."""
        if not 0 < v <= 1:
            raise ValueError("Percentages must be between 0 and 1")
        return v 