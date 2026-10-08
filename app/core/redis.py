# app/core/redis.py
from typing import AsyncGenerator
import redis.asyncio as aioredis
from app.core.config import settings

# 1. Connection Pool (Pula połączeń)
# Zamiast otwierać nowe połączenie TCP przy każdym żądaniu HTTP,
# trzymamy pulę otwartych gniazd, które są ponownie wykorzystywane.
redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    # Automatycznie dekoduje odpowiedzi z bajtów na stringi (str)
    decode_responses=True,
    max_connections=10
)


# 2. Zależność FastAPI (Dependency Injection)
async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """
    Dostarcza instancję klienta Redis dla pojedynczego żądania HTTP.
    Po zakończeniu żądania automatycznie zwraca połączenie do puli.
    """
    client = aioredis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.aclose()
