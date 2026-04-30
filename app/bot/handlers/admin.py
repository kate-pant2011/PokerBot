from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from app.bot.api.game import get_my_games_api, distribute_tables_api, get_game_in_action, add_new_game, get_game_api, remove_from_game
from app.bot.api.table import get_tables, close_table
from app.bot.api.tgchat import add_new_tgchat, get_tgchats
from app.bot.utils.formatting import format_table_result
from app.bot.utils.broadcast import broadcast_table_results
from bot.config import APIError
from app.bot.states.game import CreateGameState
from datetime import datetime

from app.bot.states.register import RegisterState

router = Router()


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    await message.answer("Nice to meet you! Please add your nickname:")

    await state.set_state(RegisterState.waiting_for_name)


@router.message(Command("setup"))
async def cmd_setup(message: Message, bot: Bot):

    chat_id = message.chat.id
    thread_id = message.message_thread_id
    chat_title = message.chat.title

    user = message.from_user
    if not user:
        return

    try:
        tgchat = await add_new_tgchat(tg_id=user.id, chat_title=chat_title, chat_id=int(chat_id), thread_id=int(thread_id) if thread_id else None)

    except APIError as e:
        await message.answer(f"⚠️ {e.message}")
        return

    await message.answer("♠♥♣♦")


@router.message(Command("start_game"))
async def cmd_start(message: Message):
    user = message.from_user
    if not user:
        return

    try:
        games = await get_my_games_api(tg_id=user.id, organizer_id=user.id)

    except APIError as e:
        await message.answer(f"⚠️ {e.message}")
        return

    items = games.get("items", [])

    keyboard = []

    for g in items:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{g['name']}",
                callback_data=f"start_game:{g['id']}:{g['name']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="➕ CREATE NEW GAME",
            callback_data="create_game"
        )
    ])

    await message.answer(
        "🎮 Choose game or create new:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data == "create_game")
async def cb_create_game(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    user = callback.from_user
    if not user:
        return

    try:
        tgchats = await get_tgchats(tg_id=user.id)

    except APIError as e:
        await callback.message.answer(f"⚠️ {e.message}")
        return

    items = tgchats.get("items", [])

    if not items:
        await state.update_data(chat_id=None)
        await state.update_data(thread_id=None) 
        await callback.message.answer("📝 Enter game name:")
        await state.set_state(CreateGameState.waiting_for_name)
        await callback.answer()
        return
    
    keyboard = []

    for chat in items:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{chat['chat_title']}",
                callback_data=f"chat:{chat['chat_id']}:{chat['thread_id']}"
            )
        ])


    await callback.message.edit_text(
        "💬 Choose chat_id",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


@router.callback_query(F.data.startswith("chat:"))
async def process_telegram_chat(callback: CallbackQuery, state: FSMContext):
    chat_data = callback.data.split(":")
    chat_id = int(chat_data[1])
    thread_id = int(chat_data[2])
    await state.update_data(chat_id=chat_id)
    await state.update_data(thread_id=thread_id)

    await callback.message.edit_text("📝 Enter game name:")
    await state.set_state(CreateGameState.waiting_for_name)
    await callback.answer()


@router.message(CreateGameState.waiting_for_name)
async def process_game_name(message: Message, state: FSMContext):
    name = message.text.strip()

    if len(name) < 1:
        await message.answer("❌ Name too short, try again:")
        return

    await state.update_data(name=name)

    await message.answer(
        "📅 Enter start time in format:\n<code>YYYY-MM-DD HH:MM:SS</code>"
    )

    await state.set_state(CreateGameState.waiting_for_date)



@router.message(CreateGameState.waiting_for_date)
async def process_game_date(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    if not user:
        return

    raw = message.text.strip()

    try:
        start_time = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        day = start_time.strftime("%d.%m")
        time = start_time.strftime("%H:%M")
    except ValueError:
        await message.answer(
            "❌ Wrong format. Use:\n<code>2026-12-25 19:30:00</code>"
        )
        return

    data = await state.get_data()
    name = data["name"]
    chat_id = data["chat_id"]
    thread_id = data["thread_id"]
    
    try:
        game = await add_new_game(
            tg_id=user.id,
            name=name,
            start_time=start_time.isoformat(),
            chat_id=chat_id
        )

    except APIError as e:
        await message.answer(f"⚠️ {e.message}")
        return

    await message.answer(
        f"✅ Game <b>{game['name']}</b> created!"
    )

    if chat_id is not None:

        me = await bot.get_me()
        bot_username = me.username

        link = f"https://t.me/{bot_username}?start=join"

        await bot.send_message(
            chat_id=int(chat_id),
            text=(
                f"<b>📢 New game announcement!</b>\n"
                f"📆 Day: {day}\n"
                f"🕗 Time: {time}\n"
                f"Name: {name}"
                f' 👉 <a href="{link}">join game</a>'
            ),
            message_thread_id=thread_id
        )

    await state.clear()


@router.callback_query(F.data.startswith("start_game:"))
async def cb_start_game(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    if not user:
        return

    game_data = callback.data.split(":")
    game_id = int(game_data[1])
    game_name = game_data[2]

    try:
        data = await distribute_tables_api(game_id=game_id, tg_id=user.id)
    except APIError as e:
        await callback.answer(e.message, show_alert=True)
        return

    text = [f"🎮 Game '{game_name}' started!\n"]

    for table in data["tables"]:
        text.append(f"Table {table['number']}:")
        for p in table["players"]:
            text.append(f" - {p['name']}")
        text.append("")

    try:
        await callback.message.edit_text("\n".join(text))
    except Exception:
        pass

    for table in data["tables"]:
        for p in table["players"]:
            try:
                await callback.bot.send_message(
                    chat_id=p["telegram_id"],
                    text=f"🪑 You are seated at table {table['number']}",
                )
            except Exception:
                pass

    if data["chat_id"] is not None:
        await bot.send_message(
            chat_id=int(data["chat_id"]),
            text=("\n".join(text)),
            message_thread_id=data.get("thread_id") or None
        )

    await callback.answer()


@router.message(Command("finish"))
async def cmd_finish(message: Message):
    user = message.from_user
    if not user:
        return

    try:
        games = await get_game_in_action(tg_id=user.id)
        games = games["items"] or []

        if not games:
            await message.answer("❌ No active game")
            return

        if len(games) > 1:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"{g['name']}", callback_data=f"finish_game:{g['id']}"
                        )
                    ]
                    for g in games
                ]
            )

            await message.answer("🎮 Choose game:", reply_markup=keyboard)
            return

        game = games[0]

        tables = await get_tables(tg_id=user.id, game_id=game["id"])

        items = tables.get("items", [])

        if not items:
            await message.answer("❌ No tables available")
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"Table {t['number']} ({t.get('total_participants', '?')} players)",
                        callback_data=f"close_table:{t['id']}",
                    )
                ]
                for t in items
            ]
        )

        await message.answer("🪑 Choose table to finish:", reply_markup=keyboard)

    except APIError as e:
        await message.answer(f"⚠️ {e.message}")
        return


@router.callback_query(F.data.startswith("finish_game:"))
async def cb_finish_game(callback: CallbackQuery):
    user = callback.from_user
    if not user:
        return

    game_id = int(callback.data.split(":")[1])

    try:
        tables = await get_tables(tg_id=user.id, game_id=game_id)

        items = tables.get("items", [])

        if not items:
            await callback.answer("❌ No tables available", show_alert=True)
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"Table {t['number']} ({t.get('total_participants', '?')} players)",
                        callback_data=f"close_table:{t['id']}",
                    )
                ]
                for t in items
            ]
        )

        await callback.message.edit_text("🪑 Choose table to finish:", reply_markup=keyboard)

        await callback.answer()

    except APIError as e:
        await callback.answer(f"⚠️ {e.message}", show_alert=True)

    except Exception:
        await callback.answer("🚫 Server error", show_alert=True)


@router.callback_query(F.data.startswith("close_table:"))
async def cb_close_table(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    if not user:
        return

    table_id = int(callback.data.split(":")[1])

    try:
        result = await close_table(tg_id=user.id, table_id=table_id)
    except APIError as e:
        await callback.answer(e.message, show_alert=True)
        return

    except Exception as e:
        await callback.answer(str(e), show_alert=True)
        return

    text = format_table_result(result)

    await callback.message.edit_text(text)

    if result["chat_id"] is not None:
        await bot.send_message(
            chat_id=int(result["chat_id"]),
            text=text,
            message_thread_id=result.get("thread_id") or None
        )

    await broadcast_table_results(callback.bot, result)

    await callback.answer()


@router.message(Command("game_list"))
async def cmd_game_list(message: Message):
    user = message.from_user
    if not user:
        return

    try:
        games = await get_my_games_api(tg_id=user.id, organizer_id=user.id)

    except APIError as e:
        await message.answer(f"⚠️ {e.message}")
        return

    items = games.get("items", [])

    keyboard = []

    for g in items:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{g['name']}",
                callback_data=f"game_list:{g['id']}:{g['name']}"
            )
        ])

    await message.answer(
        "🎮 Choose game:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


@router.callback_query(F.data.startswith("game_list:"))
async def cb_game_list(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    if not user:
        return

    game_data = callback.data.split(":")
    game_id = int(game_data[1])
    game_name = game_data[2]
    await state.update_data(game_name=game_name)
    await state.update_data(game_id=game_id)

    try:
        game = await get_game_api(game_id=game_id, tg_id=user.id)
        game_players = game.get("items") or None

    except APIError as e:
        await callback.answer(e.message, show_alert=True)
        return

    if game_players:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{gp.get("player")['name']}",
                        callback_data=f"game_player:{gp.get("player")['id']}:{gp.get("player")['name']}"
                    )
                ]
                for gp in game_players
            ]
        )

        await callback.message.edit_text(f"Choose a player to remove from game {game_name}:", reply_markup=keyboard)
    
    else:
        await callback.message.answer(f"🚫 {game_name} has no players")

    await callback.answer()


@router.callback_query(F.data.startswith("game_player:"))
async def process_game_player(callback: CallbackQuery, state: FSMContext):
    player_data = callback.data.split(":")
    player_id = int(player_data[1])
    player_name = player_data[2]

    data = await state.get_data()
    game_name = data["game_name"]

    await state.update_data(player_id=player_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="YES",
                callback_data="remove_from_game"
            )
        ],
        [
            InlineKeyboardButton(
                text="NO",
                callback_data="remain_in_game"
            )
        ]
    ])
    await callback.message.edit_text(f"Are you sure you want to remove <b>{player_name}</b> from game '{game_name}'?", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "remove_from_game")
async def cb_create_game(callback: CallbackQuery, state: FSMContext):

    user = callback.from_user
    if not user:
        return
    
    data = await state.get_data()
    player_id = data["player_id"]
    game_id = data["game_id"]

    try:
        await remove_from_game(tg_id=user.id, game_id=game_id, player_id=player_id)
    except APIError as e:
        await callback.answer(e.message, show_alert=True)
        return

    await callback.message.edit_text("✅ Done")
    await callback.answer()

    await state.clear()

@router.callback_query(F.data == "remain_in_game")
async def cb_create_game(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text("🆗 Nothing has been changed")
    