from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError


async def check_subscription(checker_bot: Bot, channel_id: int | str, user_telegram_id: int) -> bool:
    """Returns True if the user is an active member of the channel.

    Only returns False when Telegram definitively says the user is not in the
    chat (status left/kicked/banned or a "user not found" bad request).
    All other errors (rate limit, network, server, config) are re-raised so
    callers can decide to skip rather than falsely revoke access."""
    try:
        member = await checker_bot.get_chat_member(chat_id=channel_id, user_id=user_telegram_id)
        return member.status not in ("left", "kicked", "banned")
    except TelegramBadRequest as e:
        err = str(e).lower()
        # Definitively not a member — user_id invalid or confirmed not participant
        if any(k in err for k in ("user not found", "participant", "not a member")):
            return False
        raise  # e.g. "chat not found" — config issue, let caller skip
    # All other exceptions (TelegramForbiddenError, TelegramRetryAfter,
    # TelegramServerError, network errors, etc.) propagate to the caller.


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
