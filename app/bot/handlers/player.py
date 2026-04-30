from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from app.bot.states.register import RegisterState
from app.bot.states.chips import ChipsState
from app.bot.api.player import register_player, get_player_stats
from app.bot.api.game import join_game, leave_game, get_active_games
from app.bot.api.table import (
    get_tables,
    join_table,
    set_player_chips_api,
    get_my_table_api,
    knockout_player_api,
)
from aiogram.fsm.state import StatesGroup, State
from bot.config import APIError


router = Router(name="player")


@router.message(RegisterState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    user = message.from_user
    if not user:
        return

    name = message.text.strip()

    if len(name) < 2:
        await message.answer("Name too short, try again:")
        return

    try:
        player = await register_player(
            tg_id=user.id,
            name=name,
        )

    except APIError as e:
        if e.status_code == 400:
            await message.answer(f"⚠️ {e.message}")
            await state.clear()
        else:
            await message.answer(f"🚫 Server error, try later - {e}")
        return

    await message.answer(f"✅ Registered as <b>{name}</b>")

    await state.clear()


@router.message(Command("join"))
async def cmd_join(message: Message):
    user = message.from_user
    if not user:
        return

    try:
        games = await get_active_games(tg_id=user.id)

    except APIError as e:
        await message.answer(f"⚠️ {e.message}")
        return

    items = games.get("items", [])

    if not items:
        await message.answer("❌ No available games")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{g['name']}", callback_data=f"join_game:{g['id']}")]
            for g in items
        ]
    )

    await message.answer("🎮 Choose a game:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("join_game:"))
async def cb_join_game(callback: CallbackQuery):
    user = callback.from_user
    if not user:
        return

    game_id = int(callback.data.split(":")[1])

    try:
        result = await join_game(tg_id=user.id, game_id=game_id)
    except APIError as e:
        await callback.answer(e.message, show_alert=True)
        return

    await callback.message.edit_text(f"✅ {result.get('result', 'Joined game')}")
    await callback.answer()

    try:
        tables = await get_tables(game_id=game_id, tg_id=user.id)
    except APIError as e:
        await callback.answer(e.message, show_alert=True)
        return

    items = tables.get("items", [])

    if not items:
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🪑 Table {t['number']} ({t['total_participants']}/9)",
                    callback_data=f"join_table:{t['id']}"
                    if t["total_participants"] < 9
                    else "table_full",
                )
            ]
            for t in items
        ]
    )

    await callback.message.answer("🪑 Choose a table:", reply_markup=keyboard)


@router.callback_query(F.data == "table_full")
async def cb_full(callback: CallbackQuery):
    await callback.answer("❌ Table is full", show_alert=True)


@router.callback_query(F.data.startswith("join_table:"))
async def cb_join_table(callback: CallbackQuery):
    user = callback.from_user
    if not user:
        return

    table_id = int(callback.data.split(":")[1])

    try:
        result = await join_table(tg_id=user.id, table_id=table_id)
    except APIError as e:
        await callback.answer(e.message, show_alert=True)
        return

    await callback.message.edit_text(f"✅ Joined table {result['table']['number']}")

    await callback.answer()


@router.message(Command("leave"))
async def cmd_leave(message: Message):
    user = message.from_user
    if not user:
        return

    try:
        games = await get_active_games(tg_id=user.id)
    except APIError as e:
        await message.answer(f"⚠️ {e.message}")
        return

    items = games.get("items", [])

    if not items:
        await message.answer("❌ No active games")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{g['name']}", callback_data=f"leave_game:{g['id']}")]
            for g in items
        ]
    )

    await message.answer("👋 Choose a game to leave:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("leave_game:"))
async def cb_leave_game(callback: CallbackQuery):
    user = callback.from_user
    if not user:
        return

    game_id = int(callback.data.split(":")[1])

    try:
        await leave_game(tg_id=user.id, game_id=game_id)
    except APIError as e:
        await callback.answer(e.message, show_alert=True)
        return

    await callback.message.edit_text("👋 You left the game")
    await callback.answer()


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user = message.from_user
    if not user:
        return

    try:
        data = await get_player_stats(tg_id=int(user.id))
        elo = int(data['elo'])

    except APIError as e:
        if e.status_code == 400:
            await message.answer(f"⚠️ {e.message}")
        else:
            await message.answer("🚫 Server error, try later")
        return

    except Exception:
        await message.answer("❌ Cannot load stats right now")
        return

    text = (
        f"📊 <b>{data['name']}</b>\n\n"
        f"Rating: <code>{elo}</code>\n"
        f"Games: {data['total_games']}\n"
        f"KOs: {data['total_knockouts']}\n"
    )

    await message.answer(text)


@router.message(Command("chips"))
async def cmd_chips(message: Message, state: FSMContext):
    user = message.from_user
    if not user:
        return

    try:
        data = await get_my_table_api(tg_id=user.id)
    except APIError as e:
        await message.answer(f"⚠️ {e.message}")
        return

    except Exception:
        await state.clear()
        await message.answer("🚫 Server error")
        return

    players = data["players"]
    table_id = data["table_id"] 
 

    await state.update_data(table_id=table_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{p['name']} ({p['chips']})", callback_data=f"chips:{p['id']}:{p['table_id']}"
                )
            ]
            for p in players if isinstance(p.get("table_id"), int)
        ]
    )

    title = (
        "🎮 All players (organizer)"
        if data["scope"] == "game"
        else f"🪑 Table {data.get('table_number')}"
    )

    await message.answer(f"{title}\n\nSelect player:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("chips:"))
async def cb_choose_player(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    if not user:
        return

    player_id, table_id = map(int, callback.data.split(":")[1:])

    await state.update_data(player_id=player_id)
    
    if table_id is not None:
        await state.update_data(table_id=table_id)

    await callback.message.answer("💰 Enter chips amount:")
    await state.set_state(ChipsState.waiting_for_amount)

    await callback.answer()


@router.message(ChipsState.waiting_for_amount)
async def process_chips(message: Message, state: FSMContext):
    user = message.from_user
    if not user:
        return

    try:
        chips = int(message.text)
        if chips < 0:
            raise ValueError
    except:
        await message.answer("❌ Enter a valid number")
        return

    data = await state.get_data()
    player_id = data["player_id"]
    table_id = data["table_id"]

    try:
        await set_player_chips_api(
            tg_id=user.id, player_id=player_id, table_id=table_id, chips=chips
        )
    except Exception as e:
        await message.answer(f"❌ {e}")
        await state.clear()
        return

    await message.answer("✅ Chips updated")

    await state.clear()


@router.message(Command("knockout"))
async def cmd_knockout(message: Message):
    user = message.from_user
    if not user:
        return

    try:
        data = await get_my_table_api(tg_id=user.id)
    except APIError as e:
        await message.answer(f"⚠️ {e.message}")
        return

    except Exception:
        await message.answer("🚫 Server error")
        return

    if data["scope"] == "game":
        await message.answer("❌ Organizer cannot mark knockouts")
        return

    players = data["players"]
    table_id = data["table_id"]

    if not players:
        await message.answer("❌ No players to eliminate")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{p['name']} ({p['chips']})",
                    callback_data=f"knockout:{table_id}:{p['id']}",
                )
            ]
            for p in players
        ]
    )

    await message.answer("💀 Who did you eliminate?", reply_markup=keyboard)


@router.callback_query(F.data.startswith("knockout:"))
async def cb_knockout(callback: CallbackQuery):
    user = callback.from_user
    if not user:
        return

    _, table_id, player_id = callback.data.split(":")
    table_id = int(table_id)
    player_id = int(player_id)

    try:
        data = await knockout_player_api(tg_id=user.id, table_id=table_id, player_id=player_id)
        eliminated = data.get("player")

    except APIError as e:
        await callback.answer(e.message, show_alert=True)
        return

    except Exception:
        await callback.answer("🚫 Server error", show_alert=True)
        return

    await callback.message.edit_text("✅ Knockout recorded")

    try:
        await callback.bot.send_message(
            chat_id=eliminated["telegram_id"],
            text=f"💀 You have been eliminated by {data["eliminator_name"]}",
        )
    except Exception:
        pass

    await callback.answer()
