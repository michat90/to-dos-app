from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from pydantic import Field
from app.schemas.task import TaskResponse


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    user_id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProjectWithTasksResponse(ProjectResponse):
    tasks: list[TaskResponse] = []


class ProjectStatsResponse(BaseModel):
    id: int
    name: str
    total_tasks: int = 0
    completed_tasks: int = 0
    todo_tasks: int = 0
    overdue_tasks: int = 0
    completion_rate: float = 0

    model_config = ConfigDict(from_attributes=True)
