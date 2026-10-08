from app.core.exceptions import InvalidCredentialsException, UserAlreadyExistsException
from app.core.logging import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.user import Token, UserCreate

logger = get_logger(__name__)


class UserService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def register_user(self, user_data: UserCreate) -> User:
        async with self.uow:
            existing_user = await self.uow.users.get_by_email(user_data.email)
            if existing_user:
                raise UserAlreadyExistsException(user_data.email)

            # 1. Haszujemy tylko TUTAJ
            hashed_pwd = hash_password(user_data.password)

            # 2. Przekazujemy gotowy hash do repozytorium
            user = await self.uow.users.create(user_data, hashed_password=hashed_pwd)
            logger.info("User registered successfully",
                        user_id=user.id, email=user.email)
            return user

    async def authenticate_user(self, email: str, password: str) -> Token:
        async with self.uow:
            user = await self.uow.users.get_by_email(email)
            if not user or not verify_password(password, user.hashed_password):
                raise InvalidCredentialsException()

            if not user.is_active:
                raise InvalidCredentialsException()

            # Tworzymy payload tokenu (sub z reguły zawiera ID użytkownika przekonwertowany na string)
            access_token = create_access_token(data={"sub": str(user.id)})

            logger.info("User logged in successfully", user_id=user.id)
            return Token(access_token=access_token, token_type="bearer")
