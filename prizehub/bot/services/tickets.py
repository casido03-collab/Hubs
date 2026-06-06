import random
from datetime import datetime, date
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.constants import (
    TICKETS_START_MIN, TICKETS_START_MAX,
    TICKETS_DAILY_LOGIN_MIN, TICKETS_DAILY_LOGIN_MAX,
    TICKETS_DAILY_BONUS_MIN, TICKETS_DAILY_BONUS_MAX,
    TICKETS_STREAK_MIN, TICKETS_STREAK_MAX,
    TICKETS_REFERRAL_MIN, TICKETS_REFERRAL_MAX,
    TICKETS_REFERRAL_5, TICKETS_REFERRAL_20,
)
from bot.database.repositories import UserRepository, SeasonRepository, TicketRepository
from bot.database.models import User


def _rand(min_val: int, max_val: int) -> int:
    return random.randint(min_val, max_val)


def _now_msk() -> datetime:
    tz = pytz.timezone(settings.TIMEZONE)
    return datetime.now(tz)


class TicketService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.season_repo = SeasonRepository(session)
        self.ticket_repo = TicketRepository(session)

    async def award_start(self, user: User, season_id: int) -> int:
        amount = _rand(TICKETS_START_MIN, TICKETS_START_MAX)
        await self._award(user, season_id, amount, "start")
        return amount

    async def award_daily_login(self, user: User, season_id: int) -> tuple[int, bool]:
        """Returns (tickets_awarded, is_new_day). False if already claimed today."""
        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
        last = user.last_login_date
        if last is not None:
            last_local = last.astimezone(tz) if last.tzinfo else tz.localize(last)
            if last_local.date() == now.date():
                return 0, False

        amount = _rand(TICKETS_DAILY_LOGIN_MIN, TICKETS_DAILY_LOGIN_MAX)

        # Calculate streak
        streak = user.login_streak
        if last is not None:
            last_local = last.astimezone(tz) if last.tzinfo else tz.localize(last)
            diff = (now.date() - last_local.date()).days
            if diff == 1:
                streak += 1
            elif diff > 1:
                streak = 1
        else:
            streak = 1

        await self.user_repo.update_login(user.id, streak, now)
        await self._award(user, season_id, amount, "daily_login")

        if streak > 0 and streak % 7 == 0:
            bonus = _rand(TICKETS_STREAK_MIN, TICKETS_STREAK_MAX)
            await self._award(user, season_id, bonus, "streak_bonus")
            amount += bonus

        return amount, True

    async def award_daily_bonus(self, user: User, season_id: int) -> tuple[int, bool]:
        """Returns (tickets, was_awarded). False if already claimed today."""
        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
        last = user.last_bonus_date
        if last is not None:
            last_local = last.astimezone(tz) if last.tzinfo else tz.localize(last)
            if last_local.date() == now.date():
                return 0, False
        amount = _rand(TICKETS_DAILY_BONUS_MIN, TICKETS_DAILY_BONUS_MAX)
        await self.user_repo.update_bonus_date(user.id, now)
        await self._award(user, season_id, amount, "daily_bonus")
        return amount, True

    async def award_referral(self, referrer: User, season_id: int) -> int:
        referral_count = await self.user_repo.count_referrals(referrer.id)
        amount = _rand(TICKETS_REFERRAL_MIN, TICKETS_REFERRAL_MAX)
        await self._award(referrer, season_id, amount, "referral")

        if referral_count == 5:
            await self._award(referrer, season_id, TICKETS_REFERRAL_5, "referral_5")
            amount += TICKETS_REFERRAL_5
        elif referral_count == 20:
            await self._award(referrer, season_id, TICKETS_REFERRAL_20, "referral_20")
            amount += TICKETS_REFERRAL_20

        return amount

    async def _award(self, user: User, season_id: int, amount: int, reason: str) -> None:
        await self.season_repo.add_tickets(user.id, season_id, amount)
        await self.ticket_repo.log(user.id, season_id, amount, reason)
        await self.session.commit()
