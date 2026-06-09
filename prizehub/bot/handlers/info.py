from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories import SeasonRepository
from bot.keyboards import back_to_menu

router = Router()

_ABOUT_BASE = (
    "ℹ️ <b>О розыгрыше PrizeHub</b>\n\n"
    "🏆 <b>Главный приз сезона</b>\n"
    "Каждый сезон длится 21 день. Победитель — участник с "
    "наибольшим числом билетов в рейтинге. Приз вручается лично "
    "после проверки.\n\n"
    "🎁 <b>Мини-розыгрыши</b>\n"
    "Каждые 3 дня — случайный розыгрыш среди всех участников. "
    "Призы: 500 ₽, 1 000 ₽, 1 500 ₽, 2 000 ₽. Чем больше у вас "
    "билетов — тем выше шанс победы.\n\n"
    "🎫 <b>Как зарабатывать билеты:</b>\n"
    "• Старт — до 600 билетов сразу\n"
    "• Ежедневный вход и бонус — до 230 билетов в день\n"
    "• Серия входов подряд — до 300 билетов\n"
    "• Пригласить друга — до 600 билетов\n"
    "• Пригласить 5 друзей — +2 000 билетов\n"
    "• Пригласить 20 друзей — +10 000 билетов\n\n"
)

_CONDITIONS_CHANNEL = (
    "📋 <b>Условия участия:</b>\n"
    "• Подпишитесь на канал спонсора\n"
    "• Оставайтесь подписаны весь сезон\n"
    "• Отписка = потеря доступа к розыгрышу"
)

_CONDITIONS_BOT = (
    "📋 <b>Условия участия:</b>\n"
    "• Запустите бота спонсора\n"
    "• Подтвердите запуск кнопкой «Я запустил»\n"
    "• Оставайтесь активны в боте спонсора"
)


async def _about_text(session: AsyncSession) -> str:
    season_repo = SeasonRepository(session)
    season = await season_repo.get_active()
    conditions = _CONDITIONS_BOT if (season and season.sponsor_type == "bot") else _CONDITIONS_CHANNEL
    return _ABOUT_BASE + conditions


@router.callback_query(F.data == "about_raffle")
async def cb_about_raffle(callback: CallbackQuery, session: AsyncSession):
    text = await _about_text(session)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_to_menu())
    await callback.answer()


@router.message(F.text == "ℹ️ О розыгрыше")
async def msg_about_raffle(message: Message, session: AsyncSession):
    text = await _about_text(session)
    await message.answer(text, parse_mode="HTML")
