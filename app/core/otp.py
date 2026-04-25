import secrets
from redis.asyncio import Redis
from app.config import settings


def _key(phone: str, purpose: str) -> str:
    return f"otp:{purpose}:{phone}"


def _attempts_key(phone: str, purpose: str) -> str:
    return f"otp_attempts:{purpose}:{phone}"


async def create_otp(redis: Redis, phone: str, purpose: str) -> str:
    code = str(secrets.randbelow(900000) + 100000)
    key = _key(phone, purpose)
    await redis.set(key, code, ex=settings.OTP_EXPIRE_SECONDS)
    await redis.delete(_attempts_key(phone, purpose))
    return code


async def verify_otp(redis: Redis, phone: str, purpose: str, code: str) -> tuple[bool, str]:
    key = _key(phone, purpose)
    attempts_key = _attempts_key(phone, purpose)

    stored = await redis.get(key)
    if not stored:
        return False, "OTP_EXPIRED"

    attempts = int(await redis.get(attempts_key) or 0)
    if attempts >= settings.OTP_MAX_ATTEMPTS:
        return False, "TOO_MANY_ATTEMPTS"

    if stored != code:
        await redis.incr(attempts_key)
        await redis.expire(attempts_key, settings.OTP_EXPIRE_SECONDS)
        return False, "INVALID_CODE"

    await redis.delete(key)
    await redis.delete(attempts_key)
    return True, "OK"


async def send_otp(phone: str, code: str):
    if settings.SMS_PROVIDER == "console":
        print(f"[SMS-CONSOLE] To: {phone}  Code: {code}")
        return
    # TODO: Netgsm veya Twilio entegrasyonu buraya eklenecek
