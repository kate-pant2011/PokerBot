from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.config import ApplicationException
from app.bot.utils.formatting import format_table_result
from app.bot.utils.broadcast import broadcast_table_results
from app.bot.states.game import CreateGameState
from datetime import datetime, timezone
from app.services.tgchat import create_tgchat, get_tgchat_list
from app.services.player import check_player_tg_id, get_my_table
from app.services.game import (
    get_game_list, create_game, distribute_tables, get_game_players_list, leave_game, distribute_tables_for_shuffle
)
from app.services.table_player import leave_table
from app.services.table import get_table_list, delete_table, get_table_list
from app.services.score import close_table_and_update_elo
from app.schemas.tgchat import TgchatAddRequest
from app.schemas.game import GameAddRequest
from app.schemas.table_player import TablePlayerPatch
from app.models.game import GameStatus
from app.bot.states.register import RegisterState
from app.database.game import get_all_games, get_active_game_players, get_game_by_id
from app.database.table import get_table_by_id, get_active_tables
from app.database.table_player import get_active_player_table, get_table_players_for_knockout, reward_survivors, get_table_players_by_id
from app.database.player import recalculate_rush6_elo, reset_all_players_elo, set_player_elo_by_name

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
    if not tg_user:
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
        await message.answer(f"⚠️ Server error - {e}")
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
        await message.answer(f"⚠️ Server error - {e}")
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
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
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
    if not tg_user:
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

    #создаем полл
    poll_register = await bot.send_poll(
        chat_id=int(chat_id),
        question=(
            f"<b>📢 Турнир!</b>\n"
            f"<b>{name}</b>\n"
            f"📆 Когда: {day}\n"
            f"🕗 Во сколько: {time}\n"
             "\n"
            f"Я секретарь турнира, зарегистрирую вас 🧐\n"
            "Тыкните если точно будете ⬇️"
        ),
        options=[
            "✅ Пришел на турнир, дайте стол"
        ],
        is_anonymous=False,
    )
    # poll_exit = await bot.send_poll(
    #         chat_id=int(chat_id),
    #         question=(
    #             f"{name} ({day})\n"
    #             f"Тебя выбили? Тыкай сюда ⬇️"
    #         ),
    #         options=[
    #             "☠️ Забрали все, кроме моего достоинства"
    #         ],
    #         is_anonymous=False,
    # )
    
    try:
        
        item = GameAddRequest(
            name=name,
            start_time=start_time.isoformat(),
            chat_id=chat_id
        )
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        game = await create_game(session=session,
                                 item=item,
                                 user_id=user.id,
                                 poll_register_id=poll_register.poll.id,
                                 poll_exit_id=None,
                                 registered=0)

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return 

    except Exception as e:
        await message.answer(f"⚠️ Server error - {e}")
        return

    await message.answer(
        f"✅ Game <b>{game.name}</b> created!"
    )

    if chat_id is not None:

        me = await bot.get_me()
        bot_username = me.username

        # link = f"https://t.me/{bot_username}?start=join"

        # await bot.send_message(
        #     chat_id=int(chat_id),
        #     text=(
        #         f"<b>📢 Турнир!</b>\n"
        #         f"<b>{name}</b>\n"
        #         f"📆 Когда: {day}\n"
        #         f"🕗 Во сколько: {time}\n"
        #         f' 👉 <a>регистрируйтесь в поле в основной беседе</a>' # тут ссылка была href="{link}" внутри <a ...>
        #     ),
        #     message_thread_id=thread_id
        # )

    await state.clear()


@router.callback_query(F.data.startswith("start_game:"))
async def cb_start_game(callback: CallbackQuery, bot: Bot, session: AsyncSession):
    tg_user = callback.from_user
    if not tg_user:
        return

    game_data = callback.data.split(":")
    game_id = int(game_data[1])
    game_name = game_data[2]

    try:
        print("BEFORE USER")
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        print("AFTER USER")
        data = await distribute_tables(session=session, game_id=game_id, user_id=user.id)
        print("AFTER TABLE DISTRIBUTE")

    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
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
                    text=f"🪑 Двигай за стол {table.number}",
                )
            except Exception:
                pass

    if data.chat_id is not None:
        message = await bot.send_message(
            chat_id=int(data.chat_id),
            text=("\n".join(text)),
            message_thread_id=data.thread_id or None
        )
        game = await get_game_by_id(session, game_id)
        game.status = GameStatus.IN_ACTION
        game.telegram_chat.message_with_tables_id = message.message_id
        game.telegram_chat.message_with_tables = "\n".join(text)
        # me = await bot.get_me()
        # bot_username = me.username
        poll_exit = await bot.send_poll(
                    chat_id=int(data.chat_id),
                    question=(
                        f"Тебя выбили? Тыкай сюда ⬇️"
                    ),
                    options=[
                        "☠️ Забрали все, кроме моего достоинства"
                    ],
                    is_anonymous=False,
            )
        game.poll_exit_id = poll_exit.poll.id
        await session.flush()
        # link = f"https://t.me/{bot_username}?start=knockout"
        # keyboard = InlineKeyboardMarkup(
        # inline_keyboard=[
        #         [
        #             InlineKeyboardButton(
        #                 text="💀 Выбил кого-то — тыкай сюда",
        #                 url=link,
        #             )
        #         ]
        #     ]
        # )

        # await bot.send_message(
        #     chat_id=int(data.chat_id),
        #     text="Фиксация выбиваний",
        #     reply_markup=keyboard,
        #     message_thread_id=data.thread_id or None,
        # )
    await callback.answer()


# @router.callback_query(F.data.startswith("knockout_menu:"))
# async def cb_knockout_menu(callback: CallbackQuery, session: AsyncSession):
#     tg_user = callback.from_user

#     if tg_user is None:
#         return
#     _, game_id = callback.data.split(":")
#     game_id = int(game_id)
#     user = await check_player_tg_id(
#         session=session,
#         tg_id=tg_user.id,
#     )
#     table_player = await get_active_player_table(
#         session=session,
#         player_id=user.id,
#         game_id=game_id,
#     )

#     if table_player is None:
#         await callback.answer(
#             text="Вы сейчас не сидите за столом",
#             receiver_user_id=tg_user.id,
#             show_alert=True,
#         )
#         return
#     table = table_player.table
#     players = await get_table_players_for_knockout(session, table.id, user.id)
#     keyboard = InlineKeyboardMarkup(
#     inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text=p.name,
#                     callback_data=f"knockout:{game_id}:{p.id}",
#                 )
#             ]
#             for p in players
#         ]
#     )
#     await callback.message.edit_text(
#         "💀 Кого выбили?",
#         reply_markup=keyboard,
#     )


# @router.callback_query(F.data.startswith("knockout:"))
# async def cb_knockout(callback: CallbackQuery, session: AsyncSession):
#     _, game_id, player_id = callback.data.split(":")

#     game_id = int(game_id)
#     player_id = int(player_id)
#     user = await check_player_tg_id(
#         session=session,
#         tg_id=callback.from_user.id,
#     )
#     table_player = await get_my_table(session=session, player_id=user.id)

#     table_id = table_player.table_id
#     item = TablePlayerPatch(
#         eliminated=True,
#     )

#     data = await leave_table(
#         session=session,
#         item=item,
#         table_id=table_id,
#         player_id=player_id,
#         user_id=user.id,
#         user_name=user.name,
#     )
#     try:
#         await callback.bot.send_message(
#             chat_id=data.telegram_id,
#             text=f"💀 You have been eliminated by {data.eliminator_name}",
#         )
#     except Exception:
#         pass
#     await reward_survivors(session, table_id)
#     keyboard = InlineKeyboardMarkup(
#     inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text="💀 Выбил кого-то — тыкай сюда",
#                     callback_data=f"knockout_menu:{game_id}",
#                 )
#             ]
#         ]
#     )

#     await callback.message.edit_text(
#         "Фиксация выбиваний",
#         reply_markup=keyboard,
#     )


@router.message(Command("finish"))
async def cmd_finish(message: Message, session: AsyncSession):
    user = message.from_user
    if not user:
        return

    try:
        await check_player_tg_id(session=session, tg_id=user.id)
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
        print("\n BEFORE GAME SUBSCRIPTION\n")
        game = games[0]
        print(f"\n {game.name} \n")
        # g = await get_game_by_id(session, game.id)
        # g.staus = GameStatus.FINISHED
        # g.is_archived = True
        
        # await session.flush()
        # return
        print("\n BEFORE GET TABLE LIST \n")
        tables = await get_table_list(
            session=session, limit=50, offset=0, game_id=game.id, organizer_id=None
        )
        print("\n AFTER GET TABLE LIST \n")
        items = tables.items or []
        if not items:
            await message.answer("❌ No tables available")
            return
        print("\n BEFORE INLINE KEYBOARD \n")
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
        await message.answer(f"⚠️ Server error - {e}")
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
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
        return


@router.callback_query(F.data.startswith("close_table:"))
async def cb_close_table(callback: CallbackQuery, bot: Bot, session: AsyncSession):
    tg_user = callback.from_user
    if not tg_user:
        return

    table_id = int(callback.data.split(":")[1])

    try:
        print(f"\n⚠️⚠️⚠️ BEFORE CHECK_TG_ID\n")
        user = await check_player_tg_id(session=session, tg_id=tg_user.id)
        print(f"\n⚠️⚠️⚠️ BEFORE CLOSE_TABLE_AND_UPDATE_ELO\n")
        result = await close_table_and_update_elo(
            session=session, table_id=table_id, user_id=user.id
        )
        print(f"\n⚠️⚠️⚠️ AFTER CLOSE_TABLE_AND_UPDATE_ELO\n")
    except ApplicationException as e:
        await callback.answer(e.name, show_alert=True)
        return 

    except Exception as e:
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
        return
    print(f"\n⚠️⚠️⚠️ BEFORE FORMAT RESULTS\n")
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
        await message.answer(f"⚠️ Server error - {e}")
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

########################################
@router.message(Command("shuffle"))
async def cmd_shuffle(message: Message, bot: Bot, session: AsyncSession):
    tg_user = message.from_user

    if tg_user is None:
        return
    
    try:
        user = await check_player_tg_id(
            session=session,
            tg_id=tg_user.id,
        )
        g = await get_all_games(session, 100, 0, GameStatus.IN_ACTION, user.id)
        game = g.items[0]
        # логика ниже для случая многих столов
        # tables = await get_table_list(session, 100, 0, game.id, organizer_id=user.id)
        # tables = tables.items
        # print("TABLES ITEMS")
        # while tables:
        #     table_slepok = tables.pop()
        #     table = await get_table_by_id(session, table_slepok.id)
        #     #await delete_table(session, table.id, user.id)
        #     table.finished_at = datetime.now(timezone.utc)
        #     print("TABLE FINISHED")
        # await session.flush()
        # print("AFTER FLUSH")
        #players = await get_active_game_players(session, game.id)
        sorting_rules = {"number": ("number",)}
        tables = await get_active_tables(session, 1000, 0, game.id, sorting_rules)
        #print(f"\nACTIVE TABLES {len(tables.items)}\n")
        print(f"ACTIVE TABLES WHEN SHUFFLE {len(tables.items)}")
        players = await get_table_players_by_id(session, tables.items[0].id)
        print(f"\nTABLE ID for ALL{tables.items[0].id}\n")
        data = await distribute_tables_for_shuffle(session, game.id, user.id, players, tables.items[0].id)
        print("SHUFFLE DISTRIBUTED")

    except ApplicationException as e:
        await message.answer(e.name)
        return
    
    except Exception as e:
        await message.answer(f"⚠️ Server error - {e}")
        return

    text = ["🔀 Столы перемешали!", ""]

    for table in data.tables:
        text.append(f"Table {table.number}:")
        for p in table.players:
            text.append(f" - {p.name}")
        text.append("")

    result = "\n".join(text)

    # Личные сообщения игрокам
    for table in data.tables:
        for p in table.players:
            try:
                await bot.send_message(
                    chat_id=p.telegram_id,
                    text=f"🪑 Двигай за стол {table.number}",
                )
            except Exception:
                pass

    # Сообщение в чат
    if data.chat_id is not None:
        # await bot.send_message(
        #     chat_id=int(data.chat_id),
        #     text=result,
        #     message_thread_id=data.thread_id or None,
        # )
        try:
            print("BEFORE MESSAGE_ID")
            message_id_with_tables = game.telegram_chat.message_with_tables_id
            print(f"\n ⚠️⚠️⚠️ \n chat_id={int(data.chat_id)}\n message_id={message_id_with_tables}")
            await bot.edit_message_text(
                text=result,
                chat_id=int(data.chat_id),
                message_id=message_id_with_tables
            )
        except Exception as e:
            print(f"⚠️ {e.name}")
            pass

    await message.answer("✅ Shuffle completed.")
    
#######################################


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
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
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
        await callback.answer(f"⚠️ Server error - {e}", show_alert=True)
        return

    await callback.message.edit_text("✅ Done")
    await callback.answer()

    await state.clear()

@router.callback_query(F.data == "remain_in_game")
async def cb_create_game(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text("🆗 Nothing has been changed")


@router.message(Command("reset_shit"))
async def cmd_reset_shit(message: Message, bot: Bot, session: AsyncSession):
    #await mod_all_players_elo(session)
    #await reset_all_players_elo(session, 0)
    #await recalculate_rush6_elo(session)
    await set_player_elo_by_name(
    session,
    "vladkier",
    81.7)
    await set_player_elo_by_name(
        session,
        "Санчоус",
        91.1)
    await set_player_elo_by_name(
            session,
            "Penchekrak",
            0)
    await set_player_elo_by_name(
                session,
                "f4koffka",
                9.9)