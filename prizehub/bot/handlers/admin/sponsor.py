from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.handlers.admin.router import is_admin
from bot.services import sponsor_mode

router = Router()


@router.message(Command("sponsor"))
async def cmd_sponsor_toggle(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    new_value = await sponsor_mode.toggle(session)

    if new_value:
        # Sponsor ON — normal mode
        await message.answer(
            "✅ <b>Режим спонсора ВКЛЮЧЁН</b>\n\n"
            "Для участия в розыгрыше требуется подписка на канал спонсора.\n\n"
            "Повторите /sponsor чтобы переключить в белый режим.",
            parse_mode="HTML",
        )
    else:
        # Sponsor OFF — white mode
        await message.answer(
            "⚪ <b>Белый режим ВКЛЮЧЁН</b>\n\n"
            "Подписка на канал спонсора <b>не требуется</b>.\n"
            "Все пользователи получают доступ просто заходя в бота.\n\n"
            "Повторите /sponsor чтобы вернуть обязательную подписку.",
            parse_mode="HTML",
        )
