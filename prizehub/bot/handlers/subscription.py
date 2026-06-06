from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.database.repositories import UserRepository, SeasonRepository
from bot.keyboards import main_menu_keyboard, subscribe_keyboard
from bot.services.subscription import check_subscription
from bot.services.tickets import TicketService

router = Router()


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
        await user_repo.set_subscribed(user.id, True)
        ts = TicketService(session)
        tickets = await ts.award_start(user, season.id)
        rank = await season_repo.get_user_rank(user.id, season.id)

        await callback.message.edit_caption(
            caption=(
                f"🎊 <b>Поздравляем!</b>\n\n"
                f"Вы участвуете в сезоне.\n\n"
                f"🎫 Начислено: <b>{tickets}</b> стартовых билетов\n"
                f"🥇 Ваше место: <b>#{rank}</b>"
            ),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        ) if callback.message.photo else await callback.message.edit_text(
            text=(
                f"🎊 <b>Поздравляем!</b>\n\n"
                f"Вы участвуете в сезоне.\n\n"
                f"🎫 Начислено: <b>{tickets}</b> стартовых билетов\n"
                f"🥇 Ваше место: <b>#{rank}</b>"
            ),
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await callback.answer("✅ Подписка подтверждена!", show_alert=False)
        await callback.message.edit_reply_markup(reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "open_sponsor")
async def cb_open_sponsor(callback: CallbackQuery, session: AsyncSession):
    season_repo = SeasonRepository(session)
    season = await season_repo.get_active()
    if season:
        link = f"https://t.me/{season.sponsor_channel.lstrip('@')}"
        await callback.answer(url=link)
    else:
        await callback.answer("Нет активного сезона.", show_alert=True)
