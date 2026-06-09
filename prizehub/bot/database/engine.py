from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from bot.config import settings
from bot.database.models import Base

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Idempotent column migrations — safe to run on every restart
        await conn.execute(text(
            "ALTER TABLE seasons "
            "ADD COLUMN IF NOT EXISTS sponsor_type VARCHAR(16) NOT NULL DEFAULT 'channel'"
        ))
        await conn.execute(text(
            "ALTER TABLE seasons "
            "ADD COLUMN IF NOT EXISTS sponsor_bot VARCHAR(256) NULL"
        ))
        await conn.execute(text(
            "ALTER TABLE seasons "
            "ALTER COLUMN sponsor_channel DROP NOT NULL"
        ))


async def dispose_engine() -> None:
    await engine.dispose()
