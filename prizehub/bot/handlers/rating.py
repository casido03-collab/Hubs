from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories import UserRepository, SeasonRepository
from bot.keyboards import back_to_menu
from bot.services.rating import RatingService

router = Router()


@router.callback_query(F.data == "rating")
async def cb_rating(callback: CallbackQuery, session: AsyncSession):
    user_repo = UserRepository(session)
    season_repo = SeasonRepository(session)

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_subscribed:
        await callback.answer("🔒 Для участия необходимо подписаться на канал спонсора.", show_alert=True)
        return

    season = await season_repo.get_active()
    if not season:
        await callback.answer("Нет активного сезона.", show_alert=True)
        return

    rs = RatingService(session)
    ctx = await rs.get_context(user, season.id)

    rank = ctx["rank"]
    tickets = ctx["tickets"]
    prev = ctx["prev"]
    nxt = ctx["next"]
    gap = ctx["tickets_to_next"]

    lines = []

    if prev:
        lines.append(f"<b>{prev['rank']} {prev['name']} — {prev['tickets']:,}</b>")

    star = "⭐ "
    lines.append(f"{star}<b>Вы — {tickets:,}</b>  (#{rank})")

    if nxt:
        lines.append(f"<b>{nxt['rank']} {nxt['name']} — {nxt['tickets']:,}</b>")

    gap_line = f"\n⬆️ До следующего места: <b>{gap}</b> билетов" if gap is not None and gap > 0 else ""

    total = await season_repo.participants_count(season.id)
    text = (
        f"🏆 <b>Рейтинг сезона</b>\n"
        f"Участников: <b>{total:,}</b>\n\n"
        + "\n".join(lines)
        + gap_line
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=back_to_menu())
    await callback.answer()
