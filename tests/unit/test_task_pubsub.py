# tests/unit/test_task_pubsub.py
import json
from unittest.mock import AsyncMock
import pytest

from app.schemas.task import PriorityEnum, StatusEnum, TaskCreate
from app.services.task_service import TaskService

pytestmark = pytest.mark.asyncio(loop_scope="function")


# Asynchroniczny generator symulujący brak kluczy w scan_iter
async def mock_scan_iter(*args, **kwargs):
    if False:
        yield


async def test_create_task_publishes_pubsub_event(mock_uow):
    # GIVEN
    mock_redis = AsyncMock()
    # Kluczowa zmiana: scan_iter zwraca generator, a nie coroutine
    mock_redis.scan_iter = mock_scan_iter

    service = TaskService(uow=mock_uow, redis=mock_redis)

    # Moki dla projektu oraz zadania
    mock_uow.projects.get_by_id_and_user_id.return_value = AsyncMock()

    mock_task = AsyncMock()
    mock_task.id = 101
    mock_task.project_id = 5
    mock_task.title = "Nowe zadanie z PubSub"
    mock_task.description = None
    mock_task.due_date = None
    mock_task.completed_at = None
    mock_task.status = StatusEnum.TODO
    mock_task.priority = PriorityEnum.HIGH
    mock_uow.tasks.create.return_value = mock_task

    task_in = TaskCreate(
        title="Nowe zadanie z PubSub",
        project_id=5,
        status=StatusEnum.TODO,
        priority=PriorityEnum.HIGH,
    )

    # WHEN
    await service.create_task(task_data=task_in, user_id=1)

    # THEN - Sprawdzamy, czy publish zostało wywołane na obiekcie mock_redis
    assert mock_redis.publish.called, "Metoda redis.publish nie została wywołana!"

    args, _ = mock_redis.publish.call_args
    channel, raw_message = args[0], args[1]

    assert channel == "task_events"

    data = json.loads(raw_message)
    assert data["event"] == "task_created"
    assert data["data"]["task_id"] == 101
    assert data["data"]["user_id"] == 1
