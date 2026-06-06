from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories import WinnerRepository, UserRepository
from bot.handlers.admin.router import is_admin
from bot.keyboards import admin_winner_actions_keyboard, admin_back_keyboard
from bot.services.notifications import broadcast_out_of_turn
from bot.states import AdminWinnerStates

router = Router()


@router.callback_query(F.data == "admin_winners")
async def cb_admin_winners(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    winner_repo = WinnerRepository(session)
    winners = await winner_repo.get_all(limit=20)
    user_repo = UserRepository(session)

    if not winners:
        text = "🏅 <b>Победители</b>\n\nПока нет победителей."
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_menu"))
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_menu"))
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()

    lines = ["🏅 <b>Победители</b>\n"]
    for w in winners:
        user = await user_repo.get_by_id(w.user_id)
        name = user.first_name if user else "—"
        status_icon = "✅" if w.status == "published" else "⏳"
        photo_icon = "🖼" if w.photo_id else ""
        type_icon = "💎" if w.raffle_type == "main" else "🎁"
        lines.append(f"{status_icon} {type_icon} {photo_icon} {name} — {w.prize}".strip())
        # ALL winners are clickable (published ones can get photo/desc updated)
        builder.row(InlineKeyboardButton(
            text=f"{'⚙️' if w.status == 'pending' else '✏️'} {name} — {w.prize}",
            callback_data=f"admin_winner:{w.id}",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu"))
    text = "\n".join(lines)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_winner:"))
async def cb_admin_winner_detail(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    winner_id = int(callback.data.split(":")[1])
    winner_repo = WinnerRepository(session)
    user_repo = UserRepository(session)

    winner = await winner_repo.get_by_id(winner_id)
    if not winner:
        await callback.answer("Победитель не найден.", show_alert=True)
        return

    user = await user_repo.get_by_id(winner.user_id)

    text = (
        f"🏆 <b>Определён победитель</b>\n\n"
        f"Приз: <b>{winner.prize}</b>\n"
        f"Имя: <b>{user.first_name if user else '—'}</b>\n"
        f"Username: @{user.username or '—'}\n"
        f"Telegram ID: <code>{user.telegram_id if user else '—'}</code>"
    )

    try:
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=admin_winner_actions_keyboard(winner_id, winner.status),
        )
    except Exception:
        await callback.message.answer(
            text, parse_mode="HTML",
            reply_markup=admin_winner_actions_keyboard(winner_id, winner.status),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_winner_photo:"))
async def cb_admin_winner_photo_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    winner_id = int(callback.data.split(":")[1])
    await state.update_data(winner_id=winner_id)
    await callback.message.answer("Отправьте фотографию для победителя:")
    await state.set_state(AdminWinnerStates.upload_photo)
    await callback.answer()


@router.message(AdminWinnerStates.upload_photo)
async def admin_winner_photo_upload(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.photo:
        await message.answer("Пожалуйста, отправьте фотографию.")
        return
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer("Введите описание (или «-» чтобы пропустить):")
    await state.set_state(AdminWinnerStates.description)


@router.message(AdminWinnerStates.description)
async def admin_winner_description(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    await state.clear()

    raw = message.text.strip() if message.text else "-"
    description = None if raw == "-" else raw
    photo_id = data.get("photo_id")
    winner_id = data["winner_id"]
    is_update = data.get("is_update", False)

    winner_repo = WinnerRepository(session)
    user_repo = UserRepository(session)

    if is_update:
        # Only update photo/description, keep status=published, no broadcast
        await winner_repo.update_photo(winner_id, photo_id, description)
        await session.commit()
        await message.answer("✅ Данные победителя обновлены!")
    else:
        # First-time publish: set status, broadcast to all users
        await winner_repo.publish(winner_id, photo_id, description)
        await session.commit()

        winner = await winner_repo.get_by_id(winner_id)
        user = await user_repo.get_by_id(winner.user_id)

        await message.answer("✅ Победитель опубликован!")

        await broadcast_out_of_turn(
            bot,
            f"🏆 <b>Опубликован новый победитель!</b>\n\n"
            f"{'💎' if winner.raffle_type == 'main' else '🎁'} Приз: <b>{winner.prize}</b>\n"
            f"👤 Победитель: <b>{user.first_name if user else '—'}</b>\n\n"
            f"Смотрите раздел «Победители»!",
        )


@router.callback_query(F.data.startswith("admin_winner_publish:"))
async def cb_admin_winner_publish_no_photo(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    winner_id = int(callback.data.split(":")[1])
    winner_repo = WinnerRepository(session)
    user_repo = UserRepository(session)

    await winner_repo.publish(winner_id, None, None)
    await session.commit()

    winner = await winner_repo.get_by_id(winner_id)
    user = await user_repo.get_by_id(winner.user_id)
    await callback.answer("✅ Опубликовано!", show_alert=True)

    await broadcast_out_of_turn(
        bot,
        f"🏆 <b>Опубликован новый победитель!</b>\n\n"
        f"{'💎' if winner.raffle_type == 'main' else '🎁'} Приз: <b>{winner.prize}</b>\n"
        f"👤 Победитель: <b>{user.first_name if user else '—'}</b>",
    )


@router.callback_query(F.data.startswith("admin_winner_reroll:"))
async def cb_admin_winner_reroll(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    winner_id = int(callback.data.split(":")[1])
    winner_repo = WinnerRepository(session)
    winner = await winner_repo.get_by_id(winner_id)
    if not winner:
        await callback.answer("Не найдено.", show_alert=True)
        return

    from bot.database.repositories import SeasonRepository
    from bot.services.raffle import RaffleService
    season_repo = SeasonRepository(session)
    season = await season_repo.get_by_id(winner.season_id)

    raffle_service = RaffleService(session)
    new_winner_id, name = await raffle_service.conduct_main_raffle(season) \
        if winner.raffle_type == "main" \
        else (None, None)

    if new_winner_id:
        await callback.answer(f"✅ Перевыбран: {name}", show_alert=True)
    else:
        await callback.answer("Не удалось перевыбрать победителя.", show_alert=True)


# ── Update photo for already-published winners ──────────────────────────────

@router.callback_query(F.data.startswith("admin_winner_updatephoto:"))
async def cb_admin_winner_updatephoto_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    winner_id = int(callback.data.split(":")[1])
    await state.update_data(winner_id=winner_id, is_update=True)
    await callback.message.answer("Отправьте новую фотографию для победителя:")
    await state.set_state(AdminWinnerStates.upload_photo)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_winner_updatedesc:"))
async def cb_admin_winner_updatedesc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    winner_id = int(callback.data.split(":")[1])
    await state.update_data(winner_id=winner_id, is_update=True, photo_id=None, skip_photo=True)
    await callback.message.answer("Введите новое описание для победителя (или «-» чтобы очистить):")
    await state.set_state(AdminWinnerStates.description)
    await callback.answer()
