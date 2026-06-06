from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.handlers.admin.router import is_admin
from bot.keyboards import admin_back_keyboard
from bot.services.notifications import broadcast_out_of_turn
from bot.states import AdminPushStates

router = Router()


@router.callback_query(F.data == "admin_pushes")
async def cb_admin_pushes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📣 Рассылка всем", callback_data="admin_push_broadcast"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu"))

    try:
        await callback.message.edit_text(
            "📣 <b>Пуш-уведомления</b>",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    except Exception:
        await callback.message.answer(
            "📣 <b>Пуш-уведомления</b>",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin_push_broadcast")
async def cb_admin_push_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    await callback.message.answer("Введите текст рассылки (поддерживается HTML):")
    await state.set_state(AdminPushStates.text)
    await callback.answer()


@router.message(AdminPushStates.text)
async def admin_push_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    text = message.text or message.caption or ""
    await message.answer("⏳ Отправляю рассылку...")
    await broadcast_out_of_turn(bot, text)
    await message.answer("✅ Рассылка отправлена всем подписанным пользователям.")
