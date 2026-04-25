"""
Geliştirme ortamı için feature flag seed scripti.
Kullanım: python scripts/seed.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.models.feature_flag import FeatureFlag


async def seed():
    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    flags = [
        FeatureFlag(key="iyzico_payments", enabled=False, description="İyzico ödeme entegrasyonu"),
        FeatureFlag(key="kyc_automation", enabled=False, description="Otomatik kimlik doğrulama (Sumsub)"),
        FeatureFlag(key="face_recognition", enabled=False, description="Yüz tanıma doğrulaması"),
        FeatureFlag(key="criminal_record_llm", enabled=False, description="LLM destekli sabıka kaydı kontrolü"),
        FeatureFlag(key="websocket_messages", enabled=False, description="Gerçek zamanlı mesajlaşma"),
    ]

    async with Session() as db:
        for flag in flags:
            existing = await db.get(FeatureFlag, flag.key)
            if not existing:
                db.add(flag)
                print(f"  + {flag.key} eklendi")
            else:
                print(f"  ~ {flag.key} zaten mevcut")
        await db.commit()

    await engine.dispose()
    print("Seed tamamlandı.")


if __name__ == "__main__":
    asyncio.run(seed())
