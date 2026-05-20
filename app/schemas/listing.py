import uuid
from datetime import datetime, date
from pydantic import BaseModel


class ListingCreate(BaseModel):
    listing_type: str  # room_available | looking_for_room | looking_together
    title: str
    description: str | None = None
    city: str
    district: str
    neighborhood: str | None = None
    rent_full: int
    rent_per_person: int | None = None
    move_in_date: date
    residents_current: int = 0
    residents_total: int
    house_rules: dict = {"smoking": False, "pets": False, "gender_preference": "any"}
    amenities: list[str] = []


class ListingUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    rent_full: int | None = None
    rent_per_person: int | None = None
    move_in_date: date | None = None
    residents_current: int | None = None
    residents_total: int | None = None
    house_rules: dict | None = None
    amenities: list[str] | None = None
    is_active: bool | None = None


class ListingOwnerBrief(BaseModel):
    id: uuid.UUID
    full_name: str | None = None
    profile_photo_url: str | None = None
    verification_badges: list[str] = []
    flatmate_score: int | None = None

    model_config = {"from_attributes": True}


class ListingOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    listing_type: str
    title: str
    description: str | None
    city: str
    district: str
    neighborhood: str | None
    rent_full: int
    rent_per_person: int | None
    move_in_date: date
    residents_current: int
    residents_total: int
    house_rules: dict
    amenities: list[str]
    is_active: bool
    expires_at: datetime
    created_at: datetime
    photos: list["ListingPhotoOut"] = []
    owner: ListingOwnerBrief | None = None

    model_config = {"from_attributes": True}


class ListingPhotoOut(BaseModel):
    id: uuid.UUID
    url: str
    sort_order: int

    model_config = {"from_attributes": True}


ListingOut.model_rebuild()
