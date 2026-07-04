import httpx
from app.config import settings


async def send_telegram(message: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            })
    except Exception:
        pass


async def notify_new_user(phone: str, full_name: str | None, city: str | None) -> None:
    name = full_name or "İsimsiz"
    location = city or "Belirtilmemiş"
    await send_telegram(
        f"👤 <b>Yeni Kullanıcı</b>\n"
        f"Ad: {name}\n"
        f"Telefon: {phone}\n"
        f"Şehir: {location}"
    )


async def notify_new_listing(title: str, city: str, listing_type: str, rent: int) -> None:
    types = {
        "room_available": "Oda Var",
        "looking_for_room": "Oda Arıyor",
        "looking_together": "Birlikte Arıyor",
    }
    await send_telegram(
        f"🏠 <b>Yeni İlan</b>\n"
        f"Başlık: {title}\n"
        f"Şehir: {city}\n"
        f"Tür: {types.get(listing_type, listing_type)}\n"
        f"Kira: {rent:,} ₺"
    )


async def notify_api_error(path: str, status_code: int, detail: str) -> None:
    await send_telegram(
        f"🚨 <b>API Hatası</b>\n"
        f"Endpoint: {path}\n"
        f"Kod: {status_code}\n"
        f"Detay: {detail[:200]}"
    )
