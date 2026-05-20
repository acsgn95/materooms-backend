import uuid
from datetime import datetime, date
from sqlalchemy import String, Boolean, DateTime, Date, Integer, SmallInteger, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB

from app.db.base import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    listing_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    neighborhood: Mapped[str | None] = mapped_column(String(100))
    rent_full: Mapped[int] = mapped_column(Integer, nullable=False)
    rent_per_person: Mapped[int | None] = mapped_column(Integer)
    move_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    residents_current: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    residents_total: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    house_rules: Mapped[dict] = mapped_column(JSONB, default=lambda: {"smoking": False, "pets": False, "gender_preference": "any"})
    amenities: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="listings")
    photos: Mapped[list["ListingPhoto"]] = relationship("ListingPhoto", back_populates="listing", cascade="all, delete-orphan")


class ListingPhoto(Base):
    __tablename__ = "listing_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listing: Mapped["Listing"] = relationship("Listing", back_populates="photos")
