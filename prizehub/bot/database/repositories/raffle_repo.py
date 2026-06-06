from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import MiniRaffle


class RaffleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_mini(
        self, season_id: int, day_number: int, prize_amount: int, scheduled_at: datetime
    ) -> MiniRaffle:
        raffle = MiniRaffle(
            season_id=season_id,
            day_number=day_number,
            prize_amount=prize_amount,
            scheduled_at=scheduled_at,
        )
        self.session.add(raffle)
        await self.session.flush()
        return raffle

    async def get_by_id(self, raffle_id: int) -> MiniRaffle | None:
        result = await self.session.execute(
            select(MiniRaffle).where(MiniRaffle.id == raffle_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_for_season(self, season_id: int) -> list[MiniRaffle]:
        result = await self.session.execute(
            select(MiniRaffle).where(
                MiniRaffle.season_id == season_id,
                MiniRaffle.status == "scheduled",
            ).order_by(MiniRaffle.scheduled_at)
        )
        return list(result.scalars().all())

    async def get_next(self, season_id: int) -> MiniRaffle | None:
        raffles = await self.get_pending_for_season(season_id)
        return raffles[0] if raffles else None

    async def set_winner(self, raffle_id: int, winner_id: int) -> None:
        await self.session.execute(
            update(MiniRaffle)
            .where(MiniRaffle.id == raffle_id)
            .values(
                winner_id=winner_id,
                conducted_at=datetime.utcnow(),
                status="pending_admin",
            )
        )

    async def mark_done(self, raffle_id: int) -> None:
        await self.session.execute(
            update(MiniRaffle).where(MiniRaffle.id == raffle_id).values(status="done")
        )

    async def get_all_for_season(self, season_id: int) -> list[MiniRaffle]:
        result = await self.session.execute(
            select(MiniRaffle)
            .where(MiniRaffle.season_id == season_id)
            .order_by(MiniRaffle.day_number)
        )
        return list(result.scalars().all())
