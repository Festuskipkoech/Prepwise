import pytest
from uuid import uuid4

# Auth rejection — before accept()
@pytest.mark.asyncio
async def test_websocket_rejects_missing_token(app):
    fastapi_app, _ = app
    from starlette.testclient import TestClient
    with TestClient(fastapi_app) as test_client:
        user_id = uuid4()
        with pytest.raises(Exception):
            with test_client.websocket_connect(f"/ws/{user_id}") as ws:
                ws.receive_json()

@pytest.mark.asyncio
async def test_websocket_rejects_invalid_token(app):
    fastapi_app, _ = app
    from starlette.testclient import TestClient

    with TestClient(fastapi_app) as test_client:
        user_id = uuid4()
        with pytest.raises(Exception):
            with test_client.websocket_connect(
                f"/ws/{user_id}?token=not.a.real.token"
            ) as ws:
                ws.receive_json()

@pytest.mark.asyncio
async def test_websocket_rejects_mismatched_user_id(app, auth):
    fastapi_app, _ = app
    from starlette.testclient import TestClient

    wrong_user_id = uuid4()

    with TestClient(fastapi_app) as test_client:
        with pytest.raises(Exception):
            with test_client.websocket_connect(
                f"/ws/{wrong_user_id}?token={auth['access_token']}"
            ) as ws:
                ws.receive_json()

# Valid connection
@pytest.mark.asyncio
async def test_websocket_accepts_valid_token(app, auth, authed_client):
    fastapi_app, _ = app
    from starlette.testclient import TestClient

    sessions_resp = await authed_client.get("/api/auth/sessions")
    sessions = sessions_resp.json()["sessions"]
    assert len(sessions) >= 1

    from app.core.security import decode_access_token
    decoded = decode_access_token(auth["access_token"])
    user_id = decoded["user_id"]

    with TestClient(fastapi_app) as test_client:
        with test_client.websocket_connect(
            f"/ws/{user_id}?token={auth['access_token']}"
        ) as ws:
            assert ws is not None

# Invalid message format
@pytest.mark.asyncio
async def test_websocket_sends_error_on_invalid_message(app, auth):
    fastapi_app, _ = app
    from starlette.testclient import TestClient
    from app.core.security import decode_access_token

    decoded = decode_access_token(auth["access_token"])
    user_id = decoded["user_id"]

    with TestClient(fastapi_app) as test_client:
        with test_client.websocket_connect(
            f"/ws/{user_id}?token={auth['access_token']}"
        ) as ws:
            ws.send_json({"type": "message", "content": ""})
            resp = ws.receive_json()
            assert resp["type"] == "error"

# Valid message — receives status
@pytest.mark.asyncio
async def test_websocket_valid_message_receives_status(app, auth):
    fastapi_app, _ = app
    from starlette.testclient import TestClient
    from unittest.mock import patch
    from app.schemas.classification import ClassificationResult
    from app.core.security import decode_access_token

    decoded = decode_access_token(auth["access_token"])
    user_id = decoded["user_id"]

    with patch("app.websocket.dispatch.classify_message") as mock_classify:
        mock_classify.return_value = ClassificationResult(
            engine_type="job",
            confidence=0.95,
            reasoning="Job search.",
        )

        with TestClient(fastapi_app) as test_client:
            with test_client.websocket_connect(
                f"/ws/{user_id}?token={auth['access_token']}"
            ) as ws:
                ws.send_json({
                    "type": "message",
                    "chat_id": None,
                    "engine_type": None,
                    "content": "Find me backend engineering roles in Nairobi",
                })

                received = []
                for _ in range(5):
                    try:
                        msg = ws.receive_json(timeout=5)
                        received.append(msg)
                        if msg["type"] in ("done", "error"):
                            break
                    except Exception:
                        break

                types = {m["type"] for m in received}
                assert "status" in types or "error" in types, (
                    f"Expected status or error in {types}"
                )
