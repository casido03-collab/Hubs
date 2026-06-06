from datetime import datetime
import pytz
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.database.repositories import UserRepository, SeasonRepository
from bot.keyboards import earn_tickets_keyboard, back_to_menu
from bot.services.tickets import TicketService
from bot.services import sponsor_mode

router = Router()


async def _require_subscription(callback: CallbackQuery, session: AsyncSession) -> bool:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not sponsor_mode.user_has_access(user):
        await callback.answer(
            "🔒 Для участия необходимо подписаться на канал спонсора.",
            show_alert=True,
        )
        return False
    return True


@router.message(F.text == "🎫 Заработать билеты")
async def msg_earn_tickets(message: Message, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not sponsor_mode.user_has_access(user):
        await message.answer("🔒 Для участия необходимо подписаться на канал спонсора.")
        return

    season_repo = SeasonRepository(session)
    season = await season_repo.get_active()
    sp = await season_repo.get_participant(user.id, season.id) if season else None
    tickets = sp.tickets if sp else 0

    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)

    bonus_available = True
    if user.last_bonus_date:
        last = user.last_bonus_date.astimezone(tz) if user.last_bonus_date.tzinfo else tz.localize(user.last_bonus_date)
        bonus_available = last.date() < now.date()

    login_available = True
    if user.last_login_date:
        last = user.last_login_date.astimezone(tz) if user.last_login_date.tzinfo else tz.localize(user.last_login_date)
        login_available = last.date() < now.date()

    text = (
        f"🎫 <b>Заработать билеты</b>\n\n"
        f"Ваши билеты: <b>{tickets:,}</b>\n"
        f"Серия входов: <b>{user.login_streak}</b> дн.\n\n"
        f"Выберите действие:"
    )
    await message.answer(
        text, parse_mode="HTML",
        reply_markup=earn_tickets_keyboard(bonus_available, login_available),
    )


@router.callback_query(F.data == "earn_tickets")
async def cb_earn_tickets(callback: CallbackQuery, session: AsyncSession):
    if not await _require_subscription(callback, session):
        return

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    season_repo = SeasonRepository(session)
    season = await season_repo.get_active()

    sp = await season_repo.get_participant(user.id, season.id) if season else None
    tickets = sp.tickets if sp else 0

    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)

    bonus_available = True
    if user.last_bonus_date:
        last = user.last_bonus_date.astimezone(tz) if user.last_bonus_date.tzinfo else tz.localize(user.last_bonus_date)
        bonus_available = last.date() < now.date()

    login_available = True
    if user.last_login_date:
        last = user.last_login_date.astimezone(tz) if user.last_login_date.tzinfo else tz.localize(user.last_login_date)
        login_available = last.date() < now.date()

    text = (
        f"🎫 <b>Заработать билеты</b>\n\n"
        f"Ваши билеты: <b>{tickets:,}</b>\n"
        f"Серия входов: <b>{user.login_streak}</b> дн.\n\n"
        f"Выберите действие:"
    )
    try:
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=earn_tickets_keyboard(bonus_available, login_available),
        )
    except Exception:
        await callback.message.answer(
            text, parse_mode="HTML",
            reply_markup=earn_tickets_keyboard(bonus_available, login_available),
        )
    await callback.answer()


@router.callback_query(F.data == "claim_bonus")
async def cb_claim_bonus(callback: CallbackQuery, session: AsyncSession):
    if not await _require_subscription(callback, session):
        return

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    season_repo = SeasonRepository(session)
    season = await season_repo.get_active()

    if not season:
        await callback.answer("Нет активного сезона.", show_alert=True)
        return

    ts = TicketService(session)
    amount, awarded = await ts.award_daily_bonus(user, season.id)

    if not awarded:
        await callback.answer("🎁 Бонус уже получен сегодня. Возвращайтесь завтра!", show_alert=True)
        return

    await callback.answer(f"🎁 Получено {amount} билетов!", show_alert=True)
    await cb_earn_tickets(callback, session)


@router.callback_query(F.data == "claim_login")
async def cb_claim_login(callback: CallbackQuery, session: AsyncSession):
    if not await _require_subscription(callback, session):
        return

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    season_repo = SeasonRepository(session)
    season = await season_repo.get_active()

    if not season:
        await callback.answer("Нет активного сезона.", show_alert=True)
        return

    ts = TicketService(session)
    amount, awarded = await ts.award_daily_login(user, season.id)

    if not awarded:
        await callback.answer("🔥 Вход уже отмечен сегодня!", show_alert=True)
        return

    await user_repo.update_login(user.id, user.login_streak + 1, datetime.now(pytz.timezone(settings.TIMEZONE)))
    await callback.answer(f"🔥 Ежедневный вход: +{amount} билетов!", show_alert=True)
    await cb_earn_tickets(callback, session)


@router.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery, session: AsyncSession):
    if not await _require_subscription(callback, session):
        return

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    ref_count = await user_repo.count_referrals(user.id)

    bot = callback.bot
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user.referral_code}"

    text = (
        f"👥 <b>Пригласить друга</b>\n\n"
        f"Ваша реферальная ссылка:\n{ref_link}\n\n"
        f"Приглашено: <b>{ref_count}</b> чел.\n\n"
        f"<b>Награды:</b>\n"
        f"• За каждого друга: 300–600 билетов\n"
        f"• 5 друзей: 2 000 билетов\n"
        f"• 20 друзей: 10 000 билетов"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_to_menu())
    await callback.answer()


@router.callback_query(F.data == "achievements")
async def cb_achievements(callback: CallbackQuery, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    ref_count = await user_repo.count_referrals(user.id)

    achievements = []
    if ref_count >= 1:
        achievements.append("✅ Первый реферал")
    if ref_count >= 5:
        achievements.append("✅ 5 рефералов")
    if ref_count >= 20:
        achievements.append("✅ 20 рефералов")
    if user.login_streak >= 7:
        achievements.append("✅ Серия 7 дней")
    if user.login_streak >= 30:
        achievements.append("✅ Серия 30 дней")
    if user.total_wins >= 1:
        achievements.append("✅ Первая победа")

    locked = []
    if ref_count < 1:
        locked.append("🔒 Первый реферал")
    if ref_count < 5:
        locked.append("🔒 5 рефералов")
    if ref_count < 20:
        locked.append("🔒 20 рефералов")
    if user.login_streak < 7:
        locked.append("🔒 Серия 7 дней")
    if user.login_streak < 30:
        locked.append("🔒 Серия 30 дней")
    if user.total_wins < 1:
        locked.append("🔒 Первая победа")

    lines = achievements + locked
    text = "🏅 <b>Достижения</b>\n\n" + "\n".join(lines) if lines else "🏅 <b>Достижения</b>\n\nПока пусто."
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_to_menu())
    await callback.answer()
