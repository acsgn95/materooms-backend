import uuid
from datetime import datetime
from pydantic import BaseModel


class MessageCreate(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID | None
    participant_a: uuid.UUID
    participant_b: uuid.UUID
    created_at: datetime
    last_message: MessageOut | None = None

    model_config = {"from_attributes": True}
