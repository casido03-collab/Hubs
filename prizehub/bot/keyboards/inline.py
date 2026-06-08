from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def subscribe_keyboard(sponsor_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Подписаться на спонсора", url=sponsor_link))
    builder.row(InlineKeyboardButton(text="ℹ️ Как участвовать", callback_data="about_raffle"))
    builder.row(InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription"))
    return builder.as_markup()


def check_subscription_keyboard(sponsor_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 Подписаться", url=sponsor_link))
    builder.row(InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription"))
    return builder.as_markup()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Главная", callback_data="home"))
    builder.row(
        InlineKeyboardButton(text="🎫 Заработать билеты", callback_data="earn_tickets"),
        InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating"),
    )
    builder.row(
        InlineKeyboardButton(text="🏅 Победители", callback_data="winners"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
    )
    return builder.as_markup()


def home_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎫 Заработать билеты", callback_data="earn_tickets"),
        InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Меню", callback_data="menu"))
    return builder.as_markup()


def earn_tickets_keyboard(bonus_available: bool, login_available: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    bonus_label = "🎁 Ежедневный бонус" if bonus_available else "🎁 Бонус (уже получен)"
    login_label = "🔥 Серия входов" if login_available else "🔥 Вход (уже отмечен)"
    builder.row(InlineKeyboardButton(text=bonus_label, callback_data="claim_bonus"))
    builder.row(InlineKeyboardButton(text=login_label, callback_data="claim_login"))
    builder.row(InlineKeyboardButton(text="👥 Пригласить друга", callback_data="referral"))
    builder.row(InlineKeyboardButton(text="🏅 Достижения", callback_data="achievements"))
    builder.row(InlineKeyboardButton(text="◀️ Меню", callback_data="menu"))
    return builder.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Меню", callback_data="menu"))
    return builder.as_markup()


def winners_keyboard(has_prev: bool = False, has_next: bool = False, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"winners_page:{page-1}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"winners_page:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="◀️ Меню", callback_data="menu"))
    return builder.as_markup()


# Admin keyboards
def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.row(
        InlineKeyboardButton(text="🏆 Сезоны", callback_data="admin_seasons"),
        InlineKeyboardButton(text="🎯 Розыгрыши", callback_data="admin_raffles"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
        InlineKeyboardButton(text="🏅 Победители", callback_data="admin_winners"),
    )
    builder.row(InlineKeyboardButton(text="📣 Пуши", callback_data="admin_pushes"))
    return builder.as_markup()


def admin_season_actions_keyboard(season_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not is_active:
        builder.row(InlineKeyboardButton(text="▶️ Активировать", callback_data=f"admin_season_activate:{season_id}"))
    builder.row(InlineKeyboardButton(text="✏️ Изменить канал спонсора", callback_data=f"admin_season_editchannel:{season_id}"))
    builder.row(InlineKeyboardButton(text="🔗 Указать ID канала", callback_data=f"admin_season_setchannel:{season_id}"))
    builder.row(InlineKeyboardButton(text="🔄 Перепроверить бота в канале", callback_data=f"admin_season_recheck:{season_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_seasons"))
    return builder.as_markup()


def admin_winner_actions_keyboard(winner_id: int, status: str = "pending") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "published":
        builder.row(InlineKeyboardButton(text="📷 Обновить фото", callback_data=f"admin_winner_updatephoto:{winner_id}"))
        builder.row(InlineKeyboardButton(text="📝 Обновить описание", callback_data=f"admin_winner_updatedesc:{winner_id}"))
    else:
        builder.row(InlineKeyboardButton(text="🖼 Загрузить фото", callback_data=f"admin_winner_photo:{winner_id}"))
        builder.row(InlineKeyboardButton(text="📢 Опубликовать без фото", callback_data=f"admin_winner_publish:{winner_id}"))
        builder.row(InlineKeyboardButton(text="🔄 Перевыбрать победителя", callback_data=f"admin_winner_reroll:{winner_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_winners"))
    return builder.as_markup()


def admin_back_keyboard(target: str = "admin_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=target))
    return builder.as_markup()
