from datetime import datetime, timezone
import jwt
import redis.asyncio as aioredis


class TokenBlocklistService:

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def block_token(self, token: str, secret_key: str, algorithm: str = "HS256") -> None:
        """Zapisuje token (jti) na czarnej liście w Redisie z czasem TTL wynoszącym pozostałą ważność tokena."""
        try:
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            jti = payload.get("jti")
            exp = payload.get("exp")

            if not jti or not exp:
                return

            now = datetime.now(timezone.utc).timestamp()
            remaining_ttl = int(exp - now)

            # Zapisujemy w Redisie tylko jeśli token nie wygasł jeszcze sam z siebie
            if remaining_ttl > 0:
                cache_key = f"token_blocklist:{jti}"
                await self.redis.set(cache_key, "blocked", ex=remaining_ttl)
        except jwt.PyJWTError:
            pass  # Jeśli token jest niepoprawny lub wygasł, nic nie musimy robić

    async def is_token_blocked(self, jti: str) -> bool:
        """Sprawdza, czy identyfikator jti znajduje się w Redisie."""
        cache_key = f"token_blocklist:{jti}"
        return bool(await self.redis.exists(cache_key))
