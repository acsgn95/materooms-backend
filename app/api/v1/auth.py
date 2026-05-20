from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.db.redis import get_redis
from app.core.otp import create_otp, verify_otp, send_otp
from app.core.security import create_access_token, create_temp_token, create_refresh_token, decode_token
from app.core.rate_limit import rate_limit
from app.models.user import User, UserProfile, OtpCode, RefreshToken
from app.schemas.auth import SendOtpRequest, VerifyOtpRequest, RegisterRequest, LoginRequest, TokenRefreshRequest, AuthResponse, TokenResponse
from app.schemas.common import ok, err, ResponseEnvelope
from app.config import settings
import hashlib

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-otp", response_model=ResponseEnvelope[dict])
async def send_otp_endpoint(body: SendOtpRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    await rate_limit(request, redis, limit=10)

    if body.purpose == "register":
        result = await db.execute(select(User).where(User.phone == body.phone, User.is_deleted == False))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=err("PHONE_ALREADY_EXISTS", "Bu telefon numarası zaten kayıtlı").model_dump())
    else:
        result = await db.execute(select(User).where(User.phone == body.phone, User.is_deleted == False))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail=err("USER_NOT_FOUND", "Bu telefon numarasıyla kayıtlı kullanıcı bulunamadı").model_dump())
        if not user.is_active:
            raise HTTPException(status_code=403, detail=err("ACCOUNT_BANNED", "Hesabınız askıya alınmıştır").model_dump())

    code = await create_otp(redis, body.phone, body.purpose)
    await send_otp(body.phone, code)

    otp_record = OtpCode(phone=body.phone, code=code, purpose=body.purpose, expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.OTP_EXPIRE_SECONDS))
    db.add(otp_record)
    await db.commit()

    return ok({"expires_in": settings.OTP_EXPIRE_SECONDS})


@router.post("/verify-otp", response_model=ResponseEnvelope[dict])
async def verify_otp_endpoint(body: VerifyOtpRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    await rate_limit(request, redis, limit=10)

    success, reason = await verify_otp(redis, body.phone, body.purpose, body.code)
    if not success:
        messages = {
            "OTP_EXPIRED": "Kod süresi dolmuş, yeni kod isteyin",
            "TOO_MANY_ATTEMPTS": "Çok fazla yanlış deneme",
            "INVALID_CODE": "Geçersiz kod",
        }
        raise HTTPException(status_code=400, detail=err(reason, messages.get(reason, "Geçersiz kod")).model_dump())

    result = await db.execute(select(OtpCode).where(OtpCode.phone == body.phone, OtpCode.purpose == body.purpose, OtpCode.used == False).order_by(OtpCode.created_at.desc()))
    otp_record = result.scalar_one_or_none()
    if otp_record:
        otp_record.used = True
        await db.commit()

    temp_token = create_temp_token(body.phone, scope=body.purpose)
    return ok({"temp_token": temp_token})


@router.post("/register", response_model=ResponseEnvelope[AuthResponse])
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    await rate_limit(request, redis, limit=10)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail=err("MISSING_TOKEN", "Token gerekli").model_dump())

    payload = decode_token(auth_header[7:])
    if not payload or payload.get("scope") != "register":
        raise HTTPException(status_code=401, detail=err("INVALID_TOKEN", "Geçersiz token").model_dump())

    phone = payload.get("phone")

    user = User(phone=phone)
    db.add(user)
    await db.flush()

    profile = UserProfile(
        user_id=user.id,
        full_name=body.full_name,
        age=body.age,
        gender=body.gender,
        city=body.city,
        neighborhood=body.neighborhood,
        occupation=body.occupation,
        budget_min=body.budget_min,
        budget_max=body.budget_max,
        bio=body.bio,
        sleep_schedule=body.sleep_schedule,
        cleanliness_level=body.cleanliness_level,
        smoking=body.smoking,
        pets=body.pets,
        guests=body.guests,
        noise_tolerance=body.noise_tolerance,
        verification_badges=["phone_verified"],
        kvkk_consent=body.kvkk_consent,
        kvkk_consent_at=datetime.now(timezone.utc),
    )
    db.add(profile)

    from app.models.score import FlatmateScore, ScoreEvent
    score = FlatmateScore(user_id=user.id, total_score=5, verification_level=5)
    db.add(score)
    db.add(ScoreEvent(user_id=user.id, event_type="phone_verified", delta=5, description="Telefon doğrulaması tamamlandı"))

    access_token = create_access_token(str(user.id))
    raw_refresh, hashed_refresh = create_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))

    await db.commit()
    await db.refresh(user)
    await db.refresh(user.profile)

    return ok(AuthResponse(user=user, access_token=access_token, refresh_token=raw_refresh))


@router.post("/login", response_model=ResponseEnvelope[AuthResponse])
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    await rate_limit(request, redis, limit=10)

    success, reason = await verify_otp(redis, body.phone, "login", body.code)
    if not success:
        messages = {"OTP_EXPIRED": "Kod süresi dolmuş", "TOO_MANY_ATTEMPTS": "Çok fazla yanlış deneme", "INVALID_CODE": "Geçersiz kod"}
        raise HTTPException(status_code=400, detail=err(reason, messages.get(reason, "Geçersiz kod")).model_dump())

    result = await db.execute(
        select(User).options(selectinload(User.profile)).where(User.phone == body.phone, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=err("USER_NOT_FOUND", "Kullanıcı bulunamadı").model_dump())

    access_token = create_access_token(str(user.id))
    raw_refresh, hashed_refresh = create_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    await db.commit()

    return ok(AuthResponse(user=user, access_token=access_token, refresh_token=raw_refresh))


@router.post("/token/refresh", response_model=ResponseEnvelope[TokenResponse])
async def refresh_token(body: TokenRefreshRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.revoked == False))
    token_record = result.scalar_one_or_none()

    if not token_record or token_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail=err("INVALID_REFRESH_TOKEN", "Geçersiz veya süresi dolmuş token").model_dump())

    token_record.revoked = True
    access_token = create_access_token(str(token_record.user_id))
    raw_refresh, hashed_refresh = create_refresh_token()
    db.add(RefreshToken(
        user_id=token_record.user_id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    await db.commit()

    return ok(TokenResponse(access_token=access_token, refresh_token=raw_refresh))
