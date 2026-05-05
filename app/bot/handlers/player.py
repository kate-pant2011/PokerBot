from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.config import ApplicationException
from aiogram.filters import Command
from app.bot.states.register import RegisterState
from app.bot.states.chips import ChipsState
from app.services.player import create_player, check_player_tg_id, get_player_id, get_my_table
from app.services.game import get_game_list, join_game, leave_game
from app.services.table import get_table_list
from app.services.table_player import add_player_at_table, change_table_player, leave_table
from app.schemas.player import PlayerAddRequest
from app.schemas.table_player import TablePlayerPatch


router = Router(name="player")


@router.message(RegisterState.waiting_for_name)
async def process_name(message: Message, state: FSMContext, session: AsyncSession):
    user = message.from_user
    if not user:
        return

    name = message.text.strip()


    try:
        item = PlayerAddRequest(name=name)
    except Exception:
        await message.answer("Name too short, try again:")
        return
    
    try:
        player = await create_player(session=session, item=item, tg_id=user.id)

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        await state.clear()
        return 

    except Exception as e:
        await message.answer(f"⚠️ Server error - {e}")
        await state.clear()
        return

    await message.answer(f"✅ Registered as <b>{name}</b>")

    await state.clear()


@router.message(Command("join"))
async def cmd_join(message: Message, session: AsyncSession):
    user = message.from_user
    if not user:
        return

    try:
        player =  await check_player_tg_id(session=session, tg_id=user.id)
        games = await get_game_list(
            session=session, limit=50, offset=0, status=None, organizer_id=None
        )

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await message.answer(f"⚠️ Server error - {e}")
        return

    items = games.items or []

    if not items:
        await message.answer("❌ No available games")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{g.name}", callback_data=f"join_game:{g.id}")]
            for g in items
        ]
    )

    await message.answer("🎮 Choose a game:", reply_markup=keyboard)

'''
@router.callback_query(F.data.startswith("join_game:"))
async def cb_join_game(callback: CallbackQuery, session: AsyncSession):
    user = callback.from_user
    if not user:
        return

    game_id = int(callback.data.split(":")[1])

    try:
        player =  await check_player_tg_id(session=session, tg_id=user.id)
        result = await join_game(session=session, game_id=game_id, player_id=player.id)

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
        return

    await callback.message.edit_text("✅ joined")
    await callback.answer()

    try:
        tables = await get_table_list(
            session=session, limit=50, offset=0, game_id=game_id, organizer_id=None
        )

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
        return

    items = tables.items or []

    if not items:
        await callback.answer(f"Game has not started yet")
        return 

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🪑 Table {t.number} ({t.total_participants}/9)",
                    callback_data=f"join_table:{t.id}"
                    if t.total_participants < 9
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
'''

@router.callback_query(F.data.startswith("join_game:"))
async def cb_join_table(callback: CallbackQuery, session: AsyncSession):
    tg_user = callback.from_user
    if not tg_user:
        return

    #table_id = int(callback.data.split(":")[1])
    game_id = int(callback.data.split(":")[1])

    try:
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        result = await join_game(session=session, game_id=game_id, player_id=user.id)

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
        return

    await callback.message.edit_text("✅ Joined")
    await callback.answer()

    try:
        tables = await get_table_list(
            session=session, limit=50, offset=0, game_id=game_id, organizer_id=None
        )
        items = tables.items or []

        if items == []:
            await callback.answer(f"Game has not started yet")
            return 
        
        table = items[0]
        result = await add_player_at_table(session=session, table_id=table.id, player_id=user.id)

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
        return

    #await callback.message.edit_text(f"✅ Joined table {result.table.number}")
    await callback.message.answer(f"Game has already started!\nPlease join any free table🤗")

    await callback.answer()


@router.message(Command("leave"))
async def cmd_leave(message: Message, session: AsyncSession):
    user = message.from_user
    if not user:
        return

    try:
        games = await get_game_list(
            session=session, limit=50, offset=0, organizer_id=None, status=None
        )

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await message.answer(f"⚠️ Server error - {e}")
        return
    
    items = games.items or []

    if not items:
        await message.answer("❌ No active games")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{g.name}", callback_data=f"leave_game:{g.id}")]
            for g in items
        ]
    )

    await message.answer("👋 Choose a game to leave:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("leave_game:"))
async def cb_leave_game(callback: CallbackQuery, session: AsyncSession):
    user = callback.from_user
    if not user:
        return

    game_id = int(callback.data.split(":")[1])

    try:
        player = await check_player_tg_id(session=session, tg_id=user.id)
        await leave_game(session=session, game_id=game_id, player_id=player.id)

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
        return

    await callback.message.edit_text("👋 You left the game")
    await callback.answer()


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    tg_user = message.from_user
    if not tg_user:
        return

    try:
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        data = await get_player_id(session=session, player_id=user.id)
        elo = int(data.elo)

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await message.answer(f"⚠️ Server error - {e}")
        return

    text = (
        f"📊 <b>{data.name}</b>\n\n"
        f"Rating: <code>{elo}</code>\n"
        f"Games: {data.total_games}\n"
        f"KOs: {data.total_knockouts}\n"
    )

    await message.answer(text)


@router.message(Command("chips"))
async def cmd_chips(message: Message, state: FSMContext, session: AsyncSession):
    tg_user = message.from_user
    if not tg_user:
        return

    try:
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        data = await get_my_table(session=session, player_id=user.id)

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await state.clear()
        await message.answer(f"⚠️ Server error - {e}")
        return

    players = data.players
    table_id = data.table_id 
 

    await state.update_data(table_id=table_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{p.name} ({p.chips})", callback_data=f"chips:{p.id}:{p.table_id}:{p.name}"
                )
            ]
            for p in players if isinstance(p.table_id, int)
        ]
    )

    title = (
        "🎮 All players (organizer)"
        if data.scope == "game"
        else f"🪑 Table {data.table_number}"
    )

    await message.answer(f"{title}\n\nSelect player:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("chips:"))
async def cb_choose_player(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    if not user:
        return

    player_id, table_id, player_name = callback.data.split(":")[1:]

    await state.update_data(player_id=int(player_id))
    await state.update_data(player_name=player_name)
    
    if table_id is not None:
        await state.update_data(table_id=int(table_id))

    await callback.message.answer("💰 Enter chips amount:")
    await state.set_state(ChipsState.waiting_for_amount)

    await callback.answer()


@router.message(ChipsState.waiting_for_amount)
async def process_chips(message: Message, state: FSMContext, session: AsyncSession):
    user = message.from_user
    if not user:
        return

    try:
        chips = int(message.text)
        item = TablePlayerPatch(chips=chips)

    except:
        await message.answer("❌ Enter a valid number")
        return

    data = await state.get_data()
    player_id = data["player_id"]
    table_id = data["table_id"]
    player_name = data["player_name"]

    try:
        item = TablePlayerPatch(chips=chips)
        user = await check_player_tg_id(session=session, tg_id=user.id)
        
        await change_table_player(
            session=session, item=item, table_id=table_id, user_id=user.id, player_id=player_id
        )
    
    except Exception as e:
        await message.answer(f"❌ {e}")
        await state.clear()
        return

    await message.answer(f"✅ Chips for <b>{player_name}</b> updated")

    await state.clear()


@router.message(Command("knockout"))
async def cmd_knockout(message: Message, session: AsyncSession):
    tg_user = message.from_user
    if not tg_user:
        return

    try:

        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        data = await get_my_table(session=session, player_id=user.id)

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await message.answer(f"⚠️ Server error - {e}")
        return

    if data.scope == "game":
        await message.answer("❌ Organizer cannot mark knockouts")
        return

    players = data.players
    table_id = data.table_id

    if not players:
        await message.answer("❌ No players to eliminate")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{p.name} ({p.chips})",
                    callback_data=f"knockout:{table_id}:{p.id}",
                )
            ]
            for p in players
        ]
    )

    await message.answer("💀 Who did you eliminate?", reply_markup=keyboard)


@router.callback_query(F.data.startswith("knockout:"))
async def cb_knockout(callback: CallbackQuery, session: AsyncSession):
    tg_user = callback.from_user
    if not tg_user:
        return

    _, table_id, player_id = callback.data.split(":")
    table_id = int(table_id)
    player_id = int(player_id)

    try:
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        item = TablePlayerPatch(eliminated=True)
        data = await leave_table(
            session=session, item=item, table_id=table_id, user_id=user.id, player_id=player_id, user_name=user.name
        )
        eliminated = data.player

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
        return

    await callback.message.edit_text("✅ Knockout recorded")

    try:
        await callback.bot.send_message(
            chat_id=eliminated.telegram_id,
            text=f"💀 You have been eliminated by {data.eliminator_name}",
        )
    except Exception:
        pass

    await callback.answer()
