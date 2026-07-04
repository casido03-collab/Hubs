import secrets
from datetime import datetime, date
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from bot.constants import AUTO_WINNER_TG_ID_BASE, AUTO_WINNER_TG_ID_RANGE
from bot.database.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.referral_code == code)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str,
        referred_by_id: int | None = None,
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            referral_code=secrets.token_urlsafe(8),
            referred_by_id=referred_by_id,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_onboarding(
        self, user_id: int, age_range: str, gender: str, interests: list[str]
    ) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(age_range=age_range, gender=gender, interests=interests, onboarding_done=True)
        )

    async def set_subscribed(self, user_id: int, subscribed: bool) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(is_subscribed=subscribed)
        )

    async def update_login(self, user_id: int, streak: int, last_login: datetime) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(login_streak=streak, last_login_date=last_login)
        )

    async def update_bonus_date(self, user_id: int, dt: datetime) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(last_bonus_date=dt)
        )

    async def update_push_date(self, user_id: int, dt: datetime) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(last_push_date=dt)
        )

    async def increment_wins(self, user_id: int) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(total_wins=User.total_wins + 1)
        )

    async def count_referrals(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).where(User.referred_by_id == user_id)
        )
        return result.scalar_one()

    async def total_count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def count_registered_today(self) -> int:
        today = date.today()
        result = await self.session.execute(
            select(func.count()).where(func.date(User.registration_date) == today)
        )
        return result.scalar_one()

    async def get_all_subscribed(self) -> list[User]:
        result = await self.session.execute(
            select(User).where(User.is_subscribed == True)
        )
        return list(result.scalars().all())

    async def get_all_active(self) -> list[User]:
        """All users who finished onboarding — used as broadcast audience in
        white mode (sponsor off), where `is_subscribed` is meaningless."""
        result = await self.session.execute(
            select(User).where(User.onboarding_done == True)
        )
        return list(result.scalars().all())

    async def get_all_registered(self) -> list[User]:
        """Every real registered user regardless of onboarding/subscription
        status, excluding auto-generated fake winners. Used for broadcasts
        meant to reach the entire user base (e.g. new season announcements)."""
        result = await self.session.execute(
            select(User).where(
                (User.telegram_id < AUTO_WINNER_TG_ID_BASE)
                | (User.telegram_id >= AUTO_WINNER_TG_ID_BASE + AUTO_WINNER_TG_ID_RANGE)
            )
        )
        return list(result.scalars().all())
