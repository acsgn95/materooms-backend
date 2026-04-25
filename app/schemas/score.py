import uuid
from datetime import datetime
from pydantic import BaseModel


class ScoreEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    delta: int
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScoreOut(BaseModel):
    user_id: uuid.UUID
    total_score: int
    payment_regularity: int
    payment_punctuality: int
    dispute_history: int
    verification_level: int
    profile_completeness: int
    last_updated: datetime
    recent_events: list[ScoreEventOut] = []

    model_config = {"from_attributes": True}
