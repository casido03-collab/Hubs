from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.keyboards import admin_menu_keyboard

router = Router()


def is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🔧 <b>Панель администратора</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )
