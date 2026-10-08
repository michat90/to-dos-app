# app/services/task_service.py
import json
from datetime import date, datetime, timezone
import redis.asyncio as aioredis
from typing import Optional, List
import math

from app.core.exceptions import NotFoundException, InvalidTaskDueDateException
from app.db.models.task import Task
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, PaginatedResponse, TaskFilterParams
from app.db.models.task import PriorityEnum, StatusEnum
from app.core.cache import CacheInvalidator
from app.core.logging import get_logger

logger = get_logger(__name__)


class TaskService:
    def __init__(self, uow: UnitOfWork, redis: aioredis.Redis):
        self.uow = uow
        self.redis = redis
        self.pubsub_channel = "task_events"
        self.cache_invalidator = CacheInvalidator(redis)

    async def _publish_event(self, event_type: str, payload: dict) -> None:
        """Pomocnicza metoda do publikowania komunikatów na kanale Redis Pub/Sub."""
        message = json.dumps({"event": event_type, "data": payload})
        # Weryfikacja: czy używasz kanału "task_events"?
        await self.redis.publish("task_events", message)

    def _build_tasks_cache_key(
        self,
        user_id: int,
        project_id: int,
        status: Optional[StatusEnum] = None,
        priority: Optional[PriorityEnum] = None,
    ) -> str:
        """Tworzy unikalny klucz cache na podstawie projektu i użytych filtrów."""
        key = f"user:{user_id}:project:{project_id}:tasks"
        if status:
            key += f":status:{status.value}"
        if priority:
            key += f":priority:{priority.value}"
        return key

    async def create_task(self, task_data: TaskCreate, user_id: int) -> Task:
        logger.info(f"Creating task for user {user_id}")
        if task_data.due_date and task_data.due_date < date.today():
            raise InvalidTaskDueDateException()

        async with self.uow:
            project = await self.uow.projects.get_by_id_and_user_id(
                task_data.project_id, user_id
            )
            if not project:
                raise NotFoundException("Project", task_data.project_id)

            # Autouzupełnienie completed_at dla ukończonych zadań
            if task_data.status == StatusEnum.DONE and not task_data.completed_at:
                task_data.completed_at = datetime.now(timezone.utc)

            task = await self.uow.tasks.create(task_data)
            response = TaskResponse.model_validate(task)

        # Invalidacja wszystkich wariantów listy zadań w tym projekcie
        await self.cache_invalidator.invalidate_user_project_cache(user_id, task_data.project_id)

        await self._publish_event(
            "task_created",
            {
                "task_id": response.id,
                "project_id": response.project_id,
                "user_id": user_id,
            },
        )

        return response

    async def get_tasks_by_project(
        self,
        project_id: int,
        user_id: int,
        status: Optional[StatusEnum] = None,
        priority: Optional[PriorityEnum] = None,
    ) -> list[TaskResponse]:
        async with self.uow:
            project = await self.uow.projects.get_by_id_and_user_id(
                project_id, user_id
            )
            if not project:
                raise NotFoundException("Project", project_id)

        cache_key = self._build_tasks_cache_key(
            user_id, project_id, status, priority
        )

        # 2. Cache HIT
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            return [TaskResponse(**item) for item in json.loads(cached_data)]

        # 3. Cache MISS - pobranie z PostgreSQL
        async with self.uow:
            tasks = await self.uow.tasks.get_all_by_project_id(
                project_id, status=status, priority=priority
            )
            response_data = [TaskResponse.model_validate(t) for t in tasks]

        # 4. Zapis do Redisa z TTL = 300 sekund (5 minut)
        serialized = json.dumps(
            [t.model_dump(mode="json") for t in response_data]
        )
        await self.redis.set(cache_key, serialized, ex=300)

        return response_data

    async def update_task(self, task_id: int, task_data: TaskUpdate, user_id: int) -> Task:
        logger.info(f"Updating task {task_id} for user {user_id}")
        async with self.uow:
            task = await self.uow.tasks.get_by_id(task_id)
            if not task:
                raise NotFoundException("Task", task_id)

            # Sprawdzenie uprawnień do projektu
            project = await self.uow.projects.get_by_id_and_user_id(
                task.project_id, user_id
            )
            if not project:
                raise NotFoundException("Task", task_id)

            # Obsługa czyszczenia/ustawiania completed_at
            if task_data.status:
                if task_data.status == StatusEnum.DONE and not task.completed_at:
                    task_data.completed_at = datetime.now(timezone.utc)
                elif task_data.status != StatusEnum.DONE:
                    task_data.completed_at = None

            updated_task = await self.uow.tasks.update(task, task_data)
            response = TaskResponse.model_validate(updated_task)

        await self.cache_invalidator.invalidate_user_project_cache(user_id, task.project_id)
        return response

    async def delete_task(self, task_id: int, user_id: int) -> None:
        async with self.uow:
            task = await self.uow.tasks.get_by_id(task_id)
            if not task:
                raise NotFoundException("Task", task_id)

            project = await self.uow.projects.get_by_id_and_user_id(
                task.project_id, user_id
            )
            if not project:
                raise NotFoundException("Task", task_id)

            project_id = task.project_id
            await self.uow.tasks.delete(task)

        await self.cache_invalidator.invalidate_user_project_cache(user_id, project_id)

    async def get_tasks(
        self, user_id: int, filters: TaskFilterParams
    ) -> PaginatedResponse[TaskResponse]:
        # Generowanie deterministycznego klucza dla pamięci podręcznej Redisa
        filters_dict = filters.model_dump(mode="json")
        filters_hash = json.dumps(filters_dict, sort_keys=True)
        cache_key = f"user:{user_id}:tasks_search:{hash(filters_hash)}"

        # 1. Próba odczytu z Redisa
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            return PaginatedResponse[TaskResponse](**data)

        # 2. Pobranie z bazy danych w bloku UnitOfWork
        async with self.uow:
            tasks, total = await self.uow.tasks.get_filtered_tasks(user_id, filters)
            task_responses = [TaskResponse.model_validate(t) for t in tasks]

        total_pages = math.ceil(total / filters.page_size) if total > 0 else 1

        response = PaginatedResponse[TaskResponse](
            items=task_responses,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
        )

        # 3. Zapis do Redisa z krótkim czasem TTL (np. 60s)
        await self.redis.set(
            cache_key, response.model_dump_json(), ex=60
        )

        return response
