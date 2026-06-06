from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User
from bot.database.repositories import UserRepository

router = Router()


async def _do_reset(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)

    if user:
        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(onboarding_done=False, is_subscribed=False)
        )
        await session.commit()

    await message.answer(
        "🔄 Диалог сброшен. Начинаем знакомство заново.\n\n"
        "🎉 <b>Добро пожаловать в PrizeHub!</b>\n\n"
        "Участвуйте в розыгрышах призов и выигрывайте ценные подарки.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )

    from bot.keyboards import age_keyboard
    from bot.states import OnboardingStates
    await message.answer("Укажите ваш возраст:", reply_markup=age_keyboard())
    await state.set_state(OnboardingStates.age)


@router.message(F.text.casefold() == "сброс12")
async def reset_by_text(message: Message, state: FSMContext, session: AsyncSession):
    await _do_reset(message, state, session)


@router.message(Command("reset12"))
async def reset_by_command(message: Message, state: FSMContext, session: AsyncSession):
    await _do_reset(message, state, session)
