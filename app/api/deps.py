from typing import AsyncGenerator
import fastapi
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.core.redis import get_redis
from app.core.config import settings
from app.core.exceptions import CredentialsException
from app.core.security import decode_access_token
from app.db.database import get_db
from app.db.models.user import User
from app.repositories.unit_of_work import UnitOfWork
from app.services.project_service import ProjectService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.token_service import TokenBlocklistService

# Definiujemy schemat OAuth2 - tokenUrl wskazuje na endpoint logowania
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# 1. Sesja bazy danych i Unit of Work
async def get_uow(
    session: AsyncSession = fastapi.Depends(get_db),
) -> AsyncGenerator[UnitOfWork, None]:
    yield UnitOfWork(session)


# 2. Serwisy domenowe
def get_user_service(
    uow: UnitOfWork = fastapi.Depends(get_uow),
) -> UserService:
    return UserService(uow=uow)


def get_project_service(
    uow: UnitOfWork = fastapi.Depends(get_uow),
    redis: aioredis.Redis = fastapi.Depends(get_redis),
) -> ProjectService:
    return ProjectService(uow=uow, redis=redis)


def get_task_service(
    uow: UnitOfWork = fastapi.Depends(get_uow),
    redis: aioredis.Redis = fastapi.Depends(get_redis),
) -> TaskService:
    return TaskService(uow=uow, redis=redis)


# 3. Zależność uwierzytelniająca: weryfikacja JWT i pobranie zalogowanego Usera
# app/api/deps.py

async def get_current_user(
    token: str = fastapi.Depends(oauth2_scheme),
    uow: UnitOfWork = fastapi.Depends(get_uow),
    redis: aioredis.Redis = fastapi.Depends(get_redis),
) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise CredentialsException(
            detail="Invalid or expired authentication token")

    # 1. Sprawdzenie czy token został unieważniony (logout) w Redisie
    jti: str | None = payload.get("jti")
    if jti:
        token_service = TokenBlocklistService(redis)
        if await token_service.is_token_blocked(jti):
            raise CredentialsException(
                detail="Token has been revoked (logged out)"
            )
    # 2. Pobranie user_id z tokena
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise CredentialsException(detail="Token missing user subject")

    try:
        # Konwersja na int dla PostgreSQL/SQLAlchemy
        user_id = int(user_id_str)
    except ValueError:
        raise CredentialsException(
            detail="Invalid user identification in token")

    async with uow:
        user = await uow.users.get_by_id(user_id)
        if not user:
            raise CredentialsException(detail="User no longer exists")

        if not user.is_active:
            raise CredentialsException(detail="User is inactive")

        return user
