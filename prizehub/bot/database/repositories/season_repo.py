from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Season, SeasonParticipant


class SeasonRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self) -> Season | None:
        result = await self.session.execute(
            select(Season).where(Season.is_active == True)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, season_id: int) -> Season | None:
        result = await self.session.execute(select(Season).where(Season.id == season_id))
        return result.scalar_one_or_none()

    async def get_all(self) -> list[Season]:
        result = await self.session.execute(select(Season).order_by(Season.number.desc()))
        return list(result.scalars().all())

    async def create(
        self,
        number: int,
        name: str,
        prize_name: str,
        prize_photo_id: str | None,
        start_date,
        end_date,
        sponsor_type: str = "channel",
        sponsor_channel: str | None = None,
        sponsor_bot: str | None = None,
    ) -> Season:
        season = Season(
            number=number,
            name=name,
            prize_name=prize_name,
            prize_photo_id=prize_photo_id,
            sponsor_type=sponsor_type,
            sponsor_channel=sponsor_channel,
            sponsor_bot=sponsor_bot,
            start_date=start_date,
            end_date=end_date,
            status="pending",
        )
        self.session.add(season)
        await self.session.flush()
        return season

    async def activate(self, season_id: int) -> None:
        await self.session.execute(
            update(Season).where(Season.id != season_id).values(is_active=False)
        )
        await self.session.execute(
            update(Season)
            .where(Season.id == season_id)
            .values(is_active=True, status="active")
        )

    async def finish(self, season_id: int) -> None:
        await self.session.execute(
            update(Season)
            .where(Season.id == season_id)
            .values(is_active=False, status="finished")
        )

    async def set_sponsor_channel_id(self, season_id: int, channel_id: int) -> None:
        await self.session.execute(
            update(Season)
            .where(Season.id == season_id)
            .values(sponsor_channel_id=channel_id)
        )

    async def update_sponsor_channel(self, season_id: int, channel: str) -> None:
        await self.session.execute(
            update(Season)
            .where(Season.id == season_id)
            .values(
                sponsor_type="channel",
                sponsor_channel=channel,
                sponsor_channel_id=None,
                sponsor_bot=None,
            )
        )

    async def update_sponsor_bot(self, season_id: int, bot_username: str) -> None:
        await self.session.execute(
            update(Season)
            .where(Season.id == season_id)
            .values(
                sponsor_type="bot",
                sponsor_bot=bot_username,
                sponsor_channel=None,
                sponsor_channel_id=None,
            )
        )

    async def set_prize_photo(self, season_id: int, photo_id: str) -> None:
        await self.session.execute(
            update(Season).where(Season.id == season_id).values(prize_photo_id=photo_id)
        )

    async def next_number(self) -> int:
        result = await self.session.execute(select(func.max(Season.number)))
        max_num = result.scalar_one_or_none()
        return (max_num or 0) + 1

    # Participants
    async def get_participant(self, user_id: int, season_id: int) -> SeasonParticipant | None:
        result = await self.session.execute(
            select(SeasonParticipant).where(
                SeasonParticipant.user_id == user_id,
                SeasonParticipant.season_id == season_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_participant(self, user_id: int, season_id: int, tickets: int) -> SeasonParticipant:
        sp = SeasonParticipant(user_id=user_id, season_id=season_id, tickets=tickets)
        self.session.add(sp)
        await self.session.flush()
        return sp

    async def add_tickets(self, user_id: int, season_id: int, amount: int) -> int:
        sp = await self.get_participant(user_id, season_id)
        if sp is None:
            sp = await self.add_participant(user_id, season_id, amount)
        else:
            await self.session.execute(
                update(SeasonParticipant)
                .where(
                    SeasonParticipant.user_id == user_id,
                    SeasonParticipant.season_id == season_id,
                )
                .values(tickets=SeasonParticipant.tickets + amount)
            )
            await self.session.refresh(sp)
        return sp.tickets

    async def get_leaderboard(self, season_id: int, limit: int = 100) -> list[SeasonParticipant]:
        result = await self.session.execute(
            select(SeasonParticipant)
            .where(SeasonParticipant.season_id == season_id)
            .order_by(SeasonParticipant.tickets.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_rank(self, user_id: int, season_id: int) -> int:
        subq = (
            select(SeasonParticipant.user_id, SeasonParticipant.tickets)
            .where(SeasonParticipant.season_id == season_id)
            .subquery()
        )
        sp = await self.get_participant(user_id, season_id)
        if sp is None:
            return 0
        result = await self.session.execute(
            select(func.count()).select_from(subq).where(subq.c.tickets > sp.tickets)
        )
        return result.scalar_one() + 1

    async def participants_count(self, season_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).where(SeasonParticipant.season_id == season_id)
        )
        return result.scalar_one()

    async def get_top1(self, season_id: int) -> SeasonParticipant | None:
        result = await self.session.execute(
            select(SeasonParticipant)
            .where(SeasonParticipant.season_id == season_id)
            .order_by(SeasonParticipant.tickets.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all_participants(self, season_id: int) -> list[SeasonParticipant]:
        result = await self.session.execute(
            select(SeasonParticipant).where(SeasonParticipant.season_id == season_id)
        )
        return list(result.scalars().all())

    async def reset_tickets(self, season_id: int) -> None:
        await self.session.execute(
            update(SeasonParticipant)
            .where(SeasonParticipant.season_id == season_id)
            .values(tickets=0)
        )
