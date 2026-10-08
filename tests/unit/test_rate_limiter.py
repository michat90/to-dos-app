from unittest.mock import MagicMock
from fastapi import HTTPException
import pytest

from app.core.rate_limits import rate_limit_register, rate_limit_mutations
from app.core.rate_limiter import RateLimiter

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_rate_limiter_allows_under_limit(fake_redis):
    limiter = RateLimiter(times=3, seconds=60)
    request = MagicMock()
    request.client.host = "192.168.1.1"
    request.url.path = "/api/v1/login"

    # Wykonujemy 3 zapytania (w granicach limitu)
    for _ in range(3):
        await limiter(request, fake_redis)


async def test_rate_limiter_blocks_over_limit(fake_redis):
    limiter = RateLimiter(times=2, seconds=60)
    request = MagicMock()
    request.client.host = "192.168.1.1"
    request.url.path = "/api/v1/login"

    await limiter(request, fake_redis)  # 1. OK
    await limiter(request, fake_redis)  # 2. OK

    # 3. Przekroczenie limitu -> Oczekujemy HTTPException 429
    with pytest.raises(HTTPException) as exc_info:
        await limiter(request, fake_redis)

    assert exc_info.value.status_code == 429


async def test_register_rate_limit_blocks_fourth_attempt(fake_redis):
    request = MagicMock()
    request.client.host = "10.0.0.1"
    request.url.path = "/api/v1/auth/register"

    # 3 dozwolone rejestracje
    for _ in range(3):
        await rate_limit_register(request, fake_redis)

    # 4 próba w ciągu godziny -> HTTP 429
    with pytest.raises(HTTPException) as exc_info:
        await rate_limit_register(request, fake_redis)

    assert exc_info.value.status_code == 429


async def test_mutations_rate_limit_blocks_31st_attempt(fake_redis):
    request = MagicMock()
    request.client.host = "10.0.0.1"
    request.url.path = "/api/v1/tasks/"

    # 30 dozwolonych utworzeń w minucie
    for _ in range(30):
        await rate_limit_mutations(request, fake_redis)

    # 31 próba -> HTTP 429
    with pytest.raises(HTTPException) as exc_info:
        await rate_limit_mutations(request, fake_redis)

    assert exc_info.value.status_code == 429
