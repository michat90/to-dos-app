from typing import Self
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository


class UnitOfWork:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def __aenter__(self) -> Self:
        self.users = UserRepository(self.session)
        # Rejestrujemy repozytorium na tej samej sesji transakcyjnej
        self.projects = ProjectRepository(self.session)
        self.tasks = TaskRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            # W przypadku dowolnego wyjątku w bloku async with — wycofaj zmiany
            await self.rollback()
        else:
            # Jeśli brak błędów — zatwierdź transakcję
            await self.commit()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
