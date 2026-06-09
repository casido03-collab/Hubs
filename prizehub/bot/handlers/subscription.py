from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.database.repositories import UserRepository, SeasonRepository
from bot.keyboards import main_menu_keyboard, subscribe_keyboard, main_reply_keyboard
from bot.services.subscription import check_subscription
from bot.services.tickets import TicketService

router = Router()


async def _grant_access(callback: CallbackQuery, session, user_repo, season_repo, user, season):
    """Shared logic: mark subscribed, award start tickets, show congrats."""
    await user_repo.set_subscribed(user.id, True)
    ts = TicketService(session)
    tickets = await ts.award_start(user, season.id)
    rank = await season_repo.get_user_rank(user.id, season.id)

    congrats_text = (
        f"🎊 <b>Поздравляем!</b>\n\n"
        f"Вы участвуете в сезоне.\n\n"
        f"🎫 Начислено: <b>{tickets}</b> стартовых билетов\n"
        f"🥇 Ваше место: <b>#{rank}</b>"
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=congrats_text, parse_mode="HTML", reply_markup=main_menu_keyboard())
    else:
        await callback.message.edit_text(text=congrats_text, parse_mode="HTML", reply_markup=main_menu_keyboard())
    await callback.message.answer("🏠 Главное меню — выберите раздел:", reply_markup=main_reply_keyboard())


@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery, session: AsyncSession, bot: Bot, checker_bot: Bot):
    user_repo = UserRepository(session)
    season_repo = SeasonRepository(session)

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    season = await season_repo.get_active()

    if season is None:
        await callback.answer("Нет активного сезона.", show_alert=True)
        return

    channel_id = season.sponsor_channel_id or season.sponsor_channel
    subscribed = await check_subscription(checker_bot, channel_id, callback.from_user.id)

    if not subscribed:
        await callback.answer(
            "❌ Вы не подписаны на канал спонсора. Подпишитесь и попробуйте снова.",
            show_alert=True,
        )
        return

    if not user.is_subscribed:
        await _grant_access(callback, session, user_repo, season_repo, user, season)
    else:
        await callback.answer("✅ Подписка подтверждена!", show_alert=False)
        await callback.message.edit_reply_markup(reply_markup=main_menu_keyboard())
        await callback.message.answer("🏠 Главное меню — выберите раздел:", reply_markup=main_reply_keyboard())


@router.callback_query(F.data == "confirm_bot_launch")
async def cb_confirm_bot_launch(callback: CallbackQuery, session, bot: Bot):
    """'Я запустил' — trust-based access grant when sponsor_type is 'bot'."""
    user_repo = UserRepository(session)
    season_repo = SeasonRepository(session)

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    season = await season_repo.get_active()

    if season is None:
        await callback.answer("Нет активного сезона.", show_alert=True)
        return

    if not user.is_subscribed:
        await _grant_access(callback, session, user_repo, season_repo, user, season)
        await session.commit()
    else:
        await callback.answer("✅ Вы уже участвуете!", show_alert=False)
        await callback.message.edit_reply_markup(reply_markup=main_menu_keyboard())
        await callback.message.answer("🏠 Главное меню — выберите раздел:", reply_markup=main_reply_keyboard())
