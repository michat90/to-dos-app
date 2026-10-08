from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
import redis.asyncio as aioredis

from app.api.deps import oauth2_scheme
from app.api.deps import get_current_user, get_user_service
from app.db.models.user import User
from app.schemas.user import Token, UserCreate, UserResponse
from app.services.user_service import UserService
from app.core.rate_limits import rate_limit_register, login_rate_limiter
from app.core.redis import get_redis
from app.core.config import settings
from app.services.token_service import TokenBlocklistService

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# 1. Endpoint Rejestracji Użytkownika
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    dependencies=[Depends(rate_limit_register)],
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register_user(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service),
) -> User:
    """
    Tworzy nowe konto użytkownika.
    - Sprawdza unikalność adresu e-mail.
    - Haszuje hasło algorytmem bcrypt przed zapisaniem do bazy.
    - Zwraca dane utworzonego użytkownika (bez hasła).
    """
    return await user_service.register_user(user_data)


# ---------------------------------------------------------------------------
# 2. Endpoint Logowania (Wydanie Tokena JWT)
# ---------------------------------------------------------------------------
@router.post(
    "/login",
    dependencies=[Depends(login_rate_limiter)],
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Login and retrieve access token",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_service: UserService = Depends(get_user_service),
) -> Token:
    """
    Loguje użytkownika i zwraca token Bearer JWT.

    Uwaga: OAuth2PasswordRequestForm wymaga przesłania danych w formacie
    'application/x-www-form-urlencoded' z polami:
    - **username**: adres e-mail użytkownika
    - **password**: surowe hasło
    """
    # w OAuth2PasswordRequestForm pole 'username' przenosi nasz adres e-mail
    return await user_service.authenticate_user(
        email=form_data.username,
        password=form_data.password,
    )


# ---------------------------------------------------------------------------
# 3. Endpoint "Profilu" - Weryfikacja działania get_current_user
# ---------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current logged in user details",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Zwraca szczegóły aktualnie zalogowanego użytkownika na podstawie podanego tokena JWT.
    """
    return current_user


@router.post("/logout", status_code=200)
async def logout(
    token: str = Depends(oauth2_scheme),
    redis: aioredis.Redis = Depends(get_redis),
):
    token_service = TokenBlocklistService(redis)
    await token_service.block_token(token, secret_key=settings.SECRET_KEY)
    return {"message": "Successfully logged out"}
