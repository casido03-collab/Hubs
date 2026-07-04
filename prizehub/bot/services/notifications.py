import asyncio
import logging
from datetime import datetime, timedelta
import pytz
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

# Safe send rate: 20 msg/sec (Telegram hard limit is 30/sec, we stay well below)
_SEND_INTERVAL = 0.05

logger = logging.getLogger(__name__)
from bot.config import settings
from bot.database.repositories import UserRepository, SeasonRepository
from bot.database.models import User, PushLog
from bot.database import async_session_factory
from bot.services import sponsor_mode


async def _broadcast_audience(session: AsyncSession) -> list[User]:
    """Who should receive broadcasts/smart-pushes.

    When sponsor mode is required, only users who are actually subscribed
    have access — broadcasting to others would be pointless/confusing.
    In white mode (sponsor off), subscription is irrelevant — `is_subscribed`
    may be False for everyone, so we broadcast to all onboarded users instead
    (otherwise broadcasts silently reach nobody, including the admin)."""
    user_repo = UserRepository(session)
    if sponsor_mode.is_required():
        return await user_repo.get_all_subscribed()
    return await user_repo.get_all_active()


async def _can_send_push(user: User) -> bool:
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    if user.last_push_date is None:
        return True
    last = user.last_push_date.astimezone(tz) if user.last_push_date.tzinfo else tz.localize(user.last_push_date)
    return (now - last).total_seconds() >= 86400


async def _mark_push_sent(session: AsyncSession, user: User, push_type: str) -> None:
    tz = pytz.timezone(settings.TIMEZONE)
    await UserRepository(session).update_push_date(user.id, datetime.now(tz))
    log = PushLog(user_id=user.id, push_type=push_type)
    session.add(log)


async def send_push(
    bot: Bot,
    user: User,
    text: str,
    session: AsyncSession,
    out_of_turn: bool = False,
    push_type: str = "regular",
) -> bool:
    if not out_of_turn and not await _can_send_push(user):
        return False
    try:
        await bot.send_message(chat_id=user.telegram_id, text=text)
        if not out_of_turn:
            await _mark_push_sent(session, user, push_type)
        else:
            log = PushLog(user_id=user.id, push_type=push_type)
            session.add(log)
        return True
    except (TelegramForbiddenError, TelegramBadRequest):
        return False


async def broadcast_out_of_turn(
    bot: Bot,
    text: str,
    exclude_telegram_id: int | None = None,
    push_type: str = "broadcast",
    audience: str = "subscribed",
) -> None:
    """audience: "subscribed" (default, sponsor-aware) or "all" (every
    registered user regardless of subscription — e.g. new season announcements)."""
    async with async_session_factory() as session:
        if audience == "all":
            users = await UserRepository(session).get_all_registered()
        else:
            users = await _broadcast_audience(session)
        total = len(users)
        sent = 0
        blocked = 0
        failed = 0
        logger.info(f"broadcast_out_of_turn [{push_type}]: starting, audience={total}")
        for user in users:
            if exclude_telegram_id and user.telegram_id == exclude_telegram_id:
                continue
            try:
                await bot.send_message(chat_id=user.telegram_id, text=text, parse_mode="HTML")
                log = PushLog(user_id=user.id, push_type=push_type)
                session.add(log)
                sent += 1
            except (TelegramForbiddenError, TelegramBadRequest) as e:
                if "blocked" in str(e).lower() or "forbidden" in str(e).lower():
                    blocked += 1
                else:
                    failed += 1
                    logger.warning(f"broadcast_out_of_turn [{push_type}]: failed for {user.telegram_id}: {e}")
            await asyncio.sleep(_SEND_INTERVAL)
        await session.commit()
        logger.info(
            f"broadcast_out_of_turn [{push_type}]: done — sent={sent}, blocked={blocked}, failed={failed}, total={total}"
        )
