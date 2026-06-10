from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import pytz
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.database.models import PushLog
from bot.handlers.admin.router import is_admin
from bot.keyboards import admin_back_keyboard
from bot.services.notifications import broadcast_out_of_turn
from bot.states import AdminPushStates

router = Router()

_PUSH_LABELS = {
    # Smart pushes
    "smart_no_login":    "🎫 Не заходил сегодня",
    "smart_season_end":  "⚠️ До конца сезона 24ч",
    "smart_raffle_soon": "💎 До мини-розыгрыша 12ч",
    "smart_streak":      "🔥 Серия под угрозой",
    # Broadcasts
    "broadcast_raffle":  "🎁 Мини-розыгрыш (авто)",
    "broadcast":         "📣 Ручная рассылка",
    # Followup
    "followup_onboarding": "👋 Followup: не завершил регистрацию",
    "followup_subscribe":  "🎁 Followup: не подписался",
    # Legacy (старые записи до обновления)
    "regular":     "📅 Умные пуши (старые)",
    "out_of_turn": "⚡️ Внеочередные (старые)",
}


def _pushes_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Статистика пушей", callback_data="admin_push_stats"))
    builder.row(InlineKeyboardButton(text="📣 Рассылка всем", callback_data="admin_push_broadcast"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu"))
    return builder.as_markup()


@router.callback_query(F.data == "admin_pushes")
async def cb_admin_pushes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    try:
        await callback.message.edit_text(
            "📣 <b>Пуш-уведомления</b>",
            parse_mode="HTML",
            reply_markup=_pushes_menu_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            "📣 <b>Пуш-уведомления</b>",
            parse_mode="HTML",
            reply_markup=_pushes_menu_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin_push_stats")
async def cb_admin_push_stats(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    today = now.date()
    yesterday = today - timedelta(days=1)

    # UTC boundaries for today and yesterday in local timezone
    today_start = tz.localize(datetime.combine(today, datetime.min.time())).astimezone(pytz.utc)
    today_end = tz.localize(datetime.combine(today + timedelta(days=1), datetime.min.time())).astimezone(pytz.utc)
    yesterday_start = tz.localize(datetime.combine(yesterday, datetime.min.time())).astimezone(pytz.utc)

    async def _query(dt_from, dt_to):
        res = await session.execute(
            select(
                PushLog.push_type,
                func.count(PushLog.id).label("total"),
                func.count(PushLog.user_id.distinct()).label("users"),
            )
            .where(PushLog.sent_at >= dt_from, PushLog.sent_at < dt_to)
            .group_by(PushLog.push_type)
            .order_by(PushLog.push_type)
        )
        return res.all()

    today_rows = await _query(today_start, today_end)
    yesterday_rows = await _query(yesterday_start, today_start)

    def _format_rows(rows) -> str:
        if not rows:
            return "  нет данных"
        lines = []
        total_users = 0
        for row in rows:
            label = _PUSH_LABELS.get(row.push_type, row.push_type)
            lines.append(f"  {label}: <b>{row.users}</b> чел. ({row.total} шт.)")
            total_users += row.users
        lines.append(f"  ──────────────")
        lines.append(f"  Итого получателей: <b>{total_users}</b>")
        return "\n".join(lines)

    text = (
        f"📊 <b>Статистика пушей</b>\n\n"
        f"📆 <b>Сегодня</b> ({today.strftime('%d.%m')}):\n"
        f"{_format_rows(today_rows)}\n\n"
        f"📅 <b>Вчера</b> ({yesterday.strftime('%d.%m')}):\n"
        f"{_format_rows(yesterday_rows)}"
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_pushes"))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_back_keyboard("admin_pushes"))
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
