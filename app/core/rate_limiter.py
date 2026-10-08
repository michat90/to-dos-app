from fastapi import Depends, HTTPException, Request, status
import redis.asyncio as aioredis
from app.core.redis import get_redis


class RateLimiter:

    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds

    async def __call__(
        self,
        request: Request,
        # <--- Używamy Depends wewnątrz instancji
        redis: aioredis.Redis = Depends(get_redis)
    ) -> None:
        client_ip = request.client.host if request.client else "127.0.0.1"
        key = f"rate_limit:{request.url.path}:{client_ip}"

        requests_count = await redis.incr(key)
        if requests_count == 1:
            await redis.expire(key, self.seconds)

        if requests_count > self.times:
            retry_after = await redis.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Przekroczono limit zapytań. Spróbuj ponownie za {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
