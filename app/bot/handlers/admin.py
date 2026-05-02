from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.config import ApplicationException
from app.bot.utils.formatting import format_table_result
from app.bot.utils.broadcast import broadcast_table_results
from app.bot.states.game import CreateGameState
from datetime import datetime
from app.services.tgchat import create_tgchat, get_tgchat_list
from app.services.player import check_player_tg_id
from app.services.game import (
    get_game_list, create_game, distribute_tables, get_game_players_list, leave_game
)
from app.services.table import get_table_list
from app.services.score import close_table_and_update_elo
from app.schemas.tgchat import TgchatAddRequest
from app.schemas.game import GameAddRequest

from app.bot.states.register import RegisterState

router = Router()


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    await message.answer("Nice to meet you! Please add your nickname:")

    await state.set_state(RegisterState.waiting_for_name)


@router.message(Command("setup"))
async def cmd_setup(message: Message, session: AsyncSession):

    chat_id = message.chat.id
    thread_id = message.message_thread_id
    chat_title = message.chat.title

    tg_user = message.from_user
    if not user:
        return

    try:
        thread_id=int(thread_id) if thread_id else None
        item = TgchatAddRequest(
            chat_title=chat_title, chat_id=int(chat_id), thread_id=thread_id
        )
    
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        await create_tgchat(session=session, item=item, user_id=user.id)
    
    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await message.answer("⚠️ Server error")
        return

    await message.answer("♠♥♣♦")


@router.message(Command("start_game"))
async def cmd_start(message: Message, session: AsyncSession):
    user = message.from_user
    if not user:
        return

    try:
        await check_player_tg_id(session=session, tg_id=user.id)
        games = await get_game_list(
            session=session, limit=50, offset=0, organizer_id=user.id, status=None
        )

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await message.answer("⚠️ Server error")
        return

    items = games.items or []

    keyboard = []

    for g in items:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{g.name}",
                callback_data=f"start_game:{g.id}:{g.name}"
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
async def cb_create_game(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.answer()

    user = callback.from_user
    if not user:
        return

    try:
        await check_player_tg_id(session=session, tg_id=user.id)
        tgchats = await get_tgchat_list(session=session, limit=50, offset=0)


    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer("⚠️ Server error", show_alert=True)
        return

    items = tgchats.items or []

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
                text=f"{chat.chat_title}",
                callback_data=f"chat:{chat.chat_id}:{chat.thread_id}"
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
async def process_game_date(message: Message, state: FSMContext, bot: Bot, session: AsyncSession):
    tg_user = message.from_user
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
        
        item = GameAddRequest(
            name=name,
            start_time=start_time.isoformat(),
            chat_id=chat_id
        )
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        game = await create_game(session=session, item=item, user_id=user.id)

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await message.answer("⚠️ Server error")
        return

    await message.answer(
        f"✅ Game <b>{game.name}</b> created!"
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
async def cb_start_game(callback: CallbackQuery, bot: Bot, session: AsyncSession):
    tg_user = callback.from_user
    if not user:
        return

    game_data = callback.data.split(":")
    game_id = int(game_data[1])
    game_name = game_data[2]

    try:
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        data = await distribute_tables(session=session, game_id=game_id, user_id=user.id)

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer("⚠️ Server error", show_alert=True)
        return

    text = [f"🎮 Game '{game_name}' started!\n"]

    for table in data.tables:
        text.append(f"Table {table.number}:")
        for p in table.players:
            text.append(f" - {p.name}")
        text.append("")

    try:
        await callback.message.edit_text("\n".join(text))
    except Exception:
        pass

    for table in data.tables:
        for p in table.players:
            try:
                await callback.bot.send_message(
                    chat_id=p.telegram_id,
                    text=f"🪑 You are seated at table {table.number}",
                )
            except Exception:
                pass

    if data.chat_id is not None:
        await bot.send_message(
            chat_id=int(data.chat_id),
            text=("\n".join(text)),
            message_thread_id=data.thread_id or None
        )

    await callback.answer()


@router.message(Command("finish"))
async def cmd_finish(message: Message, session: AsyncSession):
    tg_user = message.from_user
    if not user:
        return

    try:
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        games = await get_game_list(
            session=session, limit=50, offset=0, organizer_id=user.id, status="in_action"
        )
        games = games.items or []

        if not games:
            await message.answer("❌ No active game")
            return

        if len(games) > 1:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"{g.name}", callback_data=f"finish_game:{g.id}"
                        )
                    ]
                    for g in games
                ]
            )

            await message.answer("🎮 Choose game:", reply_markup=keyboard)
            return

        game = games[0]

        tables= await get_table_list(
            session=session, limit=50, offset=0, game_id=game.id, organizer_id=None
        )

        items = tables.items or []

        if not items:
            await message.answer("❌ No tables available")
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"Table {t.number} ({t.total_participants or'?'} players)",
                        callback_data=f"close_table:{t.id}",
                    )
                ]
                for t in items
            ]
        )

        await message.answer("🪑 Choose table to finish:", reply_markup=keyboard)

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await message.answer("⚠️ Server error")
        return


@router.callback_query(F.data.startswith("finish_game:"))
async def cb_finish_game(callback: CallbackQuery, session: AsyncSession):
    user = callback.from_user
    if not user:
        return

    game_id = int(callback.data.split(":")[1])

    try:

        await check_player_tg_id(session=session, tg_id=user.id)
        tables= await get_table_list(
            session=session, limit=50, offset=0, game_id=game_id, organizer_id=None
        )
        items = tables.items or []

        if not items:
            await callback.answer("❌ No tables available", show_alert=True)
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"Table {t.number} ({t.total_participants or '?'} players)",
                        callback_data=f"close_table:{t.id}",
                    )
                ]
                for t in items
            ]
        )

        await callback.message.edit_text("🪑 Choose table to finish:", reply_markup=keyboard)

        await callback.answer()

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer("⚠️ Server error", show_alert=True)
        return


@router.callback_query(F.data.startswith("close_table:"))
async def cb_close_table(callback: CallbackQuery, bot: Bot, session: AsyncSession):
    tg_user = callback.from_user
    if not user:
        return

    table_id = int(callback.data.split(":")[1])

    try:
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        result = await close_table_and_update_elo(
            session=session, table_id=table_id, user_id=user.id
        )
    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer("⚠️ Server error", show_alert=True)
        return

    text = format_table_result(result)

    await callback.message.edit_text(text)

    if result.chat_id is not None:
        await bot.send_message(
            chat_id=int(result.chat_id),
            text=text,
            message_thread_id=result.thread_id or None
        )

    await broadcast_table_results(callback.bot, result)

    await callback.answer()


@router.message(Command("game_list"))
async def cmd_game_list(message: Message, session: AsyncSession):
    user = message.from_user
    if not user:
        return

    try:
        await check_player_tg_id(session=session, tg_id=user.id)
        games = await get_game_list(
            session=session, limit=50, offset=0, organizer_id=user.id, status=None
        )

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await message.answer("⚠️ Server error")
        return

    items = games.items or []

    keyboard = []

    for g in items:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{g.name}",
                callback_data=f"game_list:{g.id}:{g.name}"
            )
        ])

    await message.answer(
        "🎮 Choose game:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


@router.callback_query(F.data.startswith("game_list:"))
async def cb_game_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = callback.from_user
    if not user:
        return

    game_data = callback.data.split(":")
    game_id = int(game_data[1])
    game_name = game_data[2]
    await state.update_data(game_name=game_name)
    await state.update_data(game_id=game_id)

    try:
        await check_player_tg_id(session=session, tg_id=user.id)
        data = await get_game_players_list(
            session=session, game_id=game_id, limit=100, offset=0
        )
        game_players = data.items or None

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer("⚠️ Server error", show_alert=True)
        return

    if game_players:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{i}. {gp.player.name}",
                        callback_data=f"game_player:{gp.player.id}:{gp.player.name}"
                    )
                ]
                for i, gp in enumerate(game_players, start=1)
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
                text="YES, I want to remove",
                callback_data="remove_from_game"
            )
        ],
        [
            InlineKeyboardButton(
                text="NO, please don't remove",
                callback_data="remain_in_game"
            )
        ]
    ])
    await callback.message.edit_text(
        f"Are you sure you want to remove <b>{player_name}</b> from game '{game_name}'?", 
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "remove_from_game")
async def cb_create_game(callback: CallbackQuery, state: FSMContext, session: AsyncSession):

    user = callback.from_user
    if not user:
        return
    
    data = await state.get_data()
    player_id = data["player_id"]
    game_id = data["game_id"]

    try:
        await check_player_tg_id(session=session, tg_id=user.id)
        await leave_game(session=session, game_id=game_id, player_id=player_id)

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer("⚠️ Server error", show_alert=True)
        return

    await callback.message.edit_text("✅ Done")
    await callback.answer()

    await state.clear()

@router.callback_query(F.data == "remain_in_game")
async def cb_create_game(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text("🆗 Nothing has been changed")
    