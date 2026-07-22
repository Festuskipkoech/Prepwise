import uuid
import pytest
import httpx

# Register
@pytest.mark.asyncio
async def test_register_success(client):
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": unique_email,
            "password": "ValidPass1!",
            "full_name": "Test User",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["message"] == "Account created. Proceed to log in."

@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": unique_email, "password": "ValidPass1!", "full_name": "User"}

    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error_code"] == "USER_ALREADY_EXISTS"

@pytest.mark.asyncio
async def test_register_weak_password_too_short(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "Ab1!", "full_name": "User"},
    )
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_register_password_no_number(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "NoNumber!", "full_name": "User"},
    )
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_register_password_no_special_char(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "NoSpecial1", "full_name": "User"},
    )
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_register_invalid_email(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "ValidPass1!", "full_name": "User"},
    )
    assert resp.status_code == 422

# Login
@pytest.mark.asyncio
async def test_login_success_returns_access_token(client):
    email = f"login_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "ValidPass1!", "full_name": "User"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "ValidPass1!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie(client):
    email = f"cookie_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "ValidPass1!"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "ValidPass1!"},
    )
    assert "refresh_token" in resp.cookies

@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    email = f"bad_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "ValidPass1!"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "WrongPass9!"},
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "AUTHENTICATION_ERROR"


@pytest.mark.asyncio
async def test_login_nonexistent_user_returns_401(client):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@nowhere.com", "password": "ValidPass1!"},
    )
    assert resp.status_code == 401

# Refresh
@pytest.mark.asyncio
async def test_refresh_returns_new_access_token(client):
    email = f"refresh_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "ValidPass1!"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "ValidPass1!"},
    )
    old_token = login_resp.json()["access_token"]

    refresh_resp = await client.post("/api/auth/refresh")
    assert refresh_resp.status_code == 200
    new_token = refresh_resp.json()["access_token"]
    assert new_token != old_token

@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as fresh_client:
        resp = await fresh_client.post("/api/auth/refresh")
    assert resp.status_code == 401
# Logout
@pytest.mark.asyncio
async def test_logout_success(client):
    email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "ValidPass1!"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "ValidPass1!"},
    )
    access_token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Logged out successfully."

@pytest.mark.asyncio
async def test_token_invalid_after_logout(client):
    email = f"postlogout_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "ValidPass1!"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "ValidPass1!"},
    )
    access_token = login_resp.json()["access_token"]

    await client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    sessions_resp = await client.get(
        "/api/auth/sessions",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert sessions_resp.status_code == 401

# Sessions
@pytest.mark.asyncio
async def test_get_sessions_returns_list(authed_client, auth):
    resp = await authed_client.get("/api/auth/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)
    assert len(data["sessions"]) >= 1

@pytest.mark.asyncio
async def test_get_sessions_requires_auth(client):
    resp = await client.get("/api/auth/sessions")
    assert resp.status_code == 401

# Revoke specific session
@pytest.mark.asyncio
async def test_revoke_session(client):
    email = f"revoke_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "ValidPass1!"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "ValidPass1!"},
    )
    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    sessions_resp = await client.get("/api/auth/sessions", headers=headers)
    sessions = sessions_resp.json()["sessions"]
    assert len(sessions) >= 1
    session_id = sessions[0]["id"]

    revoke_resp = await client.delete(
        f"/api/auth/sessions/{session_id}",
        headers=headers,
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["message"] == "Session revoked."
