import smtplib
from email.message import EmailMessage
import asyncio
import csv
import io
import selectors
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.db.models.task import Task
from sqlalchemy import select


# bind=True,  # Pozwala na dostęp do kontekstu zadania (self)


@celery_app.task(
    name="send_welcome_email_task",
    auto_retry_for=(Exception,),  # Automatyczne ponawianie przy błędach SMTP
    retry_kwargs={"max_retries": 3},
    default_retry_delay=10,  # Czas w sekundach przed ponowną próbą
)
def send_welcome_email_task(user_email: str) -> str:
    # 1. Tworzymy strukturę wiadomości e-mail 📄
    msg = EmailMessage()
    msg["Subject"] = "Witaj w aplikacji To-Dos! 🚀"
    msg["From"] = settings.EMAILS_FROM_EMAIL
    msg["To"] = user_email
    msg.set_content(
        f"Cześć!\n\nDziękujemy za rejestrację w naszej aplikacji. "
        f"Twoje konto ({user_email}) jest już aktywne!\n\nPozdrawiamy,\nZespół To-Dos"
    )

    # 2. Łączymy się z serwerem SMTP i wysyłamy 📡
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()  # Szyfrowanie połączenia TLS 🔐
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)

    print(f"📧 [Celery Worker] Wysyłanie e-maila powitalnego do: {user_email}")
    return f"Email sent successfully to {user_email}"


async def _generate_tasks_csv() -> str:
    """Pobiera wszystkie zadania wraz z nazwami projektów i tworzy z nich plik CSV."""
    async with AsyncSessionLocal() as db:
        # 1. Pobieramy zadania razem z relacją 'project' 🔗
        stmt = select(Task).options(selectinload(Task.project))
        result = await db.execute(stmt)
        tasks = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)

        # 2. Nagłówki CSV 📊
        writer.writerow([
            "ID Zadania",
            "Tytuł",
            "Status",
            "Termin",
            "Ukończono",
            "ID Projektu",
            "Nazwa Projektu"
        ])

        # 3. Wiersze z danymi 📝
        for task in tasks:
            project_name = task.project.name if task.project else "Brak projektu"
            writer.writerow([
                task.id,
                task.title,
                task.status,
                task.due_date,
                task.completed_at,
                task.project_id,
                project_name
            ])

        return output.getvalue()


@celery_app.task(name="export_and_send_tasks_csv")
def export_and_send_tasks_csv(user_id: int, recipient_email: str) -> str:
    """Zadanie Celery: generuje CSV i wysyła na podany adres e-mail."""
    try:
        # 1. Generujemy CSV w trybie async z pętlą dla Windows 🪟
        csv_data = asyncio.run(
            _generate_tasks_csv(),
            loop_factory=lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector())
        )

        # 2. Tworzymy wiadomość e-mail z załącznikiem ✉️
        msg = EmailMessage()
        msg["Subject"] = "Twój raport zadań (CSV)"
        msg["From"] = settings.SMTP_USER
        msg["To"] = recipient_email
        msg.set_content(
            "Cześć! W załączniku znajdziesz wygenerowany raport ze swoimi zadaniami.")

        # Dodajemy załącznik CSV 📎
        msg.add_attachment(
            csv_data.encode("utf-8"),
            maintype="text",
            subtype="csv",
            filename=f"tasks_report_user_{user_id}.csv"
        )

        # 3. Wysyłamy przez Ethereal SMTP 🚀
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        print(
            f"📧 Wygenerowano i wysłano raport CSV dla użytkownika {user_id} na {recipient_email}")
        return f"Export sent to {recipient_email}"

    except Exception as e:
        print(f"❌ Błąd podczas generowania/wysyłania raportu: {e}")
        raise e
