from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User, SeasonParticipant
from bot.database.repositories import UserRepository, SeasonRepository, TicketRepository
from bot.handlers.admin.router import is_admin
from bot.keyboards import admin_back_keyboard

router = Router()


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    user_repo = UserRepository(session)
    season_repo = SeasonRepository(session)

    total_users = await user_repo.total_count()
    new_today = await user_repo.count_registered_today()

    # Active today (logged in today)
    today = datetime.utcnow().date()
    result = await session.execute(
        select(func.count()).where(func.date(User.last_login_date) == today)
    )
    active_today = result.scalar_one()

    season = await season_repo.get_active()
    season_info = f"#{season.number} — {season.prize_name}" if season else "нет"
    participants = await season_repo.participants_count(season.id) if season else 0

    subscribed_result = await session.execute(
        select(func.count()).where(User.is_subscribed == True)
    )
    subscribed = subscribed_result.scalar_one()
    conversion = f"{subscribed / total_users * 100:.1f}%" if total_users > 0 else "0%"

    # Ticket stats
    ticket_total = 0
    if season:
        ticket_repo = TicketRepository(session)
        ticket_total = await ticket_repo.total_earned(season.id)

    # Referral count
    ref_result = await session.execute(
        select(func.count()).where(User.referred_by_id != None)
    )
    ref_total = ref_result.scalar_one()

    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users:,}</b>\n"
        f"🟢 Активных сегодня: <b>{active_today:,}</b>\n"
        f"🆕 Новых за сутки: <b>{new_today:,}</b>\n\n"
        f"🏆 Активный сезон: <b>{season_info}</b>\n"
        f"🎯 Участников сезона: <b>{participants:,}</b>\n"
        f"📢 Подписаны на спонсора: <b>{subscribed:,}</b>\n"
        f"📈 Конверсия в подписку: <b>{conversion}</b>\n\n"
        f"🎫 Билетов выдано в сезоне: <b>{ticket_total:,}</b>\n"
        f"👥 Всего рефералов: <b>{ref_total:,}</b>"
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_menu"))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_menu"))
    await callback.answer()


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    from bot.keyboards import admin_menu_keyboard
    try:
        await callback.message.edit_text("🔧 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=admin_menu_keyboard())
    except Exception:
        await callback.message.answer("🔧 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=admin_menu_keyboard())
    await callback.answer()
