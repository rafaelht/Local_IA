from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MessageCreate(BaseModel):
    role: str
    content: str


class MessageRead(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {
        'from_attributes': True
    }


class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None
    favorite: Optional[bool] = None


class ChatRequest(BaseModel):
    role: str = 'user'
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_context_messages: Optional[int] = None
    enable_context_history: Optional[bool] = True


class ConversationRead(BaseModel):
    id: int
    title: str
    pinned: bool
    favorite: bool
    created_at: datetime
    updated_at: datetime
    messages: list[MessageRead] = []

    model_config = {
        'from_attributes': True
    }
