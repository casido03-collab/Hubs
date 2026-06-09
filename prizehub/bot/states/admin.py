from aiogram.fsm.state import State, StatesGroup


class AdminSeasonStates(StatesGroup):
    name = State()
    prize_name = State()
    prize_photo = State()
    sponsor_type = State()       # choose channel vs bot (creation)
    sponsor_channel = State()    # enter channel username (creation)
    sponsor_bot = State()        # enter bot username (creation)
    set_channel_id = State()
    edit_sponsor_channel = State()
    edit_sponsor_type = State()  # choose channel vs bot (mid-season edit)
    edit_sponsor_bot = State()   # enter bot username (mid-season edit)

class AdminWinnerStates(StatesGroup):
    upload_photo = State()
    description = State()

class AdminPushStates(StatesGroup):
    text = State()
