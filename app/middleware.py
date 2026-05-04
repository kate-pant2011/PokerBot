import time
import logging
from fastapi import Request
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery
from app.config.connection import SessionLocal

logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    logger.info(
        "%s %s - %s - %.3f sec",
        request.method,
        request.url.path,
        response.status_code,
        process_time,
    )
    return response


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        async with SessionLocal() as session:
            is_manual = False

            if isinstance(event, CallbackQuery):
                if event.data and event.data.startswith("start_game:"):
                    is_manual = True

            if is_manual:
                try:
                    data["session"] = session
                    result = await handler(event, data)
                    await session.commit()
                    return result
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()

            else:
                async with session.begin():
                    data["session"] = session
                    return await handler(event, data)