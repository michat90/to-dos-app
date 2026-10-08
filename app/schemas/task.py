from enum import Enum
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from pydantic import Field
from app.db.models.task import PriorityEnum, StatusEnum

T = TypeVar("T")


class TaskSortBy(str, Enum):
    CREATED_AT = "created_at"
    DUE_DATE = "due_date"
    PRIORITY = "priority"
    TITLE = "title"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class TaskFilterParams(BaseModel):
    search: Optional[str] = Field(
        None, description="Szukana fraza w tytule lub opisie")
    status: Optional[StatusEnum] = None
    priority: Optional[PriorityEnum] = None
    project_id: Optional[int] = None
    due_date_from: Optional[date] = None
    due_date_to: Optional[date] = None

    sort_by: TaskSortBy = TaskSortBy.CREATED_AT
    sort_order: SortOrder = SortOrder.DESC

    page: int = Field(1, ge=1, description="Numer strony")
    page_size: int = Field(
        20, ge=1, le=100, description="Liczba elementów na stronę")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    priority: PriorityEnum = PriorityEnum.LOW
    status: StatusEnum = StatusEnum.TODO
    due_date: date | None = None


class TaskCreate(TaskBase):
    # completed_at: datetime | None = None
    project_id: int


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: PriorityEnum | None = None
    status: StatusEnum | None = None
    due_date: date | None = None
    project_id: int | None = None
    completed_at: datetime | None = None


class TaskResponse(TaskBase):
    id: int
    project_id: int
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
