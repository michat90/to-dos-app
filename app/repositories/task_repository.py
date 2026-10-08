from datetime import datetime, timezone, date
from sqlalchemy import select
from typing import Sequence, Optional, List, Tuple
from sqlalchemy import Select, func, or_, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.task import Task, PriorityEnum, StatusEnum
from app.schemas.task import TaskCreate, TaskUpdate, SortOrder, TaskFilterParams, TaskSortBy


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.db = session

    async def get_filtered_tasks(
        self, user_id: int, filters: TaskFilterParams
    ) -> Tuple[List[Task], int]:
        """Zwraca listę pasujących zadań oraz ich całkowitą liczbę."""
        query: Select = select(Task).where(Task.user_id == user_id)

        # 1. Wyszukiwanie po frazie (Case-insensitive ILIKE)
        if filters.search:
            search_pattern = f"%{filters.search.strip()}%"
            query = query.where(
                or_(
                    Task.title.ilike(search_pattern),
                    Task.description.ilike(search_pattern),
                )
            )

        # 2. Filtrowanie po polach dyskretnych
        if filters.status:
            query = query.where(Task.status == filters.status)
        if filters.priority:
            query = query.where(Task.priority == filters.priority)
        if filters.project_id:
            query = query.where(Task.project_id == filters.project_id)
        if filters.due_date_from:
            query = query.where(Task.due_date >= filters.due_date_from)
        if filters.due_date_to:
            query = query.where(Task.due_date <= filters.due_date_to)

        # 3. Zliczanie wszystkich pasujących wyników (przed paginacją)
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # 4. Sortowanie
        sort_column = getattr(Task, filters.sort_by.value)
        if filters.sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # 5. Paginacja (OFFSET / LIMIT)
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)

        result = await self.session.execute(query)
        tasks = list(result.scalars().all())

        return tasks, total

    async def get_by_id(self, task_id: int) -> Task | None:
        query = select(Task).where(Task.id == task_id)
        return (await self.db.execute(query)).scalar_one_or_none()

    async def create(self, task_create: TaskCreate) -> Task:
        new_task = Task(**task_create.model_dump())
        self.db.add(new_task)
        await self.db.flush()  # Używamy flush zamiast commit, aby pobrać wygenerowane ID (np. new_task.id), pozostawiając transakcję otwartą dla Unit of Work!
        await self.db.refresh(new_task)
        return new_task

    async def get_all_by_project_id(
        self,
        project_id: int,
        status: Optional[StatusEnum] = None,
        priority: Optional[PriorityEnum] = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> Sequence[Task]:
        query = select(Task).where(Task.project_id == project_id)

        if status is not None:
            query = query.where(Task.status == status)
        if priority is not None:
            query = query.where(Task.priority == priority)

        # 3. Dynamiczne sortowanie
        # Mapujemy nazwę kolumny w postaci stringa na pole modelu SQLAlchemy
        sort_column = getattr(Task, sort_by, Task.created_at)

        if order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # 4. Wykonanie zapytania
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update(self, task: Task, task_update: TaskUpdate) -> Task:
        for field, value in task_update.model_dump(exclude_unset=True).items():
            setattr(task, field, value)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def delete(self, task: Task) -> None:
        await self.db.delete(task)
        await self.db.commit()

    async def get_stats_by_project_id(self, project_id: int) -> dict:
        """Pobiera skumulowane statystyki zadań dla danego projektu."""
        today = date.today()

        stmt = select(
            func.count(Task.id).label("total_tasks"),
            func.count(
                case((Task.status == StatusEnum.DONE, Task.id))
            ).label("completed_tasks"),
            func.count(
                case((Task.status != StatusEnum.DONE, Task.id))
            ).label("todo_tasks"),
            func.count(
                case(((Task.status != StatusEnum.DONE)
                     & (Task.due_date < today), Task.id))
            ).label("overdue_tasks")
        ).where(Task.project_id == project_id)

        result = await self.db.execute(stmt)
        row = result.mappings().one()
        return dict(row)
