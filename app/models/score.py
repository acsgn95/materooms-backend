import uuid
from datetime import datetime
from sqlalchemy import SmallInteger, String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class FlatmateScore(Base):
    __tablename__ = "flatmate_scores"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    total_score: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    payment_regularity: Mapped[int] = mapped_column(SmallInteger, default=0)
    payment_punctuality: Mapped[int] = mapped_column(SmallInteger, default=0)
    dispute_history: Mapped[int] = mapped_column(SmallInteger, default=0)
    verification_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    profile_completeness: Mapped[int] = mapped_column(SmallInteger, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="score")
    events: Mapped[list["ScoreEvent"]] = relationship("ScoreEvent", back_populates="score_owner", primaryjoin="FlatmateScore.user_id == ScoreEvent.user_id", foreign_keys="ScoreEvent.user_id")


class ScoreEvent(Base):
    __tablename__ = "score_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    delta: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    score_owner: Mapped["FlatmateScore"] = relationship("FlatmateScore", back_populates="events", foreign_keys=[user_id], primaryjoin="ScoreEvent.user_id == FlatmateScore.user_id")
