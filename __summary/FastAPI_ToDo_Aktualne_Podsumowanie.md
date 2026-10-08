# FastAPI To-Do List — aktualne podsumowanie projektu

## Cel projektu

Budujemy backendową aplikację **To-Do List** w Pythonie, FastAPI, PostgreSQL, Dockerze, SQLAlchemy 2.x, Pydantic Settings i Alembic.

Projekt jest edukacyjny i portfolio. Pracujemy krok po kroku: użytkownik sam pisze kod, a następnie robimy wspólne code/design review.

## Funkcjonalności

Aplikacja ma umożliwiać:
- tworzenie projektów,
- tworzenie zadań,
- grupowanie zadań w projekty,
- sortowanie według priorytetu,
- ustawianie terminów,
- oznaczanie zadań jako wykonane,
- przenoszenie niewykonanych zadań na inny dzień,
- filtrowanie,
- obsługę zadań na dziś i zaległych.

Podstawowe encje: `Project` i `Task`.

## PostgreSQL + Docker

PostgreSQL działa w Dockerze w kontenerze `fastapi-postgres`, z portem `5432`.

Używana baza projektu:
- użytkownik: `myuser`
- baza: `todo_db`

Istnieje volume z danymi — nie należy używać `docker compose down -v` bez upewnienia się, że dane nie zostaną utracone.

FastAPI jest obecnie uruchamiane lokalnie, a PostgreSQL w Dockerze:

```text
Visual Studio
    ↓
FastAPI
    ↓
127.0.0.1:5432
    ↓
Docker
    ↓
PostgreSQL
```

## `.env`

`.env` znajduje się w katalogu głównym projektu, nie w `.venv`, i jest dodany do `.gitignore`.

```text
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
DATABASE_USER=myuser
DATABASE_PASSWORD=...
DATABASE_NAME=todo_db
```

Hasło nie powinno być publikowane ani commitowane do GitHuba.

## Pydantic Settings

Mamy `app/core/config.py`.

Logicznie:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str

settings = Settings()
```

## SQLAlchemy

Mamy `app/db/database.py`.

Znajdują się tam:
- `DATABASE_URL`,
- `engine`,
- `SessionLocal`,
- `Base`,
- `get_db()`.

Połączenie zostało sprawdzone przez:

```python
with engine.connect() as connection:
    result = connection.execute(text("SELECT 1"))
    print(result.fetchone())
```

Wynik:

```text
(1,)
```

Połączenie SQLAlchemy → PostgreSQL działa.

## Struktura projektu

```text
app/
├── main.py
├── core/
│   └── config.py
├── db/
│   ├── database.py
│   ├── base.py
│   └── models/
│       ├── __init__.py
│       ├── project.py
│       └── task.py
├── schemas/
│   ├── project.py
│   └── task.py
├── api/
├── repositories/
└── services/
```

`models` jest osobnym pakietem z plikami `project.py` i `task.py`.

W `models/__init__.py` importujemy modele:

```python
from app.db.models.project import Project
from app.db.models.task import Task
```

## Circular imports i `TYPE_CHECKING`

Ponieważ `Project` zna `Task`, a `Task` zna `Project`, pojawił się problem circular imports.

Rozwiązujemy go przez:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.project import Project
```

i analogicznie w drugim modelu.

To rozwiązanie obecnie działa.

# Model Project

Pola:

| Pole | Typ | Znaczenie |
|---|---|---|
| `id` | Integer | Primary Key |
| `name` | VARCHAR(100) | nazwa projektu |
| `description` | VARCHAR(1000), NULL | opcjonalny opis |
| `created_at` | timestamp | data utworzenia |
| `updated_at` | timestamp | data ostatniej zmiany |

Tabela:

```text
projects
```

# Model Task

Pola:

| Pole | Typ | Znaczenie |
|---|---|---|
| `id` | Integer | Primary Key |
| `title` | VARCHAR(100) | nazwa zadania |
| `description` | VARCHAR(1000), NULL | opcjonalny opis |
| `priority` | Enum | `LOW`, `MEDIUM`, `HIGH` |
| `status` | Enum | `TO_DO`, `IN_PROGRESS`, `DONE` |
| `due_date` | DATE, NULL | termin wykonania |
| `completed_at` | timestamp, NULL | ostatni moment ukończenia |
| `created_at` | timestamp | data utworzenia |
| `updated_at` | timestamp | data ostatniej zmiany |
| `project_id` | Integer | FK do `projects.id` |

Tabela:

```text
tasks
```

## `due_date`

Wybraliśmy `DATE`, ponieważ wymaganiem jest możliwość przeniesienia zadania na inny dzień. Na pierwszym etapie nie przechowujemy historii poprzednich terminów.

Przykład:

```text
2026-09-05
    ↓
2026-09-07
```

## Priorytet

Wybraliśmy enum:

```text
LOW
MEDIUM
HIGH
```

Jest czytelniejszy niż wartości liczbowe.

## Status

Aktualnie:

```text
TO_DO
IN_PROGRESS
DONE
```

Można później rozważyć zmianę `TO_DO` na `TODO`, ale oba warianty są technicznie poprawne.

## `completed_at`

Reguły biznesowe:

```text
TO_DO
    completed_at = NULL

IN_PROGRESS
    completed_at = NULL

DONE
    completed_at = CURRENT_TIMESTAMP
```

Przejście `DONE → IN_PROGRESS/TO_DO` ustawia `completed_at` na `NULL`.

Ponowne przejście do `DONE` ustawia nowy timestamp.

`completed_at` oznacza ostatni moment ukończenia, a nie historię wszystkich ukończeń.

## `created_at` i `updated_at`

Timestampy mają być tworzone przez PostgreSQL, dlatego używamy:

```python
server_default=func.now()
```

`server_default` działa przy INSERT. Samo `server_default` nie aktualizuje `updated_at` podczas UPDATE.

Później stworzymy PostgreSQL trigger, który będzie ustawiał:

```text
updated_at = CURRENT_TIMESTAMP
```

przy zmianie rekordu.

# Relacja Project → Task

Relacja:

```text
Project 1 ─────────── N Task
```

W bazie:

```python
project_id = mapped_column(
    ForeignKey("projects.id", ondelete="CASCADE"),
    nullable=False
)
```

## `ForeignKey` vs `relationship`

`ForeignKey` opisuje relację na poziomie bazy:

```python
project_id = mapped_column(
    ForeignKey("projects.id")
)
```

`relationship()` opisuje relację pomiędzy obiektami ORM:

```python
project = relationship(...)
```

Czyli:

```text
PostgreSQL
    ↓
ForeignKey
    ↓
project_id

Python / SQLAlchemy ORM
    ↓
relationship()
    ↓
task.project / project.tasks
```

## Aktualne `relationship()`

W `Task`:

```python
project: Mapped["Project"] = relationship(
    back_populates="tasks"
)
```

W `Project`:

```python
tasks: Mapped[list["Task"]] = relationship(
    back_populates="project",
    cascade="all, delete-orphan"
)
```

`back_populates` wskazuje nazwę atrybutu po drugiej stronie relacji:

```text
Task.project
       ↕
Project.tasks
```

## Cascade

Mamy dwa mechanizmy:

```python
cascade="all, delete-orphan"
```

po stronie SQLAlchemy ORM oraz:

```python
ondelete="CASCADE"
```

po stronie PostgreSQL.

Są to mechanizmy działające na różnych poziomach.

# Aktualny eksperyment

Sprawdzamy:

```python
project = Project(name="Remont")
task = Task(title="Kupić farbę")

project.tasks.append(task)
```

oraz:

```python
task.project = project
```

Celem jest zrozumienie, jak `back_populates` synchronizuje obie strony relacji.

Wcześniej przewidzieliśmy, że:

```python
task.project is project
```

po `project.tasks.append(task)` powinno być `True`.

Następnie sprawdzamy odwrotny kierunek:

```python
task.project = project
print(project.tasks)
```

# Co zostało zrobione

- [x] PostgreSQL
- [x] Docker
- [x] volume
- [x] `.env`
- [x] `.gitignore`
- [x] Pydantic Settings
- [x] SQLAlchemy Engine
- [x] SessionLocal
- [x] `get_db()`
- [x] sprawdzenie połączenia z PostgreSQL
- [x] model `Project`
- [x] model `Task`
- [x] typy kolumn
- [x] FK `Task → Project`
- [x] `TYPE_CHECKING`
- [x] `models/__init__.py`
- [x] podstawowe `relationship()`
- [x] `back_populates`

# Roadmap

```text
Sprint 1 — Fundamenty
Sprint 2 — Project
Sprint 3 — Task
Sprint 4 — Logika biznesowa
Sprint 5 — Jakość
```

Obecnie jesteśmy na przejściu między fundamentami/modelami a Sprintem 2.

Nie przechodzimy jeszcze do endpointów. Najpierw dopracowujemy modele i migracje.

# Zadania TERAZ

## 1. Dokończyć `relationship()`

Zrozumieć i przetestować:

```python
project.tasks.append(task)
```

vs.

```python
task.project = project
```

oraz synchronizację:

```text
Project.tasks
       ↕
Task.project
```

## 2. Dopracować modele

Sprawdzić:
- `date` vs `Date`,
- `datetime` vs `DateTime` w `Mapped`,
- enumy,
- `nullable`,
- `server_default`,
- `ForeignKey`,
- `cascade`.

Następnie zrobić pełny code/design review modeli.

## 3. `updated_at`

Stworzyć PostgreSQL trigger automatycznie aktualizujący `updated_at`.

## 4. Alembic

Po zakończeniu modeli:

```text
SQLAlchemy Models
       ↓
Alembic
       ↓
migration
       ↓
PostgreSQL
```

Zrobimy pierwszą migrację i nauczymy się działania Alembic.

## 5. Pydantic schemas

Następnie przejść do:

```text
app/schemas/
├── project.py
└── task.py
```

i utworzyć m.in.:

```text
ProjectCreate
ProjectUpdate
ProjectResponse

TaskCreate
TaskUpdate
TaskResponse
```

Przy okazji rozdzielimy:

```text
SQLAlchemy Model
        ≠
Pydantic Schema
```

# Najbliższy następny krok

Wracamy do eksperymentu:

```python
project = Project(name="Remont")
task = Task(title="Kupić farbę")

task.project = project

print(project.tasks)
```

Pytanie:

**Czy `project.tasks` będzie zawierało `task` po wykonaniu `task.project = project`?**

Od tego zaczynamy następną lekcję o `back_populates`, a następnie przechodzimy do `Session`, `flush()` i `commit()`.
