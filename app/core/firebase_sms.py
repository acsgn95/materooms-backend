import httpx
from app.config import settings

FIREBASE_SEND_URL = "https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode"
FIREBASE_VERIFY_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPhoneNumber"


async def send_sms_otp(phone: str) -> str:
    """Firebase üzerinden SMS gönderir, session_info döner."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{FIREBASE_SEND_URL}?key={settings.FIREBASE_API_KEY}",
            json={"phoneNumber": phone, "recaptchaToken": "test"},
        )
        data = response.json()
        if "sessionInfo" not in data:
            error = data.get("error", {}).get("message", "SMS gönderilemedi")
            raise Exception(f"Firebase SMS hatası: {error}")
        return data["sessionInfo"]


async def verify_sms_otp(session_info: str, code: str) -> bool:
    """Firebase OTP kodunu doğrular."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{FIREBASE_VERIFY_URL}?key={settings.FIREBASE_API_KEY}",
            json={"sessionInfo": session_info, "code": code},
        )
        data = response.json()
        if "idToken" in data:
            return True
        return False
