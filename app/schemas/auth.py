from pydantic import BaseModel, field_validator
import re


class SendOtpRequest(BaseModel):
    phone: str
    purpose: str  # "register" | "login"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^\+90[0-9]{10}$", v):
            raise ValueError("Telefon numarası +90XXXXXXXXXX formatında olmalı")
        return v

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        if v not in ("register", "login"):
            raise ValueError("purpose 'register' veya 'login' olmalı")
        return v


class VerifyOtpRequest(BaseModel):
    phone: str
    code: str
    purpose: str


class RegisterRequest(BaseModel):
    full_name: str
    age: int | None = None
    gender: str | None = None
    city: str
    neighborhood: str | None = None
    occupation: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    bio: str | None = None
    sleep_schedule: str | None = None
    cleanliness_level: str | None = None
    smoking: bool = False
    pets: bool = False
    guests: str | None = None
    noise_tolerance: str | None = None
    kvkk_consent: bool

    @field_validator("kvkk_consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("KVKK onayı zorunludur")
        return v


class LoginRequest(BaseModel):
    phone: str
    code: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    user: "UserOut"
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class EmailRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    age: int | None = None
    gender: str | None = None
    city: str
    neighborhood: str | None = None
    occupation: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    bio: str | None = None
    sleep_schedule: str | None = None
    cleanliness_level: str | None = None
    smoking: bool = False
    pets: bool = False
    guests: str | None = None
    noise_tolerance: str | None = None
    kvkk_consent: bool

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalı")
        return v

    @field_validator("kvkk_consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("KVKK onayı zorunludur")
        return v


class EmailLoginRequest(BaseModel):
    email: str
    password: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalı")
        return v


from app.schemas.user import UserOut
AuthResponse.model_rebuild()
