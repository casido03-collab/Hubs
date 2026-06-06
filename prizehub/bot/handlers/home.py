from datetime import datetime
import pytz
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.database.repositories import UserRepository, SeasonRepository
from bot.database.repositories.raffle_repo import RaffleRepository
from bot.keyboards import home_keyboard, main_menu_keyboard, subscribe_keyboard, check_subscription_keyboard

router = Router()


async def _home_text(session: AsyncSession, telegram_id: int) -> tuple[str, str | None, object]:
    user_repo = UserRepository(session)
    season_repo = SeasonRepository(session)

    user = await user_repo.get_by_telegram_id(telegram_id)
    season = await season_repo.get_active()

    if season is None:
        return "🏠 <b>Главное меню</b>\n\nСейчас нет активного сезона.", None, main_menu_keyboard()

    if not user or not user.is_subscribed:
        from bot.services.channel_utils import build_sponsor_link
        sponsor_link = build_sponsor_link(season.sponsor_channel)
        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
        end = season.end_date.astimezone(tz) if season.end_date.tzinfo else tz.localize(season.end_date)
        days_left = max(0, (end.date() - now.date()).days)
        count = await season_repo.participants_count(season.id)
        text = (
            f"🏆 <b>Главный приз сезона</b>\n"
            f"🚗 <b>{season.prize_name}</b>\n\n"
            f"⏳ До розыгрыша: <b>{days_left} дн.</b>\n"
            f"👥 Уже участвуют: <b>{count:,}</b> чел.\n\n"
            f"⚠️ Для участия необходимо подписаться на канал спонсора."
        )
        return text, season.prize_photo_id, check_subscription_keyboard()

    sp = await season_repo.get_participant(user.id, season.id)
    tickets = sp.tickets if sp else 0
    rank = await season_repo.get_user_rank(user.id, season.id)

    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    end = season.end_date.astimezone(tz) if season.end_date.tzinfo else tz.localize(season.end_date)
    days_left = max(0, (end.date() - now.date()).days)

    raffle_repo = RaffleRepository(session)
    next_raffle = await raffle_repo.get_next(season.id)

    raffle_info = ""
    if next_raffle:
        raffle_dt = next_raffle.scheduled_at.astimezone(tz) if next_raffle.scheduled_at.tzinfo else tz.localize(next_raffle.scheduled_at)
        delta = raffle_dt - now
        if delta.total_seconds() > 0:
            total_secs = int(delta.total_seconds())
            days_r = total_secs // 86400
            hours_r = (total_secs % 86400) // 3600
            raffle_info = (
                f"\n\n💎 <b>Следующий мини-розыгрыш</b>\n"
                f"Приз: <b>{next_raffle.prize_amount} ₽</b>\n"
                f"Через: <b>{days_r} дн. {hours_r} ч.</b>"
            )

    # Next rank gap
    board = await season_repo.get_leaderboard(season.id, limit=200)
    rank_gap = ""
    for i, entry in enumerate(board):
        if entry.user_id == user.id and i > 0:
            diff = board[i - 1].tickets - entry.tickets
            if diff > 0:
                rank_gap = f"\n⬆️ До следующего места: <b>{diff}</b> билетов"
            break

    text = (
        f"🏆 <b>Главный приз сезона</b>\n"
        f"🚗 <b>{season.prize_name}</b>\n\n"
        f"⏳ До розыгрыша: <b>{days_left} дн.</b>\n"
        f"🎫 Ваши билеты: <b>{tickets:,}</b>\n"
        f"🥇 Ваше место: <b>#{rank}</b>"
        f"{rank_gap}"
        f"{raffle_info}"
    )
    return text, season.prize_photo_id, home_keyboard()


@router.callback_query(F.data == "home")
async def cb_home(callback: CallbackQuery, session: AsyncSession):
    text, photo_id, kb = await _home_text(session, callback.from_user.id)
    if photo_id:
        try:
            await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await callback.message.answer_photo(photo=photo_id, caption=text, parse_mode="HTML", reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if not user or not user.is_subscribed:
        await callback.message.answer("🏠 <b>Главное меню</b>", parse_mode="HTML", reply_markup=check_subscription_keyboard())
    else:
        await callback.message.answer("🏠 <b>Главное меню</b>", parse_mode="HTML", reply_markup=main_menu_keyboard())
    await callback.answer()
