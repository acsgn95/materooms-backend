from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.feature_flag import FeatureFlag


async def is_enabled(key: str, db: AsyncSession) -> bool:
    result = await db.execute(select(FeatureFlag.enabled).where(FeatureFlag.key == key))
    return result.scalar_one_or_none() or False


async def require_flag(key: str, db: AsyncSession):
    if not await is_enabled(key, db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu özellik henüz aktif değil",
        )
