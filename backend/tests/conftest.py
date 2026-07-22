import os
import pytest
import pytest_asyncio
import httpx
from asgi_lifespan import LifespanManager
from dotenv import load_dotenv

load_dotenv()

from app.main import app as fastapi_app

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app():
    async with LifespanManager(fastapi_app) as manager:
        yield manager.app

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def client(app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def auth(client):
    email = os.environ["TEST_USER_EMAIL"]
    password = os.environ["TEST_USER_PASSWORD"]
    full_name = os.environ.get("TEST_USER_NAME", "Test User")

    register_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register_resp.status_code in (201, 409), (
        f"Unexpected register status: {register_resp.status_code} — {register_resp.text}"
    )

    login_resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, (
        f"Login failed: {login_resp.status_code} — {login_resp.text}"
    )

    data = login_resp.json()
    return {
        "access_token": data["access_token"],
        "cookies": dict(login_resp.cookies),
        "email": email,
        "password": password,
    }

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def authed_client(app, auth):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
        cookies=auth["cookies"],
    ) as ac:
        yield ac

@pytest.fixture(scope="session")
def resume_path():
    path = os.environ.get("TEST_RESUME_PATH")
    assert path, "TEST_RESUME_PATH env var is not set"
    assert os.path.exists(path), f"Resume not found at: {path}"
    return path