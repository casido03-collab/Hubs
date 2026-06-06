from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Winner


class WinnerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        season_id: int,
        raffle_type: str,
        prize: str,
    ) -> Winner:
        winner = Winner(
            user_id=user_id,
            season_id=season_id,
            raffle_type=raffle_type,
            prize=prize,
        )
        self.session.add(winner)
        await self.session.flush()
        return winner

    async def get_by_id(self, winner_id: int) -> Winner | None:
        result = await self.session.execute(select(Winner).where(Winner.id == winner_id))
        return result.scalar_one_or_none()

    async def publish(self, winner_id: int, photo_id: str | None, description: str | None) -> None:
        await self.session.execute(
            update(Winner)
            .where(Winner.id == winner_id)
            .values(
                photo_id=photo_id,
                description=description,
                status="published",
                published_at=datetime.utcnow(),
            )
        )

    async def update_photo(self, winner_id: int, photo_id: str | None, description: str | None) -> None:
        """Update photo/description for an already-published winner (no status change)."""
        values: dict = {}
        if photo_id is not None:
            values["photo_id"] = photo_id
        if description is not None:
            values["description"] = description
        if values:
            await self.session.execute(
                update(Winner).where(Winner.id == winner_id).values(**values)
            )

    async def get_published(self, limit: int = 20, offset: int = 0) -> list[Winner]:
        result = await self.session.execute(
            select(Winner)
            .where(Winner.status == "published")
            .order_by(Winner.published_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_pending(self) -> list[Winner]:
        result = await self.session.execute(
            select(Winner).where(Winner.status == "pending")
        )
        return list(result.scalars().all())

    async def get_all(self, limit: int = 50) -> list[Winner]:
        result = await self.session.execute(
            select(Winner).order_by(Winner.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
