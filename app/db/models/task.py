from typing import TYPE_CHECKING
from datetime import date, datetime
import enum

from app.db.database import Base
from sqlalchemy import String, DateTime, func, Enum, ForeignKey, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.db.models.project import Project


class PriorityEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class StatusEnum(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    OVERDUE = "OVERDUE"
    DONE = "DONE"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True)
    priority: Mapped[PriorityEnum] = mapped_column(
        Enum(PriorityEnum, name="priority_enum"), server_default=PriorityEnum.LOW.value, nullable=False)
    status: Mapped[StatusEnum] = mapped_column(
        Enum(StatusEnum, name="status_enum"), server_default=StatusEnum.TODO.value, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    project_id: Mapped[int] = mapped_column(ForeignKey(
        "projects.id", ondelete="CASCADE"), nullable=False)
    # above ForeignKey projects.is showing like looks connection in database

    project: Mapped["Project"] = relationship(back_populates="tasks")
    # above showing how i can access project from task and task from project,
    # so i can do task.project.name or project.tasks[0].title
    # -----------------------------------------------------
    # ondelete="CASCADE" works on the PostgreSQL level
    # -----------------------------------------------------
    # str | None when nullable=True, otherwise str
    # -----------------------------------------------------
    # Enum(StatusEnum, name="status_enum") thanks that Alembic can generate
    # the correct SQL for the enum type in PostgreSQL
