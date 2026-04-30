import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from app.bot.handlers import admin, common, player

from aiogram.types import Message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("bot")


async def main():
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    dp.include_router(common.router)
    dp.include_router(player.router)
    dp.include_router(admin.router)

    await bot.set_my_commands(
        [
            BotCommand(command="register", description="Register"),
            BotCommand(command="join", description="Join game"),
            BotCommand(command="start_game", description="Start game"),
            BotCommand(command="rating", description="Leaderboard"),
            BotCommand(command="stats", description="Your stats"),
            BotCommand(command="knockout", description=" You are eliminator"),
            BotCommand(command="chips", description="Set chips"),
            BotCommand(command="finish", description="Finish table"),
            BotCommand(command="leave", description="Leave game"),
            BotCommand(command="game_list", description="Your game players"),
            BotCommand(command="help", description="Help"),
        ]
    )

    log.info("Bot started")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        log.info("Завершение работы...")
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Бот остановлен.")
