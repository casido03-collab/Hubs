from datetime import datetime, timedelta
import pytz
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.database.repositories import UserRepository, SeasonRepository
from bot.database.models import User, PushLog
from bot.database import async_session_factory


async def _can_send_push(user: User) -> bool:
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    if user.last_push_date is None:
        return True
    last = user.last_push_date.astimezone(tz) if user.last_push_date.tzinfo else tz.localize(user.last_push_date)
    return (now - last).total_seconds() >= 86400


async def _mark_push_sent(session: AsyncSession, user: User) -> None:
    tz = pytz.timezone(settings.TIMEZONE)
    await UserRepository(session).update_push_date(user.id, datetime.now(tz))
    log = PushLog(user_id=user.id, push_type="regular")
    session.add(log)


async def send_push(bot: Bot, user: User, text: str, session: AsyncSession, out_of_turn: bool = False) -> bool:
    if not out_of_turn and not await _can_send_push(user):
        return False
    try:
        await bot.send_message(chat_id=user.telegram_id, text=text)
        if not out_of_turn:
            await _mark_push_sent(session, user)
        else:
            log = PushLog(user_id=user.id, push_type="out_of_turn")
            session.add(log)
        return True
    except (TelegramForbiddenError, TelegramBadRequest):
        return False


async def broadcast_out_of_turn(bot: Bot, text: str, exclude_telegram_id: int | None = None) -> None:
    async with async_session_factory() as session:
        users = await UserRepository(session).get_all_subscribed()
        for user in users:
            if exclude_telegram_id and user.telegram_id == exclude_telegram_id:
                continue
            try:
                await bot.send_message(chat_id=user.telegram_id, text=text, parse_mode="HTML")
                log = PushLog(user_id=user.id, push_type="broadcast")
                session.add(log)
            except (TelegramForbiddenError, TelegramBadRequest):
                pass
        await session.commit()
