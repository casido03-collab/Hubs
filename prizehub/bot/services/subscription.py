from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError


async def check_subscription(checker_bot: Bot, channel_id: int | str, user_telegram_id: int) -> bool:
    try:
        member = await checker_bot.get_chat_member(chat_id=channel_id, user_id=user_telegram_id)
        return member.status not in ("left", "kicked", "banned")
    except (TelegramBadRequest, TelegramForbiddenError):
        return False
    except Exception:
        return False


async def verify_checker_bot_in_channel(checker_bot: Bot, channel: str) -> tuple[bool, int | None]:
    """Returns (success, channel_id). Verifies checker bot is admin in channel."""
    try:
        chat = await checker_bot.get_chat(channel)
        bot_info = await checker_bot.get_me()
        member = await checker_bot.get_chat_member(chat_id=chat.id, user_id=bot_info.id)
        is_admin = member.status in ("administrator", "creator")
        return is_admin, chat.id
    except Exception:
        return False, None
