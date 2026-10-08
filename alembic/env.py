import asyncio
from logging.config import fileConfig
import sys

from alembic import context
from sqlalchemy import pool

# 1. Pobieramy engine oraz Base bezpośrednio z Twojego modułu database.py!
from app.db.database import Base, engine
from app.db.models import Project, Task, User  # Import modeli dla autogenerate

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Uruchamianie migracji w trybie offline."""
    url = str(engine.url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Uruchamia migracje na istniejącym obiekcie engine z database.py."""
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)


def run_migrations_online() -> None:
    """Uruchamianie migracji w trybie online."""
    # Ustawienie polityki pętli dla psycopg w systemie Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
