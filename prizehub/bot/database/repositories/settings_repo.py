from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import GlobalSetting


class GlobalSettingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str, default: str = "") -> str:
        result = await self.session.execute(
            select(GlobalSetting).where(GlobalSetting.key == key)
        )
        row = result.scalar_one_or_none()
        return row.value if row else default

    async def set(self, key: str, value: str) -> None:
        stmt = insert(GlobalSetting).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value})
        await self.session.execute(stmt)
        await self.session.commit()
