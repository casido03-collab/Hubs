from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories import SeasonRepository
from bot.database.repositories.raffle_repo import RaffleRepository
from bot.handlers.admin.router import is_admin
from bot.keyboards import admin_back_keyboard
import pytz
from bot.config import settings

router = Router()


@router.callback_query(F.data == "admin_raffles")
async def cb_admin_raffles(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    season_repo = SeasonRepository(session)
    raffle_repo = RaffleRepository(session)
    season = await season_repo.get_active()

    if not season:
        text = "🎯 <b>Розыгрыши</b>\n\nНет активного сезона."
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_menu"))
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_menu"))
        await callback.answer()
        return

    raffles = await raffle_repo.get_all_for_season(season.id)
    tz = pytz.timezone(settings.TIMEZONE)

    lines = [f"🎯 <b>Розыгрыши сезона #{season.number}</b>\n"]
    for r in raffles:
        dt_str = r.scheduled_at.astimezone(tz).strftime("%d.%m %H:%M") if r.scheduled_at else "—"
        status_icon = {"scheduled": "⏳", "pending_admin": "🔔", "done": "✅"}.get(r.status, "❓")
        lines.append(f"{status_icon} День {r.day_number} — {r.prize_amount} ₽ ({dt_str})")

    text = "\n".join(lines)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_menu"))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_menu"))
    await callback.answer()
