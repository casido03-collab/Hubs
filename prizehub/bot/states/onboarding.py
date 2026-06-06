from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    age = State()
    gender = State()
    interests = State()
