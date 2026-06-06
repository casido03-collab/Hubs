from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User
from bot.database.repositories import UserRepository
from bot.handlers.admin.router import is_admin
from bot.keyboards import admin_back_keyboard

router = Router()


@router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    user_repo = UserRepository(session)
    total = await user_repo.total_count()
    new_today = await user_repo.count_registered_today()
    all_users = await user_repo.get_all_subscribed()

    text = (
        f"👥 <b>Пользователи</b>\n\n"
        f"Всего: <b>{total:,}</b>\n"
        f"Новых сегодня: <b>{new_today:,}</b>\n"
        f"Подписаны на спонсора: <b>{len(all_users):,}</b>"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_menu"))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_menu"))
    await callback.answer()
