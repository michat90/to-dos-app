import json
from typing import List, Optional
import redis.asyncio as aioredis
import csv
import io
from reportlab.pdfgen import canvas

from app.core.exceptions import NotFoundException
from app.db.models.project import Project
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectStatsResponse
from app.core.logging import get_logger
from app.core.cache import CacheInvalidator


logger = get_logger(__name__)


class ProjectService:

    def __init__(self, uow: UnitOfWork, redis: aioredis.Redis):
        self.uow = uow
        self.redis = redis
        self.cache_invalidator = CacheInvalidator(redis)

    async def create_project(
        self, project_data: ProjectCreate, user_id: int
    ) -> ProjectResponse:
        async with self.uow:
            project = await self.uow.projects.create(
                project_data, user_id=user_id
            )
            response = ProjectResponse.model_validate(project)

        # INVALIDACJA CACHE (Czyszczenie starych danych z Redisa)
        # Przy nowym projekcie stary cache staje się nieaktualny
        # cache_key = f"user:{user_id}:projects"
        logger.info(f"Project created", project_id=project.id, user_id=user_id)
        await self.cache_invalidator.invalidate_user_project_cache(user_id=user_id)

        return response

    async def get_user_projects(self, user_id: int) -> List[ProjectResponse]:
        # Unikalny klucz dla cache konkretnego użytkownika
        cache_key = f"user:{user_id}:projects"

        # 1. SPRAWDZENIE CACHE (HIT)
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            # Dane w Redisie są zapisane jako string JSON -> deserializujemy do listy obiektów Pydantic
            data = json.loads(cached_data)
            return [ProjectResponse(**item) for item in data]

        # 2. CACHE MISS -> Pobranie z bazy danych PostgreSQL
        async with self.uow:
            projects = await self.uow.projects.get_all_by_user_id(user_id)
            response_data = [
                ProjectResponse.model_validate(p) for p in projects
            ]

        # 3. ZAPIS DO REDISA Z TTL (np. 300 sekund / 5 minut)
        # Seryjalizujemy listę obiektów Pydantic do ciągu JSON
        serialized_data = json.dumps(
            [p.model_dump(mode="json") for p in response_data]
        )
        await self.redis.set(cache_key, serialized_data, ex=300)

        return response_data

    async def get_project_by_id(self, project_id: int, user_id: int) -> Project:
        cache_key = f"user:{user_id}:project:{project_id}"

        # 1. Sprawdzenie Cache
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            return ProjectResponse.model_validate_json(cached_data)

        # 2. Pobranie z PostgreSQL (MISS)
        async with self.uow:
            project = await self.uow.projects.get_by_id_and_user_id(
                project_id, user_id=user_id
            )
            if not project:
                logger.warning(f"Project not found: {project_id}")
                raise NotFoundException("Project", project_id)
            response = ProjectResponse.model_validate(project)

        # 3. Zapis w Redisie
        serialized = json.dumps(response.model_dump(mode="json"))
        await self.redis.set(cache_key, serialized, ex=300)
        logger.info(f"Project found: {project.id}")
        return response

    async def update_project(
        self, project_id: int, project_data: ProjectUpdate, user_id: int
    ) -> Project:
        async with self.uow:
            project = await self.uow.projects.get_by_id_and_user_id(project_id, user_id)
            if not project:
                raise NotFoundException("Project", project_id)
            logger.info(f"Updating project: {project.id}")
            response = await self.uow.projects.update(project, project_data)
            await self.cache_invalidator.invalidate_user_project_cache(user_id=user_id, project_id=project_id)

            return response

    async def delete_project(self, project_id: int, user_id: int) -> None:
        async with self.uow:
            project = await self.uow.projects.get_by_id_and_user_id(project_id, user_id)
            if not project:
                raise NotFoundException("Project", project_id)
            logger.info(f"Deleting project: {project.id}")

            await self.uow.projects.delete(project)
            await self.cache_invalidator.invalidate_user_project_cache(user_id=user_id, project_id=project_id)

    async def get_project_stats(self, project_id: int, user_id: int) -> ProjectStatsResponse:
        cache_key = f"user:{user_id}:project:{project_id}:stats"

        # 1. Sprawdzamy, czy dane są w pamięci podręcznej Redisa
        cached_stats = await self.redis.get(cache_key)
        if cached_stats:
            return ProjectStatsResponse.model_validate_json(cached_stats)

        # 2. Jeśli nie ma w Redisie, pobieramy dane z bazy za pośrednictwem UoW
        async with self.uow:
            project = await self.uow.projects.get_by_id_and_user_id(project_id, user_id)
            if not project:
                raise NotFoundException("Project", project_id)

            raw_stats = await self.uow.tasks.get_stats_by_project_id(project_id)

        # 3. Obliczamy procent wykonanych zadań (z zabezpieczeniem przed dzieleniem przez 0)
        total = raw_stats["total_tasks"]
        completed = raw_stats["completed_tasks"]
        completion_rate = round(
            (completed / total * 100), 2) if total > 0 else 0.0

        project = await self.uow.projects.get_by_id_and_user_id(project_id, user_id)

        # 4. Tworzymy obiekt Pydantic
        stats_response = ProjectStatsResponse(
            id=project.id,
            name=project.name,
            total_tasks=total,
            completed_tasks=completed,
            todo_tasks=raw_stats["todo_tasks"],
            overdue_tasks=raw_stats["overdue_tasks"],
            completion_rate=completion_rate
        )

        # 5. Zapisujemy w Redisie z czasem TTL = 10 minut (600 sekund)
        await self.redis.set(cache_key, stats_response.model_dump_json(), ex=600)

        return stats_response

    def _generate_csv(self, stats: ProjectStatsResponse) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)

        # 1. Nagłówki
        writer.writerow([
            "project_id", "project_name", "total_tasks",
            "completed_tasks", "todo_tasks", "overdue_tasks", "completion_rate"
        ])

        # 2. Wiersz z danymi
        writer.writerow([
            stats.id,
            stats.name,
            stats.total_tasks,
            stats.completed_tasks,
            stats.todo_tasks,
            stats.overdue_tasks,
            stats.completion_rate
        ])

        return output.getvalue().encode("utf-8")

    def _generate_pdf(self, stats) -> bytes:
        # 1. Tworzymy wirtualny plik bajtowy w RAM
        buffer = io.BytesIO()

        # 2. Generujemy PDF bezpośrednio do bufora
        p = canvas.Canvas(buffer)
        p.drawString(100, 750, f"Raport dla projektu: {stats.name}")
        p.drawString(100, 730, f"Ukończone zadania: {stats.completed_tasks}")
        p.showPage()
        p.save()

        # 3. Pobieramy surowe bajty gotowego pliku PDF
        return buffer.getvalue()

    async def export_project_stats(
        self, project_id: int, user_id: int, export_format: str
    ) -> tuple[bytes, str, str]:
        # Pobieramy statystyki (z wykorzystaniem cache!)
        stats = await self.get_project_stats(project_id, user_id)

        if export_format.lower() == "csv":
            content = self._generate_csv(stats)
            media_type = "text/csv"
            filename = f"project_{project_id}_stats.csv"
        elif export_format.lower() == "pdf":
            content = self._generate_pdf(stats)
            media_type = "application/pdf"
            filename = f"project_{project_id}_stats.pdf"
        else:
            raise ValueError("Unsupported format")

        return content, media_type, filename
