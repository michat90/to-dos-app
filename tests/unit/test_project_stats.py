import pytest
from unittest.mock import AsyncMock, MagicMock
from app.schemas.project import ProjectStatsResponse
from app.services.project_service import ProjectService
from app.core.exceptions import NotFoundException
from app.core.cache import CacheInvalidator
from app.db.models.project import Project

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_get_project_stats_cache_hit_and_miss(mock_uow, fake_redis):
    project_service = ProjectService(uow=mock_uow, redis=fake_redis)
    # 1. ARRANGE - Przygotowanie danych i mocków
    project_id = 1
    user_id = 10
    cache_key = f"user:{user_id}:project:{project_id}:stats"

    # Symulujemy brak danych w Redisie przy pierwszym wywołaniu (Cache Miss)
    cache = CacheInvalidator(redis=fake_redis)
    await cache.invalidate_user_project_cache(user_id=user_id, project_id=project_id)

    # Symulujemy projekt i wynik z bazy danych
    mock_uow.projects.get_by_id_and_user_id.return_value = Project(
        id=project_id, user_id=user_id, name="Test Project"
    )
    mock_uow.tasks.get_stats_by_project_id.return_value = {
        "id": project_id,
        "name": "Test Project",
        "total_tasks": 3,
        "completed_tasks": 1,
        "todo_tasks": 1,
        "overdue_tasks": 1
    }

    # 2. ACT (Pierwsze wywołanie - Cache Miss)
    stats_1 = await project_service.get_project_stats(project_id, user_id)

    # 3. ACT (Drugie wywołanie - Cache Hit)
    stats_2 = await project_service.get_project_stats(project_id, user_id)

    # 4. ASSERT - Sprawdzamy zachowanie
    assert stats_1.total_tasks == 3
    assert stats_1.completion_rate == 33.33

    # Upewniamy się, że do bazy danych sięgnęliśmy TYLKO RAZ!
    assert mock_uow.tasks.get_stats_by_project_id.call_count == 1

    # Upewniamy się, że do Redisa zapisaliśmy wynik za pierwszym razem
    cached_val = await fake_redis.get(cache_key)
    assert cached_val is not None


async def test_get_project_stats_project_not_found(mock_uow, fake_redis):
    project_service = ProjectService(uow=mock_uow, redis=fake_redis)
    # 1. ARRANGE - Symulujemy brak projektu w bazie
    mock_uow.projects.get_by_id_and_user_id.return_value = None

    # 2. ACT & 3. ASSERT - Sprawdzamy, czy wywołanie zgłosi oczekiwany wyjątek
    with pytest.raises(NotFoundException):
        await project_service.get_project_stats(project_id=999, user_id=1)


async def test_export_project_stats_csv_success(mock_uow, fake_redis):
    # 1. ARRANGE - przygotowujemy mocki i dane wejściowe
    project_id = 1
    user_id = 1
    service = ProjectService(uow=mock_uow, redis=fake_redis)
    mock_uow.projects.get_by_id_and_user_id.return_value = Project(
        id=project_id, user_id=user_id, name="Test Project")

    mock_stats = ProjectStatsResponse(
        id=project_id,
        name="Test Project",
        total_tasks=5,
        completed_tasks=2,
        todo_tasks=3,
        overdue_tasks=1,
        completion_rate=40.0
    )
    # Mockujemy get_project_stats, aby nie odwoływać się do bazy/Redisa
    service.get_project_stats = AsyncMock(return_value=mock_stats)

    # 2. ACT - wywołujemy eksport dla CSV
    content, media_type, filename = await service.export_project_stats(
        project_id=project_id, user_id=10, export_format="csv"
    )

    # 3. ASSERT - sprawdzamy nagłówki i treść
    assert media_type == "text/csv"
    assert filename == f"project_{project_id}_stats.csv"

    # Decodujemy bajty na tekst, aby sprawdzić zawartość CSV
    csv_text = content.decode("utf-8")
    assert "project_id,project_name,total_tasks" in csv_text
    assert "1,Test Project,5,2,3,1,40.0" in csv_text


async def test_export_project_stats_invalid_format_raises_error(mock_uow, fake_redis):
    service = ProjectService(uow=mock_uow, redis=fake_redis)
    service.get_project_stats = AsyncMock(return_value=MagicMock())

    # Sprawdzamy, czy dla nieznanego formatu rzucany jest wyjątek
    with pytest.raises(ValueError, match="Unsupported format"):
        await service.export_project_stats(
            project_id=1, user_id=10, export_format="invalid_fmt"
        )
