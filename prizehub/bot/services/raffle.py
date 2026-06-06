import random
from datetime import datetime, timedelta
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.constants import MINI_RAFFLE_PRIZES, MINI_RAFFLE_START_HOUR, MINI_RAFFLE_END_HOUR
from bot.database.repositories import SeasonRepository, RaffleRepository, WinnerRepository, UserRepository
from bot.database.models import Season, MiniRaffle


def _random_time_on_day(day: datetime) -> datetime:
    tz = pytz.timezone(settings.TIMEZONE)
    start = day.replace(hour=MINI_RAFFLE_START_HOUR, minute=0, second=0, microsecond=0)
    end = day.replace(hour=MINI_RAFFLE_END_HOUR, minute=0, second=0, microsecond=0)
    random_seconds = random.randint(0, int((end - start).total_seconds()))
    return (start + timedelta(seconds=random_seconds)).astimezone(pytz.utc)


class RaffleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.season_repo = SeasonRepository(session)
        self.raffle_repo = RaffleRepository(session)
        self.winner_repo = WinnerRepository(session)
        self.user_repo = UserRepository(session)

    async def schedule_mini_raffles(self, season: Season) -> None:
        """Create all mini raffle entries for a season."""
        tz = pytz.timezone(settings.TIMEZONE)
        start = season.start_date.astimezone(tz) if season.start_date.tzinfo else tz.localize(season.start_date)

        for day, prize in MINI_RAFFLE_PRIZES.items():
            raffle_day = start + timedelta(days=day - 1)
            scheduled_at = _random_time_on_day(raffle_day)
            await self.raffle_repo.create_mini(season.id, day, prize, scheduled_at)

        await self.session.commit()

    async def conduct_mini_raffle(self, raffle: MiniRaffle) -> tuple[int | None, str]:
        """Pick a random winner. Returns (winner_user_id, winner_name)."""
        participants = await self.season_repo.get_all_participants(raffle.season_id)
        if not participants:
            return None, ""

        winner_sp = random.choice(participants)
        user = await self.user_repo.get_by_id(winner_sp.user_id)

        await self.raffle_repo.set_winner(raffle.id, winner_sp.user_id)

        winner = await self.winner_repo.create(
            user_id=winner_sp.user_id,
            season_id=raffle.season_id,
            raffle_type="mini",
            prize=f"{raffle.prize_amount} ₽",
        )

        await self.user_repo.increment_wins(winner_sp.user_id)
        await self.session.commit()

        return winner.id, user.first_name if user else "—"

    async def conduct_main_raffle(self, season: Season) -> tuple[int | None, str]:
        """Top-1 in rating wins the main prize."""
        top1 = await self.season_repo.get_top1(season.id)
        if top1 is None:
            return None, ""

        user = await self.user_repo.get_by_id(top1.user_id)

        winner = await self.winner_repo.create(
            user_id=top1.user_id,
            season_id=season.id,
            raffle_type="main",
            prize=season.prize_name,
        )

        await self.user_repo.increment_wins(top1.user_id)
        await self.season_repo.finish(season.id)
        await self.session.commit()

        return winner.id, user.first_name if user else "—"
