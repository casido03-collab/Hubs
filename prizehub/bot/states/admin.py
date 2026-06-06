from aiogram.fsm.state import State, StatesGroup


class AdminSeasonStates(StatesGroup):
    name = State()
    prize_name = State()
    prize_photo = State()
    sponsor_channel = State()

class AdminWinnerStates(StatesGroup):
    upload_photo = State()
    description = State()

class AdminPushStates(StatesGroup):
    text = State()
