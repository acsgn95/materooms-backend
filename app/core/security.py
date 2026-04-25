import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.config import settings


def create_access_token(user_id: str, scope: str = "access") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "scope": scope, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_temp_token(phone: str, scope: str = "register") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    return jwt.encode(
        {"phone": phone, "scope": scope, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token() -> tuple[str, str]:
    raw = secrets.token_hex(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
