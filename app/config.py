from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://materooms:secret@localhost:5432/materooms"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-me-in-production-min-32-chars-long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    OTP_EXPIRE_SECONDS: int = 300
    OTP_MAX_ATTEMPTS: int = 5

    SMS_PROVIDER: str = "console"  # "console" | "netgsm" | "twilio"
    SMS_API_KEY: str = ""
    SMS_API_SECRET: str = ""
    SMS_SENDER: str = "MateRooms"

    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    ENVIRONMENT: str = "development"

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://www.materooms.com",
        "https://materooms.com",
    ]


settings = Settings()
