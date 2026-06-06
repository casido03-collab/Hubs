from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import TicketTransaction


class TicketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, user_id: int, season_id: int, amount: int, reason: str) -> None:
        tx = TicketTransaction(
            user_id=user_id,
            season_id=season_id,
            amount=amount,
            reason=reason,
        )
        self.session.add(tx)

    async def total_earned(self, season_id: int) -> int:
        result = await self.session.execute(
            select(func.sum(TicketTransaction.amount)).where(
                TicketTransaction.season_id == season_id,
                TicketTransaction.amount > 0,
            )
        )
        return result.scalar_one_or_none() or 0
