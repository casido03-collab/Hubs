import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from bot.config import settings
from bot.database import async_session_factory
from bot.database.models import PushLog
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

# 30 rotating texts per smart-push type
_TEXTS_NO_LOGIN = [
    "🎫 Сегодня ещё не забрали билеты! Каждый день — это шаг ближе к главному призу сезона. Заходите и получайте.",
    "⏰ День уже идёт, а ваши билеты ещё не получены. Зайдите в бота — это займёт 10 секунд.",
    "🏆 Рейтинг обновляется каждый день. Пока вы не зашли — другие уже набирают очки. Не отставайте!",
    "🎁 Ежедневный бонус ждёт вас прямо сейчас. Не дайте ему сгореть — заберите билеты сегодня.",
    "💡 Знаете, что отличает победителей? Они заходят каждый день. Сегодня ваша очередь.",
    "🏆 Главный приз сезона ближе, чем кажется — один заход в день и вы в игре. Сегодня ещё не заходили!",
    "📊 Ваши позиции в рейтинге зависят от ежедневной активности. Зайдите и укрепите своё место.",
    "🔔 Напоминаем: сегодняшние билеты ещё не получены. Каждый билет — это шанс на выигрыш.",
    "💪 Маленький шаг каждый день — большой результат в конце сезона. Заходите за билетами!",
    "🎯 До конца дня ещё есть время. Зайдите в бота и заберите свои ежедневные билеты.",
    "🌟 Активные участники выигрывают чаще. Не пропускайте ни одного дня — зайдите сейчас.",
    "📅 Ещё один день без билетов — это минус в рейтинге. Исправьте это прямо сейчас!",
    "🎰 Каждый билет увеличивает ваши шансы. Сегодня вы ещё не пополнили запас — самое время!",
    "⚡️ 30 секунд — и ваши билеты за сегодня получены. Не откладывайте, зайдите прямо сейчас.",
    "🏅 В прошлом сезоне победители заходили каждый день. Не упустите свой шанс сегодня.",
    "🎪 Розыгрыш идёт, счётчик тикает. Пополните запас билетов — вы ещё не заходили сегодня.",
    "💎 Ваши билеты — ваша сила в рейтинге. Сегодня они ещё не получены. Исправим?",
    "🔥 Серия — это мощь. Но сначала нужно зайти сегодня и забрать ежедневные билеты!",
    "👀 Участники рядом с вами в рейтинге уже зашли сегодня. Не дайте им уйти вперёд.",
    "🎊 Каждый день приносит новые билеты. Сегодняшние ещё ждут вас — зайдите и заберите.",
    "📈 Хотите подняться в рейтинге? Начните с малого — зайдите сегодня за ежедневным бонусом.",
    "🛎 Напоминание: бонус за вход сгорает в полночь. Успейте забрать свои билеты сегодня!",
    "🌙 До конца дня осталось время. Не ложитесь спать без ежедневных билетов — зайдите сейчас.",
    "🎁 Бесплатные билеты каждый день — это не просто бонус, это ваш шанс. Сегодня ещё не брали?",
    "🚀 Каждый день без входа — упущенные шансы. Наверстайте прямо сейчас, пока не поздно.",
    "💰 Билеты не копятся сами — их нужно забирать. Сегодня ваши ещё не получены.",
    "🎲 Чем больше билетов — тем выше шанс выиграть. Зайдите сегодня и добавьте в копилку.",
    "🏁 Финиш сезона не за горами. Каждый пропущенный день — это отставание. Зайдите сейчас!",
    "✨ Победа любит активных. Зайдите в бота сегодня — ваши ежедневные билеты ещё не получены.",
    "🎯 Сегодня у вас ещё есть шанс пополнить запас. Один заход — и билеты ваши. Не упустите!",
]

_TEXTS_RAFFLE_SOON = [
    "💎 Через 12 часов разыгрываем {prize} ₽! Успейте заработать больше билетов — каждый на счету.",
    "⏳ Мини-розыгрыш на {prize} ₽ совсем скоро! Зайдите, заберите бонус и увеличьте шансы.",
    "🎰 До розыгрыша {prize} ₽ остаётся всё меньше. Последний шанс пополнить запас билетов!",
    "🔔 Напоминаем: через ~12 часов разыгрываем {prize} ₽. Ваши билеты уже готовы к бою?",
    "🚨 Осталось меньше 12 часов до розыгрыша {prize} ₽! Зайдите и заберите максимум билетов.",
    "💸 {prize} ₽ скоро найдут своего победителя. Сделайте всё возможное — зайдите за билетами!",
    "🎯 Мини-розыгрыш через 12 часов. Каждый новый билет — дополнительный шанс на {prize} ₽.",
    "⚡️ Скоро розыгрыш {prize} ₽! Последние часы, чтобы увеличить свои шансы. Заходите!",
    "🏆 Победитель мини-розыгрыша получит {prize} ₽. Розыгрыш через 12 часов — вы готовы?",
    "🎁 До розыгрыша {prize} ₽ осталось ~12 часов. Успейте заработать ещё билетов прямо сейчас!",
    "🌟 {prize} ₽ скоро разыграем среди участников. Не упустите шанс — зайдите за последними билетами.",
    "📊 Смотрите рейтинг — кто займёт топ к розыгрышу {prize} ₽? Повысьте свои позиции сейчас!",
    "🔥 Горячие 12 часов перед розыгрышем {prize} ₽. Каждый билет решает — заходите!",
    "💡 Знаете как повысить шансы? Зайдите прямо сейчас — до розыгрыша {prize} ₽ ещё есть время.",
    "🎪 Ещё ~12 часов до розыгрыша {prize} ₽. Последний рывок — заберите дневной бонус!",
    "🛎 Осталось полдня до розыгрыша {prize} ₽. Убедитесь, что у вас максимум билетов.",
    "💎 Приз {prize} ₽ совсем близко — розыгрыш через ~12 часов. Не теряйте время!",
    "🚀 Финальный рывок перед розыгрышем {prize} ₽. Зайдите и добавьте билеты в копилку!",
    "⏰ Отсчёт идёт! До мини-розыгрыша {prize} ₽ меньше 12 часов. Ваши шансы в ваших руках.",
    "🎊 Уже сегодня узнаем победителя {prize} ₽! Зайдите за билетами — время ещё есть.",
    "🏅 Через ~12 часов разыгрываем {prize} ₽. Участвуете? Убедитесь, что билетов хватит!",
    "💰 {prize} ₽ достанутся одному из вас. Розыгрыш через 12 часов — успейте подготовиться.",
    "🎲 Последние часы перед розыгрышем {prize} ₽. Каждый лишний билет — лишний шанс!",
    "👀 Следите за рейтингом! До розыгрыша {prize} ₽ осталось ~12 часов — боритесь за место.",
    "✨ Розыгрыш {prize} ₽ уже сегодня! Зайдите прямо сейчас и возьмите все возможные билеты.",
    "🎯 До старта розыгрыша {prize} ₽ считанные часы. Не упустите момент пополнить запас!",
    "🌙 Сегодня разыгрываем {prize} ₽. Убедитесь, что сделали всё для победы!",
    "⚡️ {prize} ₽ ждут своего обладателя — и это можете быть вы. Розыгрыш через ~12 часов.",
    "🔮 Кто выиграет {prize} ₽? Узнаем через 12 часов. Зайдите — добавьте шансов на победу.",
    "🎰 Розыгрыш {prize} ₽ совсем скоро. Сделайте последний шаг — зайдите за билетами сейчас!",
]

_TEXTS_STREAK = [
    "🔥 Ваша серия входов под угрозой! Зайдите сегодня — не дайте ей оборваться.",
    "⚠️ Серия — это не просто цифра, это бонусные билеты. Не теряйте её — зайдите прямо сейчас!",
    "😱 Внимание! Ваша серия входов прервётся в полночь, если не зайдёте сегодня.",
    "🏃 Серия ждёт продолжения! Зайдите в бота сегодня и сохраните свою streak-награду.",
    "💪 Каждый день серии — это дополнительные бонусные билеты. Не теряйте то, что заработали!",
    "🔔 Сегодня вы ещё не продлили серию. Зайдите — это займёт секунду, а серия сохранится.",
    "⚡️ Серия входов — ваш секретный бонус. Не дайте ей сгореть сегодня ночью!",
    "📅 Каждый день на счету! Ваша серия ждёт — зайдите сегодня и продолжайте копить билеты.",
    "🎯 Серия входов приносит всё больше билетов с каждым днём. Не обнуляйте её — зайдите!",
    "🌟 Ваши ежедневные заходы = бонусные билеты. Сегодня серия под угрозой — исправьте это!",
    "😤 Не дайте серии оборваться! Зайдите в бота сегодня — вы уже вложили столько дней.",
    "🔥 Огонь серии гаснет! Зайдите и раздуйте его снова — продолжайте собирать бонусы.",
    "💎 Серия 7 дней = особый бонус. Вы близко — не останавливайтесь сейчас!",
    "⏰ До полуночи ещё есть время! Продлите серию входов и сохраните свои бонусные билеты.",
    "🏆 Победители не пропускают дни. Зайдите сегодня — сохраните серию и бонусные очки.",
    "🚨 Серия под угрозой срыва! Одна минута — и она спасена. Зайдите прямо сейчас.",
    "📈 Серия входов умножает ваши награды. Не сбрасывайте счётчик — зайдите сегодня!",
    "🎁 Чем дольше серия — тем больше билетов. Продолжайте! Зайдите сегодня и не останавливайтесь.",
    "👊 Вы уже столько дней подряд заходили — не останавливайтесь сейчас! Серия ждёт.",
    "🌙 Полночь близко, а серия ещё не продлена. Зайдите прямо сейчас — спасите streak!",
    "✨ Ваша серия — это ваше достижение. Не дайте ей обнулиться сегодня!",
    "🎰 Каждый день серии — это ещё один шанс на победу. Зайдите сегодня и держите темп.",
    "🚀 Серия входов разгоняет вашу копилку билетов. Не тормозите — зайдите сегодня!",
    "💡 Знаете, что лучший способ набрать билеты? Длинная серия. Не прерывайте её сегодня!",
    "🎪 Серия ждёт продолжения! Один заход сегодня — и вы снова в строю.",
    "🏅 Длинная серия входов — это медаль достижений. Берегите её, зайдите сегодня!",
    "😰 Не обнуляйте прогресс! Ваша серия на кону — зайдите в бота прямо сейчас.",
    "🔮 Представьте: серия 30 дней и особый бонус. Начните сейчас — не прерывайте цепочку!",
    "💰 Серия — это деньги. Каждый день продолжения = больше билетов = выше шансы. Зайдите!",
    "🎯 Сегодняшний заход стоит вам 10 секунд, но сохранит всю серию. Сделайте это прямо сейчас!",
]


async def _pick_push_text(session, user_id: int, push_type: str, texts: list) -> str:
    """Returns the next rotating text for this user and push_type (cycles every 30)."""
    from sqlalchemy import select, func
    result = await session.execute(
        select(func.count(PushLog.id)).where(
            PushLog.user_id == user_id,
            PushLog.push_type == push_type,
        )
    )
    count = result.scalar_one_or_none() or 0
    return texts[count % len(texts)]


async def send_registration_followup(bot: Bot, telegram_id: int) -> None:
    """1 hour after /start: remind user to finish onboarding (A) or subscribe (B)."""
    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        season_repo = SeasonRepository(session)

        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            return

        # Already has access → nothing to remind
        if user.is_subscribed:
            return

        # White mode → no sponsor requirement, user already has full access
        if not sponsor_mode.is_required():
            return

        if not user.onboarding_done:
            # Scenario A: didn't finish onboarding
            followup_type = "followup_onboarding"
            text = (
                "👋 Вы начали регистрацию, но не завершили.\n\n"
                "Займёт всего 30 секунд — и вы в розыгрыше!\n"
                "Нажмите /start чтобы продолжить."
            )
        else:
            # Scenario B: onboarding done but sponsor step skipped
            followup_type = "followup_subscribe"
            season = await season_repo.get_active()
            count = await season_repo.participants_count(season.id) if season else 0
            if season and season.sponsor_type == "bot":
                action = "запустить бота спонсора и нажать «✅ Я запустил»"
            else:
                action = "подписаться на канал спонсора и нажать «✅ Я подписался»"
            text = (
                f"🎁 Вы почти участвуете!\n\n"
                f"Осталось {action} — и вы в игре.\n\n"
                f"👥 Уже участвуют: <b>{count:,}</b> человек"
            )

        try:
            await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
            async with async_session_factory() as log_session:
                log_session.add(PushLog(user_id=user.id, push_type=followup_type))
                await log_session.commit()
            logger.info(f"send_registration_followup [{followup_type}]: sent to {telegram_id}")
        except Exception as e:
            logger.warning(f"send_registration_followup: failed for {telegram_id}: {e}")


async def reschedule_missed_followups(bot: Bot, scheduler: "AsyncIOScheduler") -> None:
    """On startup: re-queue followup jobs lost due to bot restart.

    Finds users registered in the last 24h who are not yet subscribed and
    never received a followup push. Sends immediately if 1h already passed,
    otherwise schedules for registration_date + 1h."""
    from apscheduler.triggers.date import DateTrigger
    from sqlalchemy import select as sa_select
    from bot.database.models import User, PushLog

    if not sponsor_mode.is_required():
        logger.info("reschedule_missed_followups: skipped (white mode active).")
        return

    async with async_session_factory() as session:
        cutoff = datetime.now(pytz.utc) - timedelta(hours=24)

        already_notified = sa_select(PushLog.user_id).where(
            PushLog.push_type.in_(["followup_onboarding", "followup_subscribe"])
        )

        result = await session.execute(
            sa_select(User).where(
                User.registration_date >= cutoff,
                User.is_subscribed == False,  # noqa: E712
                User.id.not_in(already_notified),
            )
        )
        users = result.scalars().all()

    now = datetime.now(pytz.utc)
    immediate = 0
    scheduled = 0

    for user in users:
        reg_dt = user.registration_date
        if reg_dt.tzinfo is None:
            reg_dt = pytz.utc.localize(reg_dt)

        fire_at = reg_dt + timedelta(hours=1)

        if fire_at <= now:
            # 1h already passed — send with a 3-second stagger to avoid startup flood
            run_date = now + timedelta(seconds=30 + immediate * 3)
            immediate += 1
        else:
            # Still within 1h window — fire at exact original time
            run_date = fire_at
            scheduled += 1

        scheduler.add_job(
            send_registration_followup,
            trigger=DateTrigger(run_date=run_date, timezone=pytz.utc),
            kwargs={"bot": bot, "telegram_id": user.telegram_id},
            id=f"reg_followup_{user.telegram_id}",
            replace_existing=True,
        )

    logger.info(
        f"reschedule_missed_followups: recovered {immediate} immediate + {scheduled} scheduled jobs"
        f" (total={immediate + scheduled})"
    )


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
            push_type="broadcast_raffle",
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

        if season.sponsor_type == "bot":
            logger.info("recheck_subscriptions: skipped (sponsor is a bot — trust-based, no API check).")
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
                await asyncio.sleep(0.05)  # stay well under Telegram rate limits
            except Exception as e:
                logger.warning(f"recheck_subscriptions: error checking user {user.telegram_id}: {e} — skipping (access preserved)")
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

        from bot.services.notifications import _SEND_INTERVAL
        for user in users:
            sp = await season_repo.get_participant(user.id, season.id)
            if not sp:
                continue

            # Not got tickets today
            login_needed = not user.last_login_date or (
                user.last_login_date.astimezone(tz).date() < now.date()
            )
            if login_needed:
                text = await _pick_push_text(session, user.id, "smart_no_login", _TEXTS_NO_LOGIN)
                await send_push(bot, user, text, session, push_type="smart_no_login")
                await asyncio.sleep(_SEND_INTERVAL)
                continue

            # 24h to season end
            if 22 <= hours_to_end <= 26:
                await send_push(bot, user, "⚠️ До завершения сезона осталось 24 часа! Успейте улучшить позицию.", session, push_type="smart_season_end")
                await asyncio.sleep(_SEND_INTERVAL)
                continue

            # 12h to mini raffle
            if hours_to_raffle is not None and 10 <= hours_to_raffle <= 14:
                text = (await _pick_push_text(session, user.id, "smart_raffle_soon", _TEXTS_RAFFLE_SOON)).format(prize=next_raffle.prize_amount)
                await send_push(bot, user, text, session, push_type="smart_raffle_soon")
                await asyncio.sleep(_SEND_INTERVAL)
                continue

            # Streak danger
            bonus_last = user.last_bonus_date
            if bonus_last:
                last_local = bonus_last.astimezone(tz)
                if (now.date() - last_local.date()).days >= 1:
                    text = await _pick_push_text(session, user.id, "smart_streak", _TEXTS_STREAK)
                    await send_push(bot, user, text, session, push_type="smart_streak")
                    await asyncio.sleep(_SEND_INTERVAL)
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
