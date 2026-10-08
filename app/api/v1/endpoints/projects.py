from fastapi import APIRouter, Depends, status, Query, Response
import redis.asyncio as aioredis
from app.core.redis import get_redis

from app.api.deps import get_current_user, get_project_service
from app.db.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, ProjectStatsResponse
from app.services.project_service import ProjectService
from app.core.rate_limits import rate_limit_global_read, rate_limit_mutations
from app.tasks.email_tasks import send_welcome_email_task
from app.schemas.email import EmailTestRequest

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post(
    "/",
    dependencies=[Depends(rate_limit_mutations)],
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    return await service.create_project(project_data, user_id=current_user.id)


@router.get(
    "/",
    dependencies=[Depends(rate_limit_global_read)],
    response_model=list[ProjectResponse])
async def get_projects(
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    return await service.get_user_projects(user_id=current_user.id)


@router.get(
    "/{project_id}",
    dependencies=[Depends(rate_limit_global_read)],
    response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    return await service.get_project_by_id(project_id, user_id=current_user.id)


@router.get(
    "/{project_id}/stats",
    dependencies=[Depends(rate_limit_global_read)],
    response_model=ProjectStatsResponse)
async def get_project_stats(
    project_id: int,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    return await service.get_project_stats(project_id=project_id, user_id=current_user.id)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    return await service.update_project(project_id, project_data, user_id=current_user.id)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    await service.delete_project(project_id, user_id=current_user.id)


@router.get("/{project_id}/stats/export")
async def export_project_stats(
    project_id: int,
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
):
    # 1. Pobieramy bajty, media_type i filename z serwisu
    content, media_type, filename = await service.export_project_stats(
        project_id=project_id,
        user_id=current_user.id,
        export_format=format
    )

    # 2. Zwracamy odpowiedź z odpowiednimi nagłówkami
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/test-email", status_code=status.HTTP_202_ACCEPTED)
async def trigger_email_task(payload: EmailTestRequest):
    # Wydelegowanie zadania do Celery za pomocą wyciągniętego adresu z Pydantica
    task = send_welcome_email_task.delay(payload.email)

    return {
        "message": "Zadanie wysłane do Celery!",
        "task_id": task.id
    }
