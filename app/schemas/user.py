import uuid
from datetime import datetime
from pydantic import BaseModel


class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    age: int | None = None
    gender: str | None = None
    city: str | None = None
    neighborhood: str | None = None
    occupation: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    bio: str | None = None
    sleep_schedule: str | None = None
    cleanliness_level: str | None = None
    smoking: bool | None = None
    pets: bool | None = None
    guests: str | None = None
    noise_tolerance: str | None = None


class UserProfileOut(BaseModel):
    full_name: str | None
    age: int | None
    gender: str | None
    city: str | None
    neighborhood: str | None
    occupation: str | None
    budget_min: int | None
    budget_max: int | None
    bio: str | None
    profile_photo_url: str | None
    sleep_schedule: str | None
    cleanliness_level: str | None
    smoking: bool
    pets: bool
    guests: str | None
    noise_tolerance: str | None
    verification_badges: list[str]

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: uuid.UUID
    phone: str
    created_at: datetime
    profile: UserProfileOut | None

    model_config = {"from_attributes": True}
