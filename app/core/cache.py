from typing import Optional
from redis.asyncio import Redis


class CacheInvalidator:

    def __init__(self, redis: Redis):
        self.redis = redis

    async def invalidate_user_project_cache(
        self, user_id: int, project_id: Optional[int] = None
    ) -> None:
        """Czyszczenie pamięci podręcznej projektów i zadań dla danego użytkownika."""
        # Wszystkie zapisane wyszukiwania/paginacje
        patterns = [
            f"user:{user_id}:tasks_search*",  # 🔍 Wyszukiwania zadań
            f"user:{user_id}:projects*",  # 📂 Listy projektów
        ]

        # 📌 Wszystko, co dotyczy konkretnego projektu (zadania, statystyki itp.)
        # Jeśli operacja dotyczyła konkretnego projektu, czyścimy też jego cache
        if project_id is not None:
            patterns.append(f"user:{user_id}:project:{project_id}:*")

        for pattern in patterns:
            # 1. Zbieramy wszystkie pasujące klucze do listy
            keys = [key async for key in self.redis.scan_iter(match=pattern)]
            # 2. Usuwamy je zbiorczo tylko wtedy, gdy lista nie jest pusta
            if keys:
                await self.redis.delete(*keys)
