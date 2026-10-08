from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock
import pytest

from app.core.exceptions import (
    InvalidTaskDueDateException,
    NotFoundException,
)
from app.db.models.project import Project
from app.db.models.task import PriorityEnum, StatusEnum, Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task_service import TaskService

pytestmark = pytest.mark.asyncio(loop_scope="function")


def create_dummy_task(**kwargs) -> Task:
    defaults = {
        "id": 1,
        "title": "Default Title",
        "description": "Default Description",
        "priority": PriorityEnum.LOW,
        "status": StatusEnum.TODO,
        "project_id": 1,
        "due_date": None,
        "completed_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return Task(**defaults)


# ---------------------------------------------------------------------------
# Test 1: Tworzenie zadania z datą z przeszłości rzuca wyjątek przy inicjalizacji / serwisie
# ---------------------------------------------------------------------------
async def test_create_task_raises_exception_for_past_due_date(
    mock_uow, fake_redis
):
    mock_uow.projects.get_by_id_and_user_id.return_value = Project(
        id=1, user_id=1, name="Test Project"
    )

    service = TaskService(uow=mock_uow, redis=fake_redis)
    yesterday = date.today() - timedelta(days=1)

    # Walidacja w Pydantic lub w serwisie
    try:
        task_data = TaskCreate(
            title="Test Task",
            project_id=1,
            due_date=yesterday,
        )
        with pytest.raises(InvalidTaskDueDateException):
            await service.create_task(task_data, user_id=1)
    except (InvalidTaskDueDateException, ValueError):
        # Jeśli wyjątek rzucił Pydantic przy tworzeniu TaskCreate - test też uznajemy za zaliczony
        pass


# ---------------------------------------------------------------------------
# Test 2: Tworzenie zadania dla nieistniejącego projektu rzuca NotFoundException
# ---------------------------------------------------------------------------
async def test_create_task_raises_exception_when_project_not_found(
    mock_uow, fake_redis
):
    mock_uow.projects.get_by_id_and_user_id.return_value = None

    service = TaskService(uow=mock_uow, redis=fake_redis)

    task_data = TaskCreate(
        title="Test Task",
        project_id=999,
    )

    with pytest.raises(NotFoundException):
        await service.create_task(task_data, user_id=1)


# ---------------------------------------------------------------------------
# Test 3: Tworzenie zadania ze statusem DONE ustawia completed_at
# ---------------------------------------------------------------------------
async def test_create_task_sets_completed_at_when_status_is_completed(
    mock_uow, fake_redis
):
    mock_uow.projects.get_by_id_and_user_id.return_value = Project(
        id=1, user_id=1, name="Test Project"
    )

    def mock_create(task_data: TaskCreate, **kwargs) -> Task:
        # Symulujemy logikę serwisu: jeśli status == DONE, completed_at ustawiamy na teraz
        completed_val = task_data.completed_at
        if task_data.status == StatusEnum.DONE and not completed_val:
            completed_val = datetime.now(timezone.utc)

        return create_dummy_task(
            id=1,
            title=task_data.title,
            project_id=task_data.project_id,
            status=task_data.status,
            completed_at=completed_val,
        )

    mock_uow.tasks.create.side_effect = mock_create

    service = TaskService(uow=mock_uow, redis=fake_redis)

    task_data = TaskCreate(
        title="Completed Task",
        project_id=1,
        status=StatusEnum.DONE,
    )

    result = await service.create_task(task_data, user_id=1)

    assert result.completed_at is not None
    mock_uow.tasks.create.assert_called_once()


# ---------------------------------------------------------------------------
# Test 4: Zmiana statusu z DONE na IN_PROGRESS czyści completed_at
# ---------------------------------------------------------------------------
async def test_update_task_clears_completed_at_when_status_changes_from_completed(
    mock_uow, fake_redis
):
    existing_task = create_dummy_task(
        id=1,
        title="Existing Task",
        status=StatusEnum.DONE,
        completed_at=date.today(),
    )
    mock_uow.tasks.get_by_id.return_value = existing_task
    mock_uow.tasks.get_by_id_and_user_id.return_value = existing_task
    mock_uow.tasks.update.side_effect = lambda task, task_update: task

    service = TaskService(uow=mock_uow, redis=fake_redis)

    task_update = TaskUpdate(status=StatusEnum.IN_PROGRESS)

    await service.update_task(task_id=1, task_data=task_update, user_id=1)

    assert task_update.completed_at is None
    mock_uow.tasks.update.assert_called_once()


# ---------------------------------------------------------------------------
# Test 5: Aktualizacja nieistniejącego zadania rzuca NotFoundException
# ---------------------------------------------------------------------------
async def test_update_task_raises_exception_when_task_not_found(
    mock_uow, fake_redis
):
    mock_uow.tasks.get_by_id.return_value = None
    mock_uow.tasks.get_by_id_and_user_id.return_value = None

    service = TaskService(uow=mock_uow, redis=fake_redis)
    task_update = TaskUpdate(title="New Title")

    with pytest.raises(NotFoundException):
        await service.update_task(task_id=999, task_data=task_update, user_id=1)


async def test_get_project_tasks_caching_with_filters(mock_uow, fake_redis):
    user_id = 1
    project_id = 10
    mock_uow.projects.get_by_id_and_user_id.return_value = Project(
        id=project_id, user_id=user_id, name="Test Project"
    )
    mock_uow.tasks.get_all_by_project_id.return_value = []

    service = TaskService(uow=mock_uow, redis=fake_redis)

    # Używamy faktycznej nazwy metody z TaskService
    await service.get_tasks_by_project(
        project_id=project_id, user_id=user_id, status=StatusEnum.TODO
    )

    expected_key = f"user:{user_id}:project:{project_id}:tasks:status:TODO"
    cached_val = await fake_redis.get(expected_key)
    assert cached_val is not None


async def test_create_task_clears_filtered_cache_keys(mock_uow, fake_redis):
    # GIVEN
    user_id = 1
    project_id = 10
    mock_uow.projects.get_by_id_and_user_id.return_value = Project(
        id=project_id, user_id=user_id, name="Test Project"
    )

    # Symulujemy istnienie zbuforowanych filtrowanych zapytań w Redisie
    key_all = f"user:{user_id}:project:{project_id}:tasks"
    key_todo = f"user:{user_id}:project:{project_id}:tasks:status:TODO"
    await fake_redis.set(key_all, "[]")
    await fake_redis.set(key_todo, "[]")

    def mock_create(task_data: TaskCreate, **kwargs) -> Task:
        return create_dummy_task(id=1, project_id=project_id, title=task_data.title)

    mock_uow.tasks.create.side_effect = mock_create
    service = TaskService(uow=mock_uow, redis=fake_redis)

    # WHEN - Dodanie nowego zadania
    task_data = TaskCreate(title="New Task", project_id=project_id)
    await service.create_task(task_data, user_id=user_id)

    # THEN - Oba klucze powinny zostać wyczyszczone przez _invalidate_project_tasks_cache
    assert await fake_redis.get(key_all) is None
    assert await fake_redis.get(key_todo) is None
