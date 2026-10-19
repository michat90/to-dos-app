from unittest.mock import patch
import pytest
from celery.exceptions import Retry
from app.tasks.email_tasks import export_and_send_tasks_csv


@patch("app.tasks.email_tasks._generate_tasks_csv")
def test_export_and_send_tasks_csv_success(mock_generate_csv, override_get_db_session, test_user):
    """Testuje poprawne wygenerowanie i wysłanie raportu CSV z zamokowaną bazą danych."""
    mock_generate_csv.return_value = "id,title,status\n1,Test Task,Pending"

    result = export_and_send_tasks_csv.delay(
        user_id=test_user.id,
        recipient_email=test_user.email
    )

    # Sprawdzamy, czy funkcja została wywołana 🔍
    mock_generate_csv.assert_called_once()

    # Sprawdzamy wynik zadania 🎯
    assert result.status == "SUCCESS"


@patch("app.tasks.email_tasks._generate_tasks_csv")
def test_export_and_send_tasks_csv_user_not_found(mock_generate_csv, override_get_db_session):
    """Testuje zachowanie zadania, gdy funkcja wygeneruje błąd."""
    mock_generate_csv.side_effect = ValueError("Użytkownik nie istnieje")

    # Celery obsługuje błąd i zgłasza Retry 🔄
    with pytest.raises(Retry):
        export_and_send_tasks_csv.delay(
            user_id=99999,
            recipient_email="test@example.com"
        )
