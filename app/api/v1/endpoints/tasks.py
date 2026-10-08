from fastapi import APIRouter, Depends, status, Query, BackgroundTasks
from typing import Optional

from app.api.deps import get_current_user, get_task_service
from app.db.models.user import User
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate, TaskFilterParams, PaginatedResponse
from app.services.task_service import TaskService
from app.db.models.task import PriorityEnum, StatusEnum
from app.core.rate_limits import rate_limit_global_read, rate_limit_mutations
from app.tasks.email_tasks import export_and_send_tasks_csv

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
    "/",
    dependencies=[Depends(rate_limit_mutations)],
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    return await service.create_task(task_data, user_id=current_user.id)


@router.get(
    "/project/{project_id}",
    dependencies=[Depends(rate_limit_global_read)],
    response_model=list[TaskResponse])
async def get_tasks_by_project(
    project_id: int,
    status: Optional[StatusEnum] = Query(
        None, description="Filtrowanie po statusie"),
    priority: Optional[PriorityEnum] = Query(
        None, description="Filtrowanie po priorytecie"),
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    return await service.get_tasks_by_project(
        project_id=project_id,
        user_id=current_user.id,
        status=status,
        priority=priority
    )


@router.get(
    "/{task_id}",
    dependencies=[Depends(rate_limit_global_read)],
    response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    return await service.get_task_by_id(task_id, user_id=current_user.id)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    return await service.update_task(task_id, task_data, user_id=current_user.id)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    await service.delete_task(task_id, user_id=current_user.id)


@router.get("/", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    filters: TaskFilterParams = Query(),
    current_user: User = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service),
):
    """Pobiera stronnicowaną listę zadań z opcją wyszukiwania i sortowania."""
    return await task_service.get_tasks(user_id=current_user.id, filters=filters)


@router.post("/export-csv")
def export_tasks_csv(
    recipient_email: str,
    current_user: User = Depends(get_current_user),
):
    # Zlecamy zadanie do Celery i natychmiast zwracamy odpowiedź HTTP ⚡
    export_and_send_tasks_csv.delay(
        user_id=current_user.id, recipient_email=recipient_email)

    return {"message": "Generowanie raportu rozpoczęte. Plik CSV zostanie wysłany na Twój e-mail."}
