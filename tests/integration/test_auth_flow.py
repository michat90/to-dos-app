# tests/integration/test_auth_flow.py
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_full_auth_logout_lifecycle(client: AsyncClient):
    # 1. Rejestracja nowego użytkownika
    register_payload = {
        "email": "jan.kowalski@example.com",
        "password": "SecurePassword123!",
        "full_name": "Jan Kowalski"
    }
    reg_response = await client.post("/api/v1/auth/register", json=register_payload)
    assert reg_response.status_code == 201

    # 2. Logowanie i pobranie tokena JWT
    login_payload = {
        # OAuth2 password flow używa pola 'username'
        "username": "jan.kowalski@example.com",
        "password": "SecurePassword123!"
    }
    login_response = await client.post("/api/v1/auth/login", data=login_payload)
    assert login_response.status_code == 200

    tokens = login_response.json()
    assert "access_token" in tokens
    access_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 3. Dostęp do chronionego endpointu (np. pobranie listy projektów)
    protected_response = await client.get("/api/v1/projects/", headers=headers)
    assert protected_response.status_code == 200

    # 4. Wylogowanie (wpisanie tokena na czarną listę w Redisie)
    logout_response = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Successfully logged out"

    # 5. Próba ponownego użycia unieważnionego tokena
    reused_response = await client.get("/api/v1/projects/", headers=headers)
    assert reused_response.status_code == 401
    assert reused_response.json(
    )["detail"] == "Token has been revoked (logged out)"
