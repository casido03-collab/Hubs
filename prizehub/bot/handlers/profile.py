from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories import UserRepository, SeasonRepository
from bot.keyboards import back_to_menu
from bot.services import sponsor_mode

router = Router()


async def _profile_text(session: AsyncSession, telegram_id: int) -> str | None:
    user_repo = UserRepository(session)
    season_repo = SeasonRepository(session)
    user = await user_repo.get_by_telegram_id(telegram_id)
    if not sponsor_mode.user_has_access(user):
        return None

    season = await season_repo.get_active()
    sp = None
    rank = 0
    if season:
        sp = await season_repo.get_participant(user.id, season.id)
        if sp:
            rank = await season_repo.get_user_rank(user.id, season.id)

    tickets = sp.tickets if sp else 0
    ref_count = await user_repo.count_referrals(user.id)
    reg_date = user.registration_date.strftime("%d.%m.%Y") if user.registration_date else "—"
    name_display = user.first_name
    if user.username:
        name_display += f" (@{user.username})"

    return (
        f"👤 <b>Профиль</b>\n\n"
        f"Имя: <b>{name_display}</b>\n"
        f"🎫 Билеты сезона: <b>{tickets:,}</b>\n"
        f"🥇 Место в рейтинге: <b>#{rank}</b>\n"
        f"👥 Приглашено друзей: <b>{ref_count}</b>\n"
        f"🔥 Серия входов: <b>{user.login_streak}</b> дн.\n"
        f"📅 Дата регистрации: <b>{reg_date}</b>\n"
        f"🏆 Побед: <b>{user.total_wins}</b>"
    )


@router.message(F.text == "👤 Профиль")
async def msg_profile(message: Message, session: AsyncSession):
    text = await _profile_text(session, message.from_user.id)
    if text is None:
        await message.answer("🔒 Для просмотра профиля необходимо подписаться на канал спонсора.")
        return
    await message.answer(text, parse_mode="HTML", reply_markup=back_to_menu())


@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery, session: AsyncSession):
    text = await _profile_text(session, callback.from_user.id)
    if text is None:
        await callback.answer("🔒 Для участия необходимо подписаться на канал спонсора.", show_alert=True)
        return
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_to_menu())
    await callback.answer()
