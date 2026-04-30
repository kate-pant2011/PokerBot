from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from app.bot.api.player import get_leaderboard, get_player
from app.bot.utils.formatting import leaderboard_text
from app.bot.api.table import get_tables
from bot.config import APIError
from .player import cmd_join
from .admin import cmd_register

router = Router(name="common")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    if not user:
        return
    
    args = message.text.split()

    if len(args) > 1 and args[1] == "join":
        try:
            player = await get_player(tg_id=user.id)
            
            if player == "404":
                return await cmd_register(message, state)
            
            return await cmd_join(message)

        except APIError as e:
            await message.answer(f"⚠️ {e.message}")
            return
    
    await message.answer("Hello! Please use:\n/register - for new members\n/help - for others")



@router.message(Command("rating"))
async def cmd_rating(message: Message):
    user = message.from_user
    if not user:
        return

    try:
        data = await get_leaderboard(tg_id=user.id)

    except APIError as e:
        await message.answer(f"⚠️ {e.message}")
        return

    items = data.get("items", [])

    text = leaderboard_text(items)

    await message.answer(text)


@router.message(Command("tables"))
async def cmd_tables(message: Message):
    try:
        data = await get_tables()
    except Exception:
        await message.answer("❌ Cannot load tables")
        return

    tables = data.get("tables", [])

    if not tables:
        await message.answer("❌ No active tables")
        return

    text = "🃏 <b>Tables</b>\n\n"

    for t in tables:
        text += f"🟢 <b>Table {t['number']}</b> — {t['players_alive']}/{t['players_total']} alive\n"

        for p in t["players"]:
            mark = "" if p["is_alive"] else " ❌"
            text += f"  {p['name']}{mark}\n"

        text += "\n"

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
