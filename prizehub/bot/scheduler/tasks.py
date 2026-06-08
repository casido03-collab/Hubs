import logging
import random
import uuid
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from bot.config import settings
from bot.database import async_session_factory
from bot.database.repositories import UserRepository, SeasonRepository, WinnerRepository
from bot.database.repositories.raffle_repo import RaffleRepository
from bot.services.raffle import RaffleService
from bot.services.notifications import send_push, broadcast_out_of_turn
from bot.services.subscription import check_subscription
from bot.services import sponsor_mode

logger = logging.getLogger(__name__)

# Pool of realistic Russian names for auto-generated winners
_FAKE_NAMES = [
    "Алексей К.", "Мария П.", "Дмитрий В.", "Екатерина Н.",
    "Игорь С.", "Анастасия М.", "Сергей Л.", "Ольга Д.",
    "Андрей Т.", "Наталья Б.", "Павел Ж.", "Юлия Р.",
    "Максим Ф.", "Виктория З.", "Роман Ш.", "Елена А.",
    "Артём К.", "Светлана П.", "Никита Г.", "Татьяна В.",
    "Владимир Е.", "Ирина Х.", "Евгений Ю.", "Валерия С.",
    "Кирилл Н.", "Ксения М.", "Денис Б.", "Людмила Р.",
]

_FAKE_PRIZES = [500, 1000, 1500, 2000]

# telegram_id range for auto-generated fake winners (won't clash with seed_winners.py range)
_AUTO_TG_ID_BASE = 9_200_000


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

                    # No auto-broadcast — admin will contact winner and publish manually


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

                    # No auto-broadcast — admin will contact winner and publish manually


async def generate_fake_winner(bot: Bot) -> None:
    """Every 3 days: conduct the next scheduled mini-raffle with a fake winner,
    publish immediately and broadcast to all subscribed users."""
    async with async_session_factory() as session:
        season_repo = SeasonRepository(session)
        raffle_repo = RaffleRepository(session)
        winner_repo = WinnerRepository(session)
        user_repo = UserRepository(session)

        season = await season_repo.get_active()
        if not season:
            logger.info("generate_fake_winner: no active season, skipping.")
            return

        # Use the next scheduled mini-raffle so prize and counter stay in sync with main screen
        raffle = await raffle_repo.get_next(season.id)
        if not raffle:
            logger.info("generate_fake_winner: no pending raffles left in season.")
            return

        prize_amount = raffle.prize_amount
        name = random.choice(_FAKE_NAMES)

        # Unique fake telegram_id per run (timestamp-based, won't clash with real users)
        fake_tg_id = _AUTO_TG_ID_BASE + int(datetime.utcnow().timestamp()) % 100_000

        # Create or reuse fake user
        existing = await user_repo.get_by_telegram_id(fake_tg_id)
        if existing:
            fake_user = existing
            # Update name for variety
            from sqlalchemy import update as sa_update
            from bot.database.models import User
            await session.execute(
                sa_update(User).where(User.id == fake_user.id).values(first_name=name)
            )
        else:
            from bot.database.models import User
            fake_user = User(
                telegram_id=fake_tg_id,
                first_name=name,
                referral_code=f"auto_{uuid.uuid4().hex[:8]}",
                is_subscribed=False,
                onboarding_done=True,
                login_streak=0,
                total_wins=1,
            )
            session.add(fake_user)
            await session.flush()

        # Close the mini-raffle (marks it done so main screen advances to the next one)
        from sqlalchemy import update as sa_update
        from bot.database.models import MiniRaffle, Winner
        await session.execute(
            sa_update(MiniRaffle)
            .where(MiniRaffle.id == raffle.id)
            .values(
                winner_id=fake_user.id,
                conducted_at=datetime.utcnow(),
                status="done",
            )
        )

        # Create winner record, publish immediately
        winner = await winner_repo.create(
            user_id=fake_user.id,
            season_id=season.id,
            raffle_type="mini",
            prize=f"{prize_amount} ₽",
        )
        tz = pytz.timezone(settings.TIMEZONE)
        await session.execute(
            sa_update(Winner)
            .where(Winner.id == winner.id)
            .values(status="published", published_at=datetime.now(tz))
        )
        await session.commit()

        logger.info(f"Auto-winner generated: {name} — {prize_amount} ₽ (raffle day {raffle.day_number})")

        # Broadcast to all real subscribed users (fake user is not subscribed → skipped naturally)
        await broadcast_out_of_turn(
            bot,
            f"🎁 <b>Мини-розыгрыш завершён!</b>\n\n"
            f"Приз: <b>{prize_amount} ₽</b>\n"
            f"Победитель: <b>{name}</b>\n\n"
            f"Смотрите результаты в разделе «🏅 Победители»!",
            exclude_telegram_id=fake_tg_id,
        )


async def recheck_subscriptions(bot: Bot, checker_bot: Bot) -> None:
    """Every 6 hours: verify all 'subscribed' users are still in the sponsor channel.
    Strip access from those who left. Skipped in white mode."""
    if not sponsor_mode.is_required():
        logger.info("recheck_subscriptions: skipped (white mode active).")
        return
    async with async_session_factory() as session:
        season_repo = SeasonRepository(session)
        user_repo = UserRepository(session)

        season = await season_repo.get_active()
        if not season:
            return

        channel_id = season.sponsor_channel_id or season.sponsor_channel
        if not channel_id:
            logger.warning("recheck_subscriptions: no channel_id configured for active season.")
            return

        users = await user_repo.get_all_subscribed()
        unsubscribed_count = 0

        for user in users:
            try:
                still_subscribed = await check_subscription(checker_bot, channel_id, user.telegram_id)
            except Exception as e:
                logger.warning(f"recheck_subscriptions: error checking user {user.telegram_id}: {e}")
                continue

            if not still_subscribed:
                await user_repo.set_subscribed(user.id, False)
                unsubscribed_count += 1
                # Notify the user they lost access
                try:
                    await bot.send_message(
                        user.telegram_id,
                        "⚠️ <b>Вы отписались от канала спонсора.</b>\n\n"
                        "Ваш доступ к розыгрышу приостановлен.\n"
                        "Подпишитесь снова и нажмите «🏠 Главная» для восстановления.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

        if unsubscribed_count:
            await session.commit()
            logger.info(f"recheck_subscriptions: revoked access for {unsubscribed_count} users.")
        else:
            logger.info("recheck_subscriptions: all users still subscribed.")


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
        from bot.services.notifications import _broadcast_audience
        users = await _broadcast_audience(session)

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


def setup_scheduler(bot: Bot, checker_bot: Bot) -> AsyncIOScheduler:
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

    # Auto-generate fake winner every 3 days at 18:00 MSK (15:00 UTC)
    scheduler.add_job(
        generate_fake_winner,
        trigger=CronTrigger(day="*/3", hour=15, minute=0, timezone=pytz.utc),
        kwargs={"bot": bot},
        id="generate_fake_winner",
        replace_existing=True,
    )

    # Re-check all subscriptions every 6 hours
    scheduler.add_job(
        recheck_subscriptions,
        trigger="interval",
        hours=6,
        kwargs={"bot": bot, "checker_bot": checker_bot},
        id="recheck_subscriptions",
        replace_existing=True,
    )

    return scheduler
