import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.models import *  # noqa: F401,F403
from app.config import settings


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("[init_db] Tables ensured.")


if __name__ == "__main__":
    asyncio.run(main())
