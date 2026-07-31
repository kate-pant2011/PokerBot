from aiogram import Bot, Router
from aiogram.types import PollAnswer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.config import ApplicationException
from app.models.game import Game, Status
import asyncio
from app.services.player import (
    check_player_tg_id,
    create_player,
)
from app.services.game import join_game, leave_game
from app.services.score import rating_update_ballroom_system
from app.services.player import get_my_table
from app.services.table_player import leave_table
from app.database.game import is_player_in_game
from app.database.table_player import get_active_table_map, get_table_player_by_id, table_participants_count
from app.schemas.player import PlayerAddRequest
from app.schemas.table_player import TablePlayerPatch
import datetime

router = Router(name="poll")

#дописать логику регистрации на турнир
#при шаффл мы проверяем тайминги когда кто пришел и на группы делим
@router.poll_answer()
async def poll_answer_handler(
    poll_answer: PollAnswer,
    bot: Bot,
    session: AsyncSession,
):
    
    if not poll_answer:
        print("ПРоблемка в poll_answer_handler, пол не нашелся")
        return

    # Ищем poll_id
    poll_id = poll_answer.poll_id

    # Получаем игру
    game = await session.scalar(
        select(Game).where(
            Game.poll_register_id == poll_id
        )
    )
    # разбираемся какой из полов
    poll_register_id = True

    if game is None:
        print(f"\n⚠️⚠️⚠️ POLL FOR EXIT\n")
        game = await session.scalar(
                select(Game).where(
                    Game.poll_exit_id == poll_id
                )
            )
        poll_register_id = False

    try:
        player = await check_player_tg_id(
            session=session,
            tg_id=poll_answer.user.id,
        )
    except ApplicationException as e:
        player = None

    # Если пользователь снял голос, удаляем из турнира
    if poll_register_id:
        if not poll_answer.option_ids:
            await leave_game(session, game.id, player.id)
            return
    
    # Если игрока нет — создаем
    if player is None:

        item = PlayerAddRequest(
            name=poll_answer.user.username if poll_answer.user.username else f"Неопознанный орангутанг {datetime.datetime.now().microsecond % 1000}"
        )

        player = await create_player(
            session=session,
            item=item,
            tg_id=poll_answer.user.id,
        )

    if poll_register_id:
        text = await join_game(
            session=session,
            game_id=game.id,
            player_id=player.id,
        )
        game.registered = game.registered + 1
        try:
            await bot.send_message(
                chat_id=poll_answer.user.id,
                text=text.result,
            )
            # if text.result != "joined":
            #     # msg = await bot.send_message(
            #     #     chat_id=game.telegram_chat.chat_id,
            #     #     text=f"@{poll_answer.user.username}, {text.result}"
            #     # )
            #     print("BEFORE MESSAGE_ID")
            #     message_id_with_tables = game.telegram_chat.message_with_tables_id
            #     print("AFTER MESSAGE_ID")
            #     # берем новый номер человека
            #     if '#' in text.result:
            #         val_to_split_by = f"Table {text.result.split('#')[-1]}:\n"
            #         print("AFTER FIRST SPLIT")
            #         text_parts = str(game.telegram_chat.message_with_tables).split(val_to_split_by)
            #         print("SPLITTING DONE")
            #         text_parts[0] = text_parts[0] + val_to_split_by + f" - @{poll_answer.user.username}" + "\n"
            #         await bot.edit_message_text(
            #             text=text_parts[0] + text_parts[1],
            #             chat_id=int(game.telegram_chat_id),
            #             message_id=message_id_with_tables
            #         )
            #     else:
            #         msg = await bot.send_message(
            #                     chat_id=game.telegram_chat.chat_id,
            #                     text=f"@{poll_answer.user.username}, ✅ Ты в игре, НО!\n" + text.result,
            #                 )
            #         await asyncio.sleep(15)
            #         await bot.delete_message(msg.chat.id, msg.message_id)

            #await asyncio.sleep(15)
            #await bot.delete_message(msg.chat.id, msg.message_id)
        except Exception as e:
            print(f"⚠️ {e.name}")
            pass
    else: # логика если вылететел
        print(f"⚠️⚠️⚠️ POLL EXIT REALIZATION")
        game_player = await is_player_in_game(session, player.id, game.id)
        
        if game_player is not None:
            table = await get_my_table(session=session, player_id=game_player.player.id)
            table_id = table.table_id
            tp = await get_table_player_by_id(session, table_id, player.id)
            print(f"\n ⚠️⚠️⚠️game_player is ACTIVE {tp.is_active} \n")
            if tp.is_active:
                print(f"⚠️⚠️⚠️ DOING LEAVE TABLE")
                item = TablePlayerPatch(eliminated=True)
                print("\n ⚠️⚠️⚠️ BEFORE LEAVE_TABLE IN POLL ANSWER \n")
                current_participants = await table_participants_count(session, table_id)
                tp.player.elo_change_per_match = 100 * (((game.registered - current_participants)/(game.registered - 1))**(1.5))*(game.registered/15)**(0.2)
                await leave_table(session, item, table_id, player.id, player.id, game_player.player.name)
                print("⚠️⚠️⚠️ LEFT TABLE")
                await rating_update_ballroom_system(session, game.id)
            else:
                msg = await bot.send_message(
                                                chat_id=game.telegram_chat.chat_id,
                                                text=f"@{poll_answer.user.username}, твой уход уже отмечен, красавчик!\n Доброй ночи 😴",
                                            )
                await asyncio.sleep(5)
                await bot.delete_message(msg.chat.id, msg.message_id)
        else:
            msg = await bot.send_message(
                                chat_id=game.telegram_chat.chat_id,
                                text=f"@{poll_answer.user.username}, чтобы вылететь, зарегистрируйся\n",
                            )
            await asyncio.sleep(5)
            await bot.delete_message(msg.chat.id, msg.message_id)

