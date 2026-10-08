from typing import TYPE_CHECKING, List
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.db.models.task import Task
    from app.db.models.user import User


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 1. Definicja Klucza Obcego (ForeignKey) wskazującego na tabelę 'users' i pole 'id'
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 2. Relacja z odebraniem obiektywnie właściciela (User)
    owner: Mapped["User"] = relationship("User", back_populates="projects")

    # Dotychczasowa relacja z zadaniami
    tasks: Mapped[List["Task"]] = relationship(
        "Task", back_populates="project", cascade="all, delete-orphan"
    )

    # cascade="all, delete-orphan" works on the SQLAlchemy level, ensuring that when a Project is deleted,
    # all associated Tasks are also deleted.

    # relationship() allows SQLAlchemy to manage the association between objects,
    # while ForeignKey tells it how to persist that association in the database.
