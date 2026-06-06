from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories import WinnerRepository, UserRepository
from bot.keyboards import winners_keyboard, back_to_menu

router = Router()

PAGE_SIZE = 5


@router.callback_query(F.data == "winners")
async def cb_winners(callback: CallbackQuery, session: AsyncSession):
    await _show_winners(callback, session, page=0)


@router.callback_query(F.data.startswith("winners_page:"))
async def cb_winners_page(callback: CallbackQuery, session: AsyncSession):
    page = int(callback.data.split(":")[1])
    await _show_winners(callback, session, page=page)


async def _show_winners(callback: CallbackQuery, session: AsyncSession, page: int):
    winner_repo = WinnerRepository(session)
    user_repo = UserRepository(session)

    winners = await winner_repo.get_published(limit=PAGE_SIZE + 1, offset=page * PAGE_SIZE)
    has_next = len(winners) > PAGE_SIZE
    winners = winners[:PAGE_SIZE]
    has_prev = page > 0

    if not winners:
        try:
            await callback.message.edit_text(
                "🏅 <b>Победители</b>\n\nПока нет опубликованных победителей.",
                parse_mode="HTML",
                reply_markup=back_to_menu(),
            )
        except Exception:
            await callback.message.answer(
                "🏅 <b>Победители</b>\n\nПока нет опубликованных победителей.",
                parse_mode="HTML",
                reply_markup=back_to_menu(),
            )
        await callback.answer()
        return

    lines = ["🏅 <b>Победители</b>\n"]
    for w in winners:
        user = await user_repo.get_by_id(w.user_id)
        name = user.first_name if user else "—"
        date_str = w.published_at.strftime("%d.%m.%Y") if w.published_at else "—"
        type_icon = "💎" if w.raffle_type == "main" else "🎁"
        lines.append(f"{type_icon} <b>{name}</b> — {w.prize}\n📅 {date_str}")
        if w.description:
            lines.append(f"   {w.description}")

    text = "\n\n".join(lines)
    kb = winners_keyboard(has_prev=has_prev, has_next=has_next, page=page)

    # Send photo of last published winner if available
    last_with_photo = next((w for w in winners if w.photo_id), None)

    try:
        if last_with_photo and page == 0:
            await callback.message.answer_photo(
                photo=last_with_photo.photo_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=kb,
            )
            await callback.message.delete()
        else:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

    await callback.answer()
