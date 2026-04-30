import httpx
from bot.config import settings

client = httpx.AsyncClient(
    base_url=settings.BASE_URL,
    timeout=5.0,
)
