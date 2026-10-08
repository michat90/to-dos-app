from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.schemas.user import UserCreate


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, user_create: UserCreate, hashed_password: str) -> User:
        # Tworzymy model User bezpośrednio z gotowym hashed_password (NIE wywołujemy tu hash_password!)
        user = User(
            email=user_create.email,
            hashed_password=hashed_password,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
