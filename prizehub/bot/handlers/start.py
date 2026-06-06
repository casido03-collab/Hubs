from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories import UserRepository, SeasonRepository
from bot.keyboards import age_keyboard, main_menu_keyboard, subscribe_keyboard
from bot.states import OnboardingStates

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    user_repo = UserRepository(session)
    season_repo = SeasonRepository(session)

    tg_user = message.from_user
    user = await user_repo.get_by_telegram_id(tg_user.id)

    # Handle referral
    referred_by = None
    args = message.text.split()
    if len(args) > 1:
        ref_code = args[1]
        referrer = await user_repo.get_by_referral_code(ref_code)
        if referrer and (user is None or referrer.id != (user.id if user else None)):
            referred_by = referrer

    if user is None:
        user = await user_repo.create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name or "Пользователь",
            referred_by_id=referred_by.id if referred_by else None,
        )
        await session.commit()

        # Award referrer if any
        if referred_by:
            season = await season_repo.get_active()
            if season:
                from bot.services.tickets import TicketService
                ts = TicketService(session)
                earned = await ts.award_referral(referred_by, season.id)
                try:
                    await bot.send_message(
                        referred_by.telegram_id,
                        f"🎉 По вашей ссылке зарегистрировался новый пользователь!\n"
                        f"🎫 Вам начислено: <b>{earned}</b> билетов",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

    if not user.onboarding_done:
        await message.answer(
            "🎉 <b>Добро пожаловать в PrizeHub!</b>\n\n"
            "Участвуйте в розыгрышах призов и выигрывайте ценные подарки.\n\n"
            "Для начала расскажите немного о себе.",
            parse_mode="HTML",
        )
        await message.answer("Укажите ваш возраст:", reply_markup=age_keyboard())
        await state.set_state(OnboardingStates.age)
    else:
        season = await season_repo.get_active()
        if not season:
            await message.answer(
                "🏠 <b>Главное меню</b>\n\nСейчас нет активного сезона.",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(),
            )
            return

        if not user.is_subscribed:
            await _show_subscribe_screen(message, season)
        else:
            await message.answer(
                "🏠 <b>Главное меню</b>\n\nДобро пожаловать обратно!",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(),
            )


async def _show_subscribe_screen(message: Message, season):
    from datetime import datetime
    import pytz
    from bot.config import settings
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    end = season.end_date.astimezone(tz) if season.end_date.tzinfo else tz.localize(season.end_date)
    days_left = max(0, (end.date() - now.date()).days)

    text = (
        f"🏆 <b>Главный приз сезона</b>\n"
        f"🚗 <b>{season.prize_name}</b>\n\n"
        f"⏳ До розыгрыша: <b>{days_left} дн.</b>\n\n"
        f"Как принять участие:\n"
        f"1️⃣ Подпишитесь на канал спонсора\n"
        f"2️⃣ Подтвердите подписку\n"
        f"3️⃣ Получайте билеты\n"
        f"4️⃣ Поднимайтесь в рейтинге\n"
        f"5️⃣ Выигрывайте призы"
    )

    sponsor_link = f"https://t.me/{season.sponsor_channel.lstrip('@')}"

    if season.prize_photo_id:
        await message.answer_photo(
            photo=season.prize_photo_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=subscribe_keyboard(sponsor_link),
        )
    else:
        await message.answer(
            text, parse_mode="HTML", reply_markup=subscribe_keyboard(sponsor_link)
        )
