from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_create: ProjectCreate, user_id: int) -> Project:
        project = Project(
            **project_create.model_dump(),
            user_id=user_id
        )
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def get_all_by_user_id(self, user_id: int) -> Sequence[Project]:
        query = select(Project).where(Project.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_id_and_user_id(self, project_id: int, user_id: int) -> Project | None:
        """Pobiera projekt należący wyłącznie do danego użytkownika."""
        query = select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update(self, project: Project, project_update: ProjectUpdate) -> Project:
        update_data = project_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)

        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)
        await self.session.flush()
