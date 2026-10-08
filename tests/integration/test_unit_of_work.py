import pytest
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.project import ProjectCreate

pytestmark = pytest.mark.asyncio


async def gently_with_uow(uow: UnitOfWork, project_data: ProjectCreate):
    async with uow:
        await uow.projects.create(project_data, user_id=1)
        # Jawnie wywołujemy wyjątek wewnątrz transakcji, aby przetestować rollback
        raise RuntimeError("Simulated unexpected database failure")


async def test_unit_of_work_rolls_back_on_exception(override_get_db_session):
    uow = UnitOfWork(session=override_get_db_session)
    project_data = ProjectCreate(
        name="Rollback Test Project", description="Should be rolled back")

    with pytest.raises(RuntimeError, match="Simulated unexpected database failure"):
        await gently_with_uow(uow, project_data)
