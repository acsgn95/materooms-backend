import httpx
from jose import jwt
from app.config import settings

FIREBASE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
FIREBASE_ISSUER = f"https://securetoken.google.com/{settings.FIREBASE_PROJECT_ID}"


async def get_firebase_public_keys() -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(FIREBASE_CERTS_URL)
        return response.json()


async def verify_firebase_token(id_token: str) -> dict:
    keys = await get_firebase_public_keys()
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    public_key = keys.get(kid)

    if not public_key:
        raise ValueError("Geçersiz token: public key bulunamadı")

    payload = jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=settings.FIREBASE_PROJECT_ID,
        issuer=FIREBASE_ISSUER,
    )
    return payload
