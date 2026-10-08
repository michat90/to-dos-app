import asyncio
import selectors
from datetime import date
from sqlalchemy import update

from app.core.celery_app import celery_app
# 👈 Importujemy fabrykę sesji asynchronicznej
from app.db.database import AsyncSessionLocal
from app.db.models.task import Task, StatusEnum


async def _run_check_and_update_overdue_tasks() -> int:
    """Asynchroniczna funkcja wykonująca zapytanie do bazy."""
    async with AsyncSessionLocal() as db:
        today = date.today()

        # Tworzymy zapytanie UPDATE w składni SQLAlchemy 2.0
        stmt = (
            update(Task)
            .where(
                Task.due_date < today,
                Task.completed_at == None,
                Task.status != StatusEnum.OVERDUE,
            )
            .values(status=StatusEnum.OVERDUE)
        )

        result = await db.execute(stmt)
        await db.commit()

        return result.rowcount  # Zwraca liczbę zaktualizowanych wierszy


@celery_app.task(name="check_and_update_overdue_tasks")
def check_and_update_overdue_tasks() -> str:
    try:
        # Przekazujemy lambdę, która wywoła konstruktor pętli dla Windows 🪟
        updated_count = asyncio.run(
            _run_check_and_update_overdue_tasks(),
            loop_factory=lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector())
        )

        print(
            f"⚠️ [Celery Beat] Oznaczono {updated_count} zadań jako OVERDUE.")
        return f"Updated {updated_count} tasks."
    except Exception as e:
        print(f"❌ [Celery Beat] Błąd aktualizacji: {e}")
        raise e
