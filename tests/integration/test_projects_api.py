import pytest
from fastapi import status
from httpx import AsyncClient
from datetime import datetime, timedelta, timezone, date


pytestmark = pytest.mark.asyncio


# Helper do szybkiego tworzenia i logowania użytkowników w testach
async def create_authenticated_client(client: AsyncClient, email: str, password: str = "Password123!") -> dict:
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestProjectsAPI:

    async def test_create_project_success(self, client: AsyncClient):
        headers = await create_authenticated_client(client, "owner@example.com")
        payload = {"name": "Projekt Testowy", "description": "Opis projektu"}

        response = await client.post("/api/v1/projects/", json=payload, headers=headers)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["description"] == payload["description"]
        assert "id" in data

    async def test_get_user_projects_isolation(self, client: AsyncClient):
        # 1. Tworzymy dwóch niezależnych użytkowników
        headers_user_a = await create_authenticated_client(client, "usera@example.com")
        headers_user_b = await create_authenticated_client(client, "userb@example.com")

        # 2. Użytkownik A tworzy swój projekt
        await client.post(
            "/api/v1/projects/",
            json={"name": "Projekt Użytkownika A",
                  "description": "Tylko dla A"},
            headers=headers_user_a
        )

        # 3. Użytkownik B pobiera listę swoich projektów (powinna być pusta)
        response_b = await client.get("/api/v1/projects/", headers=headers_user_b)
        assert response_b.status_code == status.HTTP_200_OK
        assert len(response_b.json()) == 0

        # 4. Użytkownik A pobiera listę swoich projektów (powinien mieć 1 projekt)
        response_a = await client.get("/api/v1/projects/", headers=headers_user_a)
        assert response_a.status_code == status.HTTP_200_OK
        assert len(response_a.json()) == 1
        assert response_a.json()[0]["name"] == "Projekt Użytkownika A"

    async def test_get_project_by_id_forbidden_for_other_user(self, client: AsyncClient):
        headers_user_a = await create_authenticated_client(client, "owner_a@example.com")
        headers_user_b = await create_authenticated_client(client, "attacker_b@example.com")

        # Użytkownik A tworzy projekt
        create_res = await client.post(
            "/api/v1/projects/",
            json={"name": "Tajny Projekt A"},
            headers=headers_user_a
        )
        project_id = create_res.json()["id"]

        # Użytkownik B próbuje pobrać projekt Użytkownika A po ID (powinien otrzymać 404 Not Found)
        response_b = await client.get(f"/api/v1/projects/{project_id}", headers=headers_user_b)
        assert response_b.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_project_isolation(self, client: AsyncClient):
        headers_user_a = await create_authenticated_client(client, "user_a_upd@example.com")
        headers_user_b = await create_authenticated_client(client, "user_b_upd@example.com")

        # Użytkownik A tworzy projekt
        create_res = await client.post(
            "/api/v1/projects/",
            json={"name": "Oryginalna Nazwa"},
            headers=headers_user_a
        )
        project_id = create_res.json()["id"]

        # Użytkownik B próbuje zaktualizować projekt A
        update_payload = {"name": "Zhakowana Nazwa"}
        response_b = await client.put(
            f"/api/v1/projects/{project_id}",
            json=update_payload,
            headers=headers_user_b
        )
        assert response_b.status_code == status.HTTP_404_NOT_FOUND

        # Użytkownik A aktualizuje swój projekt (sukces)
        response_a = await client.put(
            f"/api/v1/projects/{project_id}",
            json=update_payload,
            headers=headers_user_a
        )
        assert response_a.status_code == status.HTTP_200_OK
        assert response_a.json()["name"] == "Zhakowana Nazwa"

    async def test_delete_project_isolation(self, client: AsyncClient):
        headers_user_a = await create_authenticated_client(client, "user_a_del@example.com")
        headers_user_b = await create_authenticated_client(client, "user_b_del@example.com")

        create_res = await client.post(
            "/api/v1/projects/",
            json={"name": "Projekt do usunięcia"},
            headers=headers_user_a
        )
        project_id = create_res.json()["id"]

        # Próba usunięcia przez Użytkownika B (odrzucona)
        del_res_b = await client.delete(f"/api/v1/projects/{project_id}", headers=headers_user_b)
        assert del_res_b.status_code == status.HTTP_404_NOT_FOUND

        # Usunięcie przez właściciela (Użytkownik A)
        del_res_a = await client.delete(f"/api/v1/projects/{project_id}", headers=headers_user_a)
        assert del_res_a.status_code == status.HTTP_204_NO_CONTENT

    async def test_unauthorized_access_rejected(self, client: AsyncClient):
        # Próba wykonania operacji bez nagłówka Authorization
        response = await client.get("/api/v1/projects/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_project_stats_integration(self, client: AsyncClient):
        headers = await create_authenticated_client(client, "usera@example.com")

        create_res = await client.post(
            "/api/v1/projects/",
            json={"name": "Projekt"},
            headers=headers
        )
        project_id = create_res.json()["id"]

        today = date.today()

        tasks_to_create = [
            {"title": "Task 1", "project_id": project_id,
             "status": "TODO", "priority": "HIGH", "due_date": (today).isoformat()},
            {"title": "Task 2", "project_id": project_id,
             "status": "TODO", "priority": "LOW", "due_date": (today).isoformat()},
            {"title": "Task 3", "project_id": project_id,
             "status": "DONE", "priority": "HIGH", "due_date": (today).isoformat()},
        ]
        task_ids: list[int] = []
        for task in tasks_to_create:
            res = await client.post("/api/v1/tasks/", json=task, headers=headers)
            assert res.status_code == status.HTTP_201_CREATED
            task_ids.append(res.json()["id"])

        # Aktualizacja daty
        update_resp = await client.put(
            f"/api/v1/tasks/{task_ids[0]}",
            json={"due_date": (today - timedelta(days=3)).isoformat()},
            headers=headers
        )
        assert update_resp.status_code == status.HTTP_200_OK

        endpoint_url = f"/api/v1/projects/{project_id}/stats"

        # 2. ACT - Pierwsze wywołanie (Cache Miss -> pobranie z bazy)
        response_1 = await client.get(endpoint_url, headers=headers)

        # 3. ASSERT - Sprawdzamy poprawność odpowiedzi z bazy
        assert response_1.status_code == status.HTTP_200_OK
        data_1 = response_1.json()

        assert data_1["total_tasks"] == 3
        assert data_1["completed_tasks"] == 1
        assert data_1["todo_tasks"] == 2
        assert data_1["overdue_tasks"] == 1
        assert data_1["completion_rate"] == 33.33

        # 4. ACT - Drugie wywołanie (Cache Hit -> pobranie z Redisa)
        response_2 = await client.get(endpoint_url, headers=headers)

        # 5. ASSERT - Odpowiedź powinna być identyczna
        assert response_2.status_code == status.HTTP_200_OK
        assert response_2.json() == data_1

    async def test_export_project_stats_invalid_format_returns_422(
        self, client: AsyncClient
    ):
        headers = await create_authenticated_client(client, "usera@example.com")
        # 1. ACT - Wywołujemy endpoint z niepoprawnym parametrem format
        project_id = 10
        response = await client.get(
            f"/api/v1/projects/{project_id}/stats/export?format=invalid_format",
            headers=headers,
        )

        # 2. ASSERT - FastAPI powinno odrzucić zapytanie na poziomie walidacji Query
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_export_project_stats_csv_success(
        self, client: AsyncClient
    ):
        # 1. ARRANGE
        headers = await create_authenticated_client(client, "usera@example.com")

        create_res = await client.post(
            "/api/v1/projects/",
            json={"name": "Export CSV Project"},
            headers=headers
        )
        project_id = create_res.json()["id"]

        tasks_to_create = [
            {"title": "Task 1", "project_id": project_id,
             "status": "TODO", "priority": "HIGH"},
            {"title": "Task 3", "project_id": project_id,
             "status": "DONE", "priority": "HIGH"},
        ]

        for task in tasks_to_create:
            await client.post("/api/v1/tasks/", json=task, headers=headers)

        # 2. ACT
        response = await client.get(
            f"/api/v1/projects/{project_id}/stats/export?format=csv",
            headers=headers,
        )

        # 3. ASSERT
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert f'attachment; filename="project_{project_id}_stats.csv"' in response.headers[
            "content-disposition"]

        csv_content = response.text
        assert "project_id,project_name,total_tasks" in csv_content
        assert "Export CSV Project" in csv_content

    async def test_export_project_stats_pdf_success(
        self, client: AsyncClient
    ):
        # 1. ARRANGE
        headers = await create_authenticated_client(client, "usera@example.com")

        create_res = await client.post(
            "/api/v1/projects/",
            json={"name": "Export CSV Project"},
            headers=headers
        )
        project_id = create_res.json()["id"]

        tasks_to_create = [
            {"title": "Task 1", "project_id": project_id,
             "status": "TODO", "priority": "HIGH"},
            {"title": "Task 3", "project_id": project_id,
             "status": "DONE", "priority": "HIGH"},
        ]

        for task in tasks_to_create:
            await client.post("/api/v1/tasks/", json=task, headers=headers)

        # 2. ACT
        response = await client.get(
            f"/api/v1/projects/{project_id}/stats/export?format=pdf",
            headers=headers,
        )

        # 3. ASSERT
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/pdf"
        assert f'attachment; filename="project_{project_id}_stats.pdf"' in response.headers[
            "content-disposition"]

        # Sprawdzamy surowe bajty pliku PDF
        assert isinstance(response.content, bytes)
        assert response.content.startswith(b"%PDF")
