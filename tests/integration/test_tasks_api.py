import pytest
from fastapi import status
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


# Helper do rejestracji i autoryzacji użytkownika testowego
async def create_auth_headers(client: AsyncClient, email: str = "task_user@example.com") -> dict:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    res = await client.post("/api/v1/auth/login", data={"username": email, "password": "Password123!"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_task_api(client: AsyncClient):
    headers = await create_auth_headers(client, "task_create@example.com")

    # 1. Tworzymy projekt
    proj_resp = await client.post("/api/v1/projects/", json={"name": "Project for Task"}, headers=headers)
    assert proj_resp.status_code == status.HTTP_201_CREATED
    project_id = proj_resp.json()["id"]

    # 2. Tworzymy zadanie w projekcie
    task_payload = {
        "title": "Zadanie Testowe",
        "description": "Opis zadania",
        "project_id": project_id,
        "priority": "HIGH",
        "status": "TODO"
    }
    task_resp = await client.post("/api/v1/tasks/", json=task_payload, headers=headers)
    assert task_resp.status_code == status.HTTP_201_CREATED
    data = task_resp.json()
    assert data["title"] == task_payload["title"]
    assert data["priority"] == "HIGH"
    assert data["status"] == "TODO"


async def test_complete_task_sets_completed_at(client: AsyncClient):
    headers = await create_auth_headers(client, "task_complete@example.com")
    proj_resp = await client.post("/api/v1/projects/", json={"name": "Project Y"}, headers=headers)
    project_id = proj_resp.json()["id"]

    task_payload = {
        "title": "Do Wykonania",
        "project_id": project_id,
        "status": "TODO"
    }
    task_resp = await client.post("/api/v1/tasks/", json=task_payload, headers=headers)
    task_id = task_resp.json()["id"]

    # Aktualizacja statusu na DONE
    update_resp = await client.put(
        f"/api/v1/tasks/{task_id}",
        json={"status": "DONE"},
        headers=headers
    )
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["status"] == "DONE"


async def test_get_tasks_filtering_by_status_and_priority(client: AsyncClient):
    headers = await create_auth_headers(client, "filter_user@example.com")

    # 1. Przygotowujemy projekt
    proj_resp = await client.post("/api/v1/projects/", json={"name": "Filter Project"}, headers=headers)
    project_id = proj_resp.json()["id"]

    # 2. Tworzymy zadania o różnych statusach i priorytetach
    tasks_to_create = [
        {"title": "Task 1", "project_id": project_id,
            "status": "TODO", "priority": "HIGH"},
        {"title": "Task 2", "project_id": project_id,
            "status": "TODO", "priority": "LOW"},
        {"title": "Task 3", "project_id": project_id,
            "status": "DONE", "priority": "HIGH"},
        {"title": "Task 4", "project_id": project_id,
            "status": "DONE", "priority": "LOW"},
    ]

    for task in tasks_to_create:
        res = await client.post("/api/v1/tasks/", json=task, headers=headers)
        assert res.status_code == status.HTTP_201_CREATED

    # 3. Test filtrowania po statusie TODO
    res_todo = await client.get(f"/api/v1/tasks/project/{project_id}?status=TODO", headers=headers)
    assert res_todo.status_code == status.HTTP_200_OK
    todo_tasks = res_todo.json()
    assert len(todo_tasks) == 2
    assert all(t["status"] == "TODO" for t in todo_tasks)

    # 4. Test filtrowania po statusie DONE
    res_done = await client.get(f"/api/v1/tasks/project/{project_id}?status=DONE", headers=headers)
    assert res_done.status_code == status.HTTP_200_OK
    done_tasks = res_done.json()
    assert len(done_tasks) == 2
    assert all(t["status"] == "DONE" for t in done_tasks)

    # 5. Test filtrowania po priorytecie HIGH
    res_high = await client.get(f"/api/v1/tasks/project/{project_id}?priority=HIGH", headers=headers)
    assert res_high.status_code == status.HTTP_200_OK
    high_tasks = res_high.json()
    assert len(high_tasks) == 2
    assert all(t["priority"] == "HIGH" for t in high_tasks)

    # 6. Test filtrowania łączonego (status=TODO i priority=HIGH)
    res_combined = await client.get(
        f"/api/v1/tasks/project/{project_id}?status=TODO&priority=HIGH",
        headers=headers
    )
    assert res_combined.status_code == status.HTTP_200_OK
    combined_tasks = res_combined.json()
    assert len(combined_tasks) == 1
    assert combined_tasks[0]["title"] == "Task 1"
