from unittest.mock import AsyncMock
import pytest

from app.core.exceptions import NotFoundException
from app.db.models.project import Project
from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectService

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_get_project_by_id_raises_not_found_exception(mock_uow, fake_redis):
    mock_uow.projects.get_by_id.return_value = None
    mock_uow.projects.get_by_id_and_user_id.return_value = None
    service = ProjectService(uow=mock_uow, redis=fake_redis)

    with pytest.raises(NotFoundException):
        await service.get_project_by_id(project_id=999, user_id=1)


async def test_create_project_calls_repository_create(mock_uow, fake_redis):
    fake_project = Project(
        id=1, user_id=1, name="New Project", description="Test Description"
    )
    mock_uow.projects.create.return_value = fake_project

    service = ProjectService(uow=mock_uow, redis=fake_redis)
    project_data = ProjectCreate(
        name="New Project", description="Test Description"
    )

    result = await service.create_project(project_data, user_id=1)

    assert result.id == 1
    assert result.name == "New Project"
    mock_uow.projects.create.assert_called_once_with(project_data, user_id=1)


async def test_delete_project_raises_exception_when_project_not_found(
    mock_uow, fake_redis
):
    mock_uow.projects.get_by_id.return_value = None
    mock_uow.projects.get_by_id_and_user_id.return_value = None
    service = ProjectService(uow=mock_uow, redis=fake_redis)

    with pytest.raises(NotFoundException):
        await service.delete_project(project_id=999, user_id=1)

    mock_uow.projects.delete.assert_not_called()


async def test_get_user_projects_caching(mock_uow, fake_redis):
    user_id = 1
    service = ProjectService(uow=mock_uow, redis=fake_redis)

    fake_project = Project(
        id=1, user_id=user_id, name="Test Cache", description="Desc"
    )
    mock_uow.projects.get_all_by_user_id.return_value = [fake_project]

    projects_first_call = await service.get_user_projects(user_id=user_id)

    assert len(projects_first_call) == 1
    assert projects_first_call[0].name == "Test Cache"

    cached_raw = await fake_redis.get(f"user:{user_id}:projects")
    assert cached_raw is not None

    projects_second_call = await service.get_user_projects(user_id=user_id)
    assert len(projects_second_call) == 1


async def test_create_project_invalidates_cache(mock_uow, fake_redis):
    user_id = 1
    fake_project = Project(
        id=1, user_id=user_id, name="New Proj", description="Desc"
    )
    mock_uow.projects.create.return_value = fake_project

    service = ProjectService(uow=mock_uow, redis=fake_redis)

    await fake_redis.set(f"user:{user_id}:projects", "[]")

    await service.create_project(
        ProjectCreate(name="New Proj"), user_id=user_id
    )

    cached_after_create = await fake_redis.get(f"user:{user_id}:projects")
    assert cached_after_create is None
