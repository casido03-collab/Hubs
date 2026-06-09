from datetime import datetime, timedelta
import pytz
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.database.repositories import SeasonRepository
from bot.handlers.admin.router import is_admin
from bot.keyboards import admin_back_keyboard, admin_season_actions_keyboard, admin_menu_keyboard
from bot.services.subscription import verify_checker_bot_in_channel
from bot.services.raffle import RaffleService
from bot.states import AdminSeasonStates
from bot.constants import SEASON_DURATION_DAYS

router = Router()


@router.callback_query(F.data == "admin_seasons")
async def cb_admin_seasons(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    season_repo = SeasonRepository(session)
    seasons = await season_repo.get_all()

    if not seasons:
        text = "🏆 <b>Сезоны</b>\n\nСезонов пока нет."
    else:
        lines = ["🏆 <b>Сезоны</b>\n"]
        for s in seasons:
            status_icon = "🟢" if s.is_active else ("⚪" if s.status == "pending" else "🔴")
            lines.append(f"{status_icon} <b>#{s.number}</b> {s.name} — {s.prize_name}")
        text = "\n".join(lines)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    for s in (seasons or []):
        builder.row(InlineKeyboardButton(text=f"#{s.number} {s.name}", callback_data=f"admin_season:{s.id}"))
    builder.row(InlineKeyboardButton(text="➕ Создать сезон", callback_data="admin_season_create"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu"))

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_season:"))
async def cb_admin_season_detail(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    season_id = int(callback.data.split(":")[1])
    season_repo = SeasonRepository(session)
    season = await season_repo.get_by_id(season_id)
    if not season:
        await callback.answer("Сезон не найден.", show_alert=True)
        return

    tz = pytz.timezone(settings.TIMEZONE)
    start_str = season.start_date.astimezone(tz).strftime("%d.%m.%Y") if season.start_date else "—"
    end_str = season.end_date.astimezone(tz).strftime("%d.%m.%Y") if season.end_date else "—"

    if season.sponsor_type == "bot":
        sponsor_str = f"🤖 Бот: {season.sponsor_bot or '—'}"
    else:
        sponsor_str = f"📺 Канал: {season.sponsor_channel or '—'}"

    text = (
        f"🏆 <b>Сезон #{season.number}</b>\n\n"
        f"Название: {season.name}\n"
        f"Приз: {season.prize_name}\n"
        f"Спонсор: {sponsor_str}\n"
        f"Начало: {start_str}\n"
        f"Конец: {end_str}\n"
        f"Статус: {season.status}"
    )

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=admin_season_actions_keyboard(season_id, season.is_active, season.sponsor_type),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_season_create")
async def cb_admin_season_create_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    await callback.message.answer("Введите <b>название сезона</b>:", parse_mode="HTML")
    await state.set_state(AdminSeasonStates.name)
    await callback.answer()


@router.message(AdminSeasonStates.name)
async def admin_season_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await message.answer("Введите <b>название главного приза</b> (например: BMW X6):", parse_mode="HTML")
    await state.set_state(AdminSeasonStates.prize_name)


@router.message(AdminSeasonStates.prize_name)
async def admin_season_prize_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(prize_name=message.text.strip())
    await message.answer("Отправьте <b>фотографию главного приза</b> (или напишите «-» чтобы пропустить):", parse_mode="HTML")
    await state.set_state(AdminSeasonStates.prize_photo)


@router.message(AdminSeasonStates.prize_photo)
async def admin_season_prize_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.text and message.text.strip() != "-":
        await message.answer("Отправьте фото или напишите «-».")
        return
    await state.update_data(prize_photo_id=photo_id)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📺 Канал", callback_data="season_type:channel"),
        InlineKeyboardButton(text="🤖 Бот", callback_data="season_type:bot"),
    )
    await message.answer(
        "Выберите <b>тип спонсора</b>:",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(AdminSeasonStates.sponsor_type)


@router.callback_query(F.data.startswith("season_type:"), AdminSeasonStates.sponsor_type)
async def admin_season_choose_type(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    chosen = callback.data.split(":")[1]
    await state.update_data(sponsor_type=chosen)
    if chosen == "channel":
        await callback.message.answer(
            "Введите <b>ссылку или @username канала спонсора</b> (например: @mychannel):",
            parse_mode="HTML",
        )
        await state.set_state(AdminSeasonStates.sponsor_channel)
    else:
        await callback.message.answer(
            "Введите <b>@username бота-спонсора</b> (например: @InvestBot):",
            parse_mode="HTML",
        )
        await state.set_state(AdminSeasonStates.sponsor_bot)
    await callback.answer()


@router.message(AdminSeasonStates.sponsor_channel)
async def admin_season_sponsor(message: Message, state: FSMContext, session: AsyncSession, checker_bot: Bot):
    if not is_admin(message.from_user.id):
        return
    channel = message.text.strip()
    data = await state.get_data()
    await state.clear()

    season_repo = SeasonRepository(session)
    number = await season_repo.next_number()

    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)

    season = await season_repo.create(
        number=number,
        name=data["name"],
        prize_name=data["prize_name"],
        prize_photo_id=data.get("prize_photo_id"),
        sponsor_type="channel",
        sponsor_channel=channel,
        start_date=now,
        end_date=now + timedelta(days=SEASON_DURATION_DAYS),
    )
    await session.commit()

    await message.answer(
        f"✅ Сезон <b>#{number}</b> создан!\n\n"
        f"Теперь добавьте <b>@Invest_reinvest_bot</b> администратором в канал {channel}.\n"
        f"После добавления будет выполнена автоматическая проверка.\n\n"
        f"Проверяю доступ...",
        parse_mode="HTML",
    )

    ok, channel_id = await verify_checker_bot_in_channel(checker_bot, channel)
    if ok and channel_id:
        await season_repo.set_sponsor_channel_id(season.id, channel_id)
        await session.commit()
        await message.answer(
            f"✅ Проверочный бот добавлен в канал и имеет права администратора.\n\n"
            f"Активируйте сезон в /admin → Сезоны → #{number}",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await message.answer(
            f"⚠️ @Invest_reinvest_bot не найден в канале или не является администратором.\n"
            f"Добавьте его и проверьте через детали сезона.",
            reply_markup=admin_menu_keyboard(),
        )


@router.message(AdminSeasonStates.sponsor_bot)
async def admin_season_sponsor_bot(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    bot_username = message.text.strip()
    if not bot_username.startswith("@"):
        bot_username = "@" + bot_username
    data = await state.get_data()
    await state.clear()

    season_repo = SeasonRepository(session)
    number = await season_repo.next_number()

    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)

    await season_repo.create(
        number=number,
        name=data["name"],
        prize_name=data["prize_name"],
        prize_photo_id=data.get("prize_photo_id"),
        sponsor_type="bot",
        sponsor_bot=bot_username,
        start_date=now,
        end_date=now + timedelta(days=SEASON_DURATION_DAYS),
    )
    await session.commit()

    await message.answer(
        f"✅ Сезон <b>#{number}</b> создан со спонсором-ботом {bot_username}!\n\n"
        f"Участие на доверии — пользователи нажимают «Я запустил» без проверки.\n\n"
        f"Активируйте сезон в /admin → Сезоны → #{number}",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("admin_season_editchannel:"))
async def cb_admin_season_editchannel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    season_id = int(callback.data.split(":")[1])
    await state.update_data(season_id=season_id)
    await callback.message.answer(
        "Введите новую <b>ссылку или @username канала спонсора</b>\n"
        "Примеры:\n"
        "• <code>@mychannel</code>\n"
        "• <code>https://t.me/+C9qj4yn2NX43YzUy</code> (приватный канал)\n\n"
        "⚠️ После смены канала потребуется повторная проверка бота.",
        parse_mode="HTML",
    )
    await state.set_state(AdminSeasonStates.edit_sponsor_channel)
    await callback.answer()


@router.message(AdminSeasonStates.edit_sponsor_channel)
async def admin_season_save_editchannel(message: Message, state: FSMContext, session: AsyncSession, checker_bot: Bot):
    if not is_admin(message.from_user.id):
        return
    channel = message.text.strip() if message.text else ""
    if not channel:
        await message.answer("❌ Введите ссылку или @username канала.")
        return

    data = await state.get_data()
    season_id = data["season_id"]
    await state.clear()

    season_repo = SeasonRepository(session)
    # Save new channel, reset numeric ID so it gets re-verified
    await season_repo.update_sponsor_channel(season_id, channel)
    await session.commit()

    await message.answer(
        f"✅ Канал спонсора обновлён: <code>{channel}</code>\n\n"
        f"Проверяю доступ бота в канале...",
        parse_mode="HTML",
    )

    ok, channel_id = await verify_checker_bot_in_channel(checker_bot, channel)
    if ok and channel_id:
        await season_repo.set_sponsor_channel_id(season_id, channel_id)
        await session.commit()
        await message.answer(
            "✅ Бот подтверждён в новом канале!\n\n"
            "Канал спонсора успешно обновлён.",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await message.answer(
            "⚠️ Канал сохранён, но бот не подтверждён.\n\n"
            "Если канал приватный — добавьте @Invest_reinvest_bot администратором, "
            "затем используйте «🔗 Указать ID канала» или «🔄 Перепроверить».",
            reply_markup=admin_menu_keyboard(),
        )


@router.callback_query(F.data.startswith("admin_season_recheck:"))
async def cb_admin_season_recheck(callback: CallbackQuery, session: AsyncSession, checker_bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    season_id = int(callback.data.split(":")[1])
    season_repo = SeasonRepository(session)
    season = await season_repo.get_by_id(season_id)
    if not season:
        await callback.answer("Сезон не найден.", show_alert=True)
        return

    channel = season.sponsor_channel_id or season.sponsor_channel
    await callback.answer("⏳ Проверяю...", show_alert=False)

    ok, channel_id = await verify_checker_bot_in_channel(checker_bot, channel)
    if ok and channel_id:
        await season_repo.set_sponsor_channel_id(season.id, channel_id)
        await session.commit()
        await callback.message.answer(
            f"✅ Бот найден в канале! ID канала сохранён: <code>{channel_id}</code>\n\n"
            f"Теперь можно активировать сезон.",
            parse_mode="HTML",
        )
    else:
        await callback.message.answer(
            f"❌ Бот не найден в канале или не является администратором.\n\n"
            f"Если канал приватный — используйте кнопку «🔗 Указать ID канала» и введите числовой ID.\n"
            f"Получить ID: перешлите сообщение из канала боту @userinfobot",
        )


@router.callback_query(F.data.startswith("admin_season_setchannel:"))
async def cb_admin_season_setchannel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    season_id = int(callback.data.split(":")[1])
    await state.update_data(season_id=season_id)
    await callback.message.answer(
        "Введите числовой <b>ID канала</b> (например: <code>-1001234567890</code>)\n\n"
        "Получить ID: перешлите любое сообщение из канала боту @userinfobot",
        parse_mode="HTML",
    )
    await state.set_state(AdminSeasonStates.set_channel_id)
    await callback.answer()


@router.message(AdminSeasonStates.set_channel_id)
async def admin_season_set_channel_id(message: Message, state: FSMContext, session: AsyncSession, checker_bot: Bot):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip() if message.text else ""
    try:
        channel_id = int(text)
    except ValueError:
        await message.answer("❌ Введите числовой ID, например: <code>-1001234567890</code>", parse_mode="HTML")
        return

    data = await state.get_data()
    season_id = data["season_id"]
    await state.clear()

    season_repo = SeasonRepository(session)
    await season_repo.set_sponsor_channel_id(season_id, channel_id)
    await session.commit()

    # Recheck with new ID
    ok, verified_id = await verify_checker_bot_in_channel(checker_bot, channel_id)
    if ok:
        await message.answer(
            f"✅ ID канала сохранён и бот подтверждён как администратор!\n\n"
            f"Теперь активируйте сезон через /admin → Сезоны.",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await message.answer(
            f"⚠️ ID канала <code>{channel_id}</code> сохранён.\n"
            f"Но бот не подтверждён — убедитесь что @Invest_reinvest_bot добавлен администратором.",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )


@router.callback_query(F.data.startswith("admin_season_editsponsor:"))
async def cb_admin_season_editsponsor(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    season_id = int(callback.data.split(":")[1])
    await state.update_data(season_id=season_id)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📺 Канал", callback_data="edit_sponsor_type:channel"),
        InlineKeyboardButton(text="🤖 Бот", callback_data="edit_sponsor_type:bot"),
    )
    await callback.message.answer(
        "Выберите <b>новый тип спонсора</b>:\n\n"
        "⚠️ Доступ уже подтверждённых пользователей сохраняется.",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(AdminSeasonStates.edit_sponsor_type)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_sponsor_type:"), AdminSeasonStates.edit_sponsor_type)
async def admin_season_edit_sponsor_type(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    chosen = callback.data.split(":")[1]
    await state.update_data(new_sponsor_type=chosen)
    if chosen == "channel":
        await callback.message.answer(
            "Введите новую <b>ссылку или @username канала спонсора</b>:",
            parse_mode="HTML",
        )
        await state.set_state(AdminSeasonStates.edit_sponsor_channel)
    else:
        await callback.message.answer(
            "Введите <b>@username бота-спонсора</b> (например: @InvestBot):",
            parse_mode="HTML",
        )
        await state.set_state(AdminSeasonStates.edit_sponsor_bot)
    await callback.answer()


@router.message(AdminSeasonStates.edit_sponsor_bot)
async def admin_season_save_edit_sponsor_bot(message: Message, state: FSMContext, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    bot_username = message.text.strip() if message.text else ""
    if not bot_username:
        await message.answer("❌ Введите @username бота.")
        return
    if not bot_username.startswith("@"):
        bot_username = "@" + bot_username

    data = await state.get_data()
    season_id = data["season_id"]
    await state.clear()

    season_repo = SeasonRepository(session)
    await season_repo.update_sponsor_bot(season_id, bot_username)
    await session.commit()

    await message.answer(
        f"✅ Спонсор изменён на бота <b>{bot_username}</b>\n\n"
        f"Участники теперь получают доступ нажав «Я запустил» без проверки.",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("admin_season_activate:"))
async def cb_admin_season_activate(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    season_id = int(callback.data.split(":")[1])
    season_repo = SeasonRepository(session)
    season = await season_repo.get_by_id(season_id)
    if not season:
        await callback.answer("Сезон не найден.", show_alert=True)
        return

    await season_repo.activate(season_id)

    raffle_service = RaffleService(session)
    await raffle_service.schedule_mini_raffles(season)

    await session.commit()
    await callback.answer(f"✅ Сезон #{season.number} активирован!", show_alert=True)
    await cb_admin_seasons(callback, session)
