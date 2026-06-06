import logging
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from aiogram import Bot
from bot.config import settings
from bot.database import async_session_factory
from bot.database.repositories import UserRepository, SeasonRepository
from bot.database.repositories.raffle_repo import RaffleRepository
from bot.services.raffle import RaffleService
from bot.services.notifications import send_push, broadcast_out_of_turn

logger = logging.getLogger(__name__)


async def check_mini_raffles(bot: Bot) -> None:
    """Check if any mini raffle should be conducted right now."""
    async with async_session_factory() as session:
        season_repo = SeasonRepository(session)
        raffle_repo = RaffleRepository(session)

        season = await season_repo.get_active()
        if not season:
            return

        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(pytz.utc)

        pending = await raffle_repo.get_pending_for_season(season.id)
        for raffle in pending:
            if raffle.scheduled_at <= now:
                raffle_service = RaffleService(session)
                winner_id, winner_name = await raffle_service.conduct_mini_raffle(raffle)

                if winner_id:
                    from bot.database.repositories import WinnerRepository
                    winner_repo = WinnerRepository(session)
                    winner = await winner_repo.get_by_id(winner_id)
                    user_repo = UserRepository(session)
                    user = await user_repo.get_by_id(winner.user_id) if winner else None

                    # Notify admin
                    for admin_id in settings.admin_ids:
                        try:
                            from bot.keyboards import admin_winner_actions_keyboard
                            await bot.send_message(
                                admin_id,
                                f"🏆 <b>Определён победитель мини-розыгрыша</b>\n\n"
                                f"Приз: <b>{raffle.prize_amount} ₽</b>\n"
                                f"Имя: <b>{winner_name}</b>\n"
                                f"Username: @{user.username or '—'}\n"
                                f"Telegram ID: <code>{user.telegram_id}</code>",
                                parse_mode="HTML",
                                reply_markup=admin_winner_actions_keyboard(winner_id),
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify admin {admin_id}: {e}")

                    # Broadcast
                    await broadcast_out_of_turn(
                        bot,
                        f"🎁 <b>Мини-розыгрыш завершён!</b>\n\n"
                        f"Приз: <b>{raffle.prize_amount} ₽</b>\n"
                        f"Победитель: <b>{winner_name}</b>\n\n"
                        f"Смотрите результаты в разделе «Победители»!",
                    )


async def check_season_end(bot: Bot) -> None:
    """Check if active season should end."""
    async with async_session_factory() as session:
        season_repo = SeasonRepository(session)
        season = await season_repo.get_active()
        if not season:
            return

        now = datetime.now(pytz.utc)
        end = season.end_date if season.end_date.tzinfo else pytz.utc.localize(season.end_date)

        if now >= end:
            raffle_service = RaffleService(session)
            winner_id, winner_name = await raffle_service.conduct_main_raffle(season)

            if winner_id:
                from bot.database.repositories import WinnerRepository, UserRepository
                winner_repo = WinnerRepository(session)
                user_repo = UserRepository(session)
                winner = await winner_repo.get_by_id(winner_id)
                user = await user_repo.get_by_id(winner.user_id) if winner else None

                for admin_id in settings.admin_ids:
                    try:
                        from bot.keyboards import admin_winner_actions_keyboard
                        await bot.send_message(
                            admin_id,
                            f"💎 <b>Главный приз сезона #{season.number} разыгран!</b>\n\n"
                            f"Приз: <b>{season.prize_name}</b>\n"
                            f"Победитель: <b>{winner_name}</b>\n"
                            f"Username: @{user.username or '—' if user else '—'}\n"
                            f"Telegram ID: <code>{user.telegram_id if user else '—'}</code>",
                            parse_mode="HTML",
                            reply_markup=admin_winner_actions_keyboard(winner_id),
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin_id}: {e}")

                await broadcast_out_of_turn(
                    bot,
                    f"🏆 <b>Главный приз сезона #{season.number} разыгран!</b>\n\n"
                    f"Приз: <b>{season.prize_name}</b>\n"
                    f"Победитель: <b>{winner_name}</b>\n\n"
                    f"Смотрите результаты в разделе «Победители»!",
                )


async def send_smart_pushes(bot: Bot) -> None:
    """Send smart push notifications."""
    async with async_session_factory() as session:
        season_repo = SeasonRepository(session)
        user_repo = UserRepository(session)
        raffle_repo = RaffleRepository(session)

        season = await season_repo.get_active()
        if not season:
            return

        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
        users = await user_repo.get_all_subscribed()

        end = season.end_date.astimezone(tz) if season.end_date.tzinfo else tz.localize(season.end_date)
        hours_to_end = (end - now).total_seconds() / 3600

        next_raffle = await raffle_repo.get_next(season.id)
        hours_to_raffle = None
        if next_raffle:
            raffle_dt = next_raffle.scheduled_at.astimezone(tz) if next_raffle.scheduled_at.tzinfo else tz.localize(next_raffle.scheduled_at)
            hours_to_raffle = (raffle_dt - now).total_seconds() / 3600

        for user in users:
            sp = await season_repo.get_participant(user.id, season.id)
            if not sp:
                continue

            # Not got tickets today
            login_needed = not user.last_login_date or (
                user.last_login_date.astimezone(tz).date() < now.date()
            )
            if login_needed:
                await send_push(bot, user, "🎫 Сегодня вы ещё не получили билеты! Зайдите в бота.", session)
                continue

            # 24h to season end
            if 22 <= hours_to_end <= 26:
                await send_push(bot, user, "⚠️ До завершения сезона осталось 24 часа! Успейте улучшить позицию.", session)
                continue

            # 12h to mini raffle
            if hours_to_raffle is not None and 10 <= hours_to_raffle <= 14:
                await send_push(bot, user, f"💎 До мини-розыгрыша ({next_raffle.prize_amount} ₽) осталось 12 часов!", session)
                continue

            # Streak danger
            bonus_last = user.last_bonus_date
            if bonus_last:
                last_local = bonus_last.astimezone(tz)
                if (now.date() - last_local.date()).days >= 1:
                    await send_push(bot, user, "🔥 Серия входов под угрозой! Зайдите в бота сегодня.", session)
                    continue

        await session.commit()


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=pytz.utc)

    # Check mini raffles every 5 minutes
    scheduler.add_job(
        check_mini_raffles,
        trigger="interval",
        minutes=5,
        kwargs={"bot": bot},
        id="check_mini_raffles",
        replace_existing=True,
    )

    # Check season end every 10 minutes
    scheduler.add_job(
        check_season_end,
        trigger="interval",
        minutes=10,
        kwargs={"bot": bot},
        id="check_season_end",
        replace_existing=True,
    )

    # Smart pushes once a day at 10:00 MSK
    scheduler.add_job(
        send_smart_pushes,
        trigger=CronTrigger(hour=7, minute=0, timezone=pytz.utc),  # 10:00 MSK = 07:00 UTC
        kwargs={"bot": bot},
        id="smart_pushes",
        replace_existing=True,
    )

    return scheduler
