import asyncio
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings


def _build_gmail_service():
    creds = Credentials(
        token=None,
        refresh_token=settings.GMAIL_REFRESH_TOKEN,
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("gmail", "v1", credentials=creds)


def _send_email_sync(to: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"MateRooms <{settings.MAIL_FROM}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service = _build_gmail_service()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


async def send_email(to: str, subject: str, html: str) -> None:
    if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_REFRESH_TOKEN:
        print(f"[mail] To: {to} | Subject: {subject}")
        return

    try:
        await asyncio.to_thread(_send_email_sync, to, subject, html)
    except Exception as e:
        print(f"[mail] Error: {e}")


async def send_otp_email(to: str, code: str) -> None:
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px;">
        <h2 style="color:#E8192C;">MateRooms</h2>
        <p>Giriş doğrulama kodunuz:</p>
        <div style="background:#f5f5f5;border-radius:8px;padding:24px;text-align:center;margin:24px 0;">
            <span style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#E8192C;">{code}</span>
        </div>
        <p style="color:#666;font-size:14px;">Bu kod 5 dakika geçerlidir. Kodu kimseyle paylaşmayın.</p>
    </div>
    """
    await send_email(to, "MateRooms - Doğrulama Kodunuz", html)


async def send_password_reset_email(to: str, reset_url: str) -> None:
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px;">
        <h2 style="color:#E8192C;">MateRooms</h2>
        <p>Şifrenizi sıfırlamak için aşağıdaki butona tıklayın:</p>
        <div style="text-align:center;margin:32px 0;">
            <a href="{reset_url}" style="background:#E8192C;color:white;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:bold;">
                Şifremi Sıfırla
            </a>
        </div>
        <p style="color:#666;font-size:14px;">Bu link 15 dakika geçerlidir. Şifre sıfırlama talebinde bulunmadıysanız bu e-postayı görmezden gelin.</p>
    </div>
    """
    await send_email(to, "MateRooms - Şifre Sıfırlama", reset_url)
