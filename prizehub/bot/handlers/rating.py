from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories import UserRepository, SeasonRepository
from bot.keyboards import back_to_menu
from bot.services.rating import RatingService
from bot.services import sponsor_mode

router = Router()

MEDALS = ["🥇", "🥈", "🥉"]


@router.message(F.text == "🏆 Рейтинг")
async def msg_rating(message: Message, session: AsyncSession):
    """Leaderboard — personalized for subscribed users, public top-10 for guests."""
    user_repo = UserRepository(session)
    season_repo = SeasonRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    season = await season_repo.get_active()

    if not season:
        await message.answer("🏆 <b>Рейтинг</b>\n\nСейчас нет активного сезона.", parse_mode="HTML")
        return

    total = await season_repo.participants_count(season.id)

    if sponsor_mode.user_has_access(user):
        # Personalized view
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
        lines.append(f"⭐ <b>Вы — {tickets:,}</b>  (#{rank})")
        if nxt:
            lines.append(f"<b>{nxt['rank']} {nxt['name']} — {nxt['tickets']:,}</b>")

        gap_line = f"\n⬆️ До следующего места: <b>{gap}</b> билетов" if gap else ""
        text = (
            f"🏆 <b>Рейтинг сезона</b>\n"
            f"Участников: <b>{total:,}</b>\n\n"
            + "\n".join(lines) + gap_line
        )
        await message.answer(text, parse_mode="HTML", reply_markup=back_to_menu())
    else:
        # Public top-10
        top = await season_repo.get_leaderboard(season.id, limit=10)
        if not top:
            await message.answer(
                "🏆 <b>Рейтинг сезона</b>\n\nПока нет участников. Подпишитесь на спонсора и станьте первым!",
                parse_mode="HTML",
            )
            return

        lines = [f"🏆 <b>Топ участников сезона</b>\nВсего участников: <b>{total:,}</b>\n"]
        for i, entry in enumerate(top):
            u = await user_repo.get_by_id(entry.user_id)
            name = u.first_name if u else "—"
            medal = MEDALS[i] if i < 3 else f"{i + 1}."
            lines.append(f"{medal} <b>{name}</b> — {entry.tickets:,} билетов")
        lines.append("\n🔒 Подпишитесь на канал спонсора, чтобы участвовать и попасть в рейтинг!")
        await message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data == "rating")
async def cb_rating(callback: CallbackQuery, session: AsyncSession):
    user_repo = UserRepository(session)
    season_repo = SeasonRepository(session)

    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not sponsor_mode.user_has_access(user):
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
