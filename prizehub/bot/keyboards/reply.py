from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from bot.constants import AGE_RANGES, GENDERS, INTERESTS
from bot.services import sponsor_mode


def age_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for age in AGE_RANGES:
        builder.button(text=age)
    builder.adjust(3)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def gender_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for g in GENDERS:
        builder.button(text=g)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def interests_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for interest in INTERESTS:
        builder.button(text=interest)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent keyboard for subscribed users.

    "О розыгрыше" explains the sponsor-subscription mechanics, so it only
    makes sense (and is only shown) when sponsor mode is actually required —
    hidden in white mode."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🏠 Главная")
    builder.button(text="🎫 Заработать билеты")
    builder.button(text="🏆 Рейтинг")
    builder.button(text="🏅 Победители")
    builder.button(text="👤 Профиль")
    if sponsor_mode.is_required():
        builder.button(text="ℹ️ О розыгрыше")
        builder.adjust(1, 2, 2, 1)
    else:
        builder.adjust(1, 2, 2)
    return builder.as_markup(resize_keyboard=True)


def pre_subscribe_reply_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard shown to users who haven't subscribed yet — lets them browse open sections."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🏅 Победители")
    builder.button(text="🏆 Рейтинг")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def remove_keyboard() -> ReplyKeyboardMarkup:
    from aiogram.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()
