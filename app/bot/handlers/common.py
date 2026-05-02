from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.config import ApplicationException
from app.bot.utils.formatting import leaderboard_text
from .player import cmd_join
from .admin import cmd_register
from app.services.player import check_player_tg_id, get_leaderboard

router = Router(name="common")

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, bot: Bot, session: AsyncSession):
    user = message.from_user
    if not user:
        return
    
    args = message.text.split()

    if len(args) > 1 and args[1] == "join":
        try:
            player = await check_player_tg_id(session=session, tg_id=user.id)
            
            return await cmd_join(message, session)

        except ApplicationException as e:
            if e.code == 404:
                return await cmd_register(message, state, session)
               
            await message.answer(f"⚠️ {e.name}")
            return

        except Exception as e:
            await message.answer(f"⚠️ Server error - {e}")
            return
    
    await message.answer("Hello! Please use:\n/register - for new members\n/help - for others")



@router.message(Command("rating"))
async def cmd_rating(message: Message, session: AsyncSession):
    user = message.from_user
    if not user:
        return

    try:
        player = await check_player_tg_id(session=session, tg_id=user.id)
        data = await get_leaderboard(session=session, limit=50, offset=0)

    except ApplicationException as e:
        await message.answer(f"⚠️ {e.name}")
        return

    except Exception as e:
        await message.answer(f"⚠️ Server error - {e}")
        return

    items = data.items

    text = leaderboard_text(items)

    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "<b>🃏 Poker Bot Commands</b>\n\n"
        "<b>👤 Registration</b>\n"
        "/register — create your profile\n\n"
        "<b>🎮 Game</b>\n"
        "/join — join current game\n"
        "/leave — leave game\n"
        "/start_game — start game (organizer only)\n\n"
        "<b>📊 Stats</b>\n"
        "/rating — leaderboard (top players)\n"
        "/stats — your personal stats\n\n"
        "<b>🪑 Table actions</b>\n"
        "/chips — set chips for players at your table\n"
        "/knockout — mark who you knocked out\n"
        "/finish — close table & calculate results (organizer only)\n\n"
        "<b>ℹ️ Other</b>\n"
        "/help — show this message\n"
    )

    await message.answer(text)
