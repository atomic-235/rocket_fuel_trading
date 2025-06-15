"""
Telegram-related Pydantic models.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    """Telegram user information."""
    
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class TelegramChat(BaseModel):
    """Telegram chat information."""
    
    id: int
    type: str  # private, group, supergroup, channel
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TelegramMessage(BaseModel):
    """Telegram message model."""
    
    message_id: int
    from_user: Optional[TelegramUser] = Field(None, alias="from")
    chat: TelegramChat
    date: datetime
    text: Optional[str] = None
    caption: Optional[str] = None
    reply_to_message: Optional["TelegramMessage"] = None
    forward_from: Optional[TelegramUser] = None
    forward_date: Optional[datetime] = None
    edit_date: Optional[datetime] = None
    
    model_config = {
        "populate_by_name": True
        }
    
    @property
    def content(self) -> str:
        """Get message content (text or caption)."""
        return self.text or self.caption or ""
    
    @property
    def sender_name(self) -> str:
        """Get sender display name."""
        if not self.from_user:
            return "Unknown"
        
        if self.from_user.username:
            return f"@{self.from_user.username}"
        
        name_parts = [self.from_user.first_name]
        if self.from_user.last_name:
            name_parts.append(self.from_user.last_name)
        
        return " ".join(name_parts)


class TelegramUpdate(BaseModel):
    """Telegram update model."""
    
    update_id: int
    message: Optional[TelegramMessage] = None
    edited_message: Optional[TelegramMessage] = None
    channel_post: Optional[TelegramMessage] = None
    edited_channel_post: Optional[TelegramMessage] = None
    
    @property
    def effective_message(self) -> Optional[TelegramMessage]:
        """Get the effective message from the update."""
        return (
            self.message or 
            self.edited_message or 
            self.channel_post or 
            self.edited_channel_post
        )


# Enable forward references
TelegramMessage.model_rebuild() 