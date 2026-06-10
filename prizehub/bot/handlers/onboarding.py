from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession
from bot.constants import AGE_RANGES, GENDERS, INTERESTS
from bot.database.repositories import UserRepository, SeasonRepository
from bot.keyboards import gender_keyboard, interests_keyboard, subscribe_keyboard, bot_subscribe_keyboard, main_menu_keyboard, pre_subscribe_reply_keyboard, main_reply_keyboard
from bot.services import sponsor_mode
from bot.states import OnboardingStates

router = Router()


@router.message(OnboardingStates.age)
async def process_age(message: Message, state: FSMContext):
    if message.text not in AGE_RANGES:
        await message.answer("Пожалуйста, выберите вариант из предложенных.", reply_markup=age_keyboard())
        return
    await state.update_data(age_range=message.text)
    await message.answer("Укажите пол:", reply_markup=gender_keyboard())
    await state.set_state(OnboardingStates.gender)


@router.message(OnboardingStates.gender)
async def process_gender(message: Message, state: FSMContext):
    if message.text not in GENDERS:
        await message.answer("Пожалуйста, выберите вариант из предложенных.", reply_markup=gender_keyboard())
        return
    await state.update_data(gender=message.text, interests=[])
    await message.answer("Какие призы вам интересны? (выберите несколько):", reply_markup=interests_keyboard())
    await state.set_state(OnboardingStates.interests)


@router.message(OnboardingStates.interests)
async def process_interests(message: Message, state: FSMContext, session: AsyncSession):
    if message.text not in INTERESTS:
        await message.answer("Выберите вариант из предложенных.", reply_markup=interests_keyboard())
        return

    data = await state.get_data()
    interests = [message.text]

    # Save onboarding immediately after first selection
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if user:
        await user_repo.update_onboarding(user.id, data["age_range"], data["gender"], interests)
        await session.commit()

    await state.clear()

    season_repo = SeasonRepository(session)
    season = await season_repo.get_active()

    if season is None:
        await message.answer(
            "🎉 Профиль заполнен!\n\nСейчас нет активного сезона. Заходите позже!",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # White mode: skip sponsor screen entirely
    if not sponsor_mode.is_required():
        await message.answer(
            "✅ Профиль заполнен! Добро пожаловать в PrizeHub!",
            reply_markup=main_reply_keyboard(),
        )
        return

    from bot.services.channel_utils import build_sponsor_link
    from datetime import datetime
    import pytz
    from bot.config import settings
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    end = season.end_date.astimezone(tz) if season.end_date.tzinfo else tz.localize(season.end_date)
    days_left = max(0, (end.date() - now.date()).days)
    count = await season_repo.participants_count(season.id)

    await message.answer(
        "✅ Отлично! Профиль заполнен.\n\n👇 Вы можете просмотреть доступные разделы:",
        reply_markup=pre_subscribe_reply_keyboard(),
    )

    if season.sponsor_type == "bot":
        bot_link = build_sponsor_link(season.sponsor_bot or "")
        text = (
            f"🏆 <b>Главный приз сезона</b>\n"
            f"🚗 <b>{season.prize_name}</b>\n\n"
            f"⏳ До розыгрыша: <b>{days_left} дн.</b>\n"
            f"👥 Уже участвуют: <b>{count:,}</b> чел.\n\n"
            f"Как принять участие:\n"
            f"1️⃣ Запустите бота спонсора\n"
            f"2️⃣ Подтвердите запуск\n"
            f"3️⃣ Получайте билеты\n"
            f"4️⃣ Поднимайтесь в рейтинге\n"
            f"5️⃣ Выигрывайте призы"
        )
        kb = bot_subscribe_keyboard(bot_link)
    else:
        sponsor_link = build_sponsor_link(season.sponsor_channel or "")
        text = (
            f"🏆 <b>Главный приз сезона</b>\n"
            f"🚗 <b>{season.prize_name}</b>\n\n"
            f"⏳ До розыгрыша: <b>{days_left} дн.</b>\n"
            f"👥 Уже участвуют: <b>{count:,}</b> чел.\n\n"
            f"Как принять участие:\n"
            f"1️⃣ Подпишитесь на канал спонсора\n"
            f"2️⃣ Подтвердите подписку\n"
            f"3️⃣ Получайте билеты\n"
            f"4️⃣ Поднимайтесь в рейтинге\n"
            f"5️⃣ Выигрывайте призы"
        )
        kb = subscribe_keyboard(sponsor_link)

    if season.prize_photo_id:
        await message.answer_photo(photo=season.prize_photo_id, caption=text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
