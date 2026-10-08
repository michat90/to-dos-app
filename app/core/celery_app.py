
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings


celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    imports=["app.tasks.email_tasks", "app.tasks.maintenance_tasks"],
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

'''celery_app.conf.beat_schedule = {
    "check-overdue-tasks-every-15-sec": {
        "task": "check_and_update_overdue_tasks",
        "schedule": 15.0,  # Co 15 sekund
    },
}'''

celery_app.conf.beat_schedule = {
    # Zadanie uruchamiane raz na dobę o północy 🌙
    "check-overdue-tasks-daily": {
        "task": "check_and_update_overdue_tasks",
        "schedule": crontab(hour=0, minute=0),
    },

    # Alternatywnie: jeśli wolisz, żeby uruchamiało się co godzinę o pełnej godzinie ⏰:
    # "check-overdue-tasks-hourly": {
    #     "task": "check_and_update_overdue_tasks",
    #     "schedule": crontab(minute=0, hour="*"),
    # },
}

# Automatycznie wykrywaj zadania w module app.tasks
celery_app.autodiscover_tasks(["app.tasks"])
