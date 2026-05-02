from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import app.models_loader
from app.config.connection import get_db
from app.bot.handlers import admin, common, player
from app.config.config import settings
import logging
from logging.handlers import RotatingFileHandler
from .middleware import log_requests
from app.routers.table_player import table_player_router
from app.routers.player import player_router
from app.routers.score import elo_router
from app.routers.table import table_router
from app.routers.game import game_router
from app.routers.tgchat import tgchat_router
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update, BotCommand

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

handler = RotatingFileHandler("app.log", maxBytes=1_000_000, backupCount=3)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()

dp.include_router(common.router)
dp.include_router(player.router)
dp.include_router(admin.router)

@asynccontextmanager 
async def lifespan(app: FastAPI): 
    webhook_url = f"{settings.BASE_URL}/webhook"
    await bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types() 
    )

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
    
    yield
    
    await bot.delete_webhook()
    await bot.session.close()

app = FastAPI(lifespan=lifespan) 


app.middleware("http")(log_requests)
app.include_router(table_player_router)
app.include_router(player_router)
app.include_router(elo_router)
app.include_router(table_router)
app.include_router(game_router)
app.include_router(tgchat_router)


@app.post("/webhook")
async def bot_webhook(
    update: dict,
    session: AsyncSession = Depends(get_db),
):
    try:
        tg_update = Update.model_validate(update, context={"bot": bot})
        await dp.feed_update(bot, tg_update, session=session)

    except Exception as e:
        logging.error(f"Error processing update: {e}")

    return {"ok": True}

