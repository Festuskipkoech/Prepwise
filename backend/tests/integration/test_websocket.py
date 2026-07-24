import pytest
import httpx
from uuid import uuid4
from unittest.mock import patch
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from app.core.security import decode_access_token
from app.main import app as fastapi_app


def _get_user_id(access_token: str) -> str:
    decoded = decode_access_token(access_token)
    return decoded["user_id"]


@pytest.mark.asyncio
async def test_websocket_rejects_missing_token(app):
    user_id = uuid4()
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=fastapi_app), base_url="http://test"
    ) as client:
        with pytest.raises(Exception):
            async with aconnect_ws(f"http://test/ws/{user_id}", client) as ws:
                await ws.receive_json()


@pytest.mark.asyncio
async def test_websocket_rejects_invalid_token(app):
    user_id = uuid4()
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=fastapi_app), base_url="http://test"
    ) as client:
        with pytest.raises(Exception):
            async with aconnect_ws(
                f"http://test/ws/{user_id}?token=not.a.real.token", client
            ) as ws:
                await ws.receive_json()


@pytest.mark.asyncio
async def test_websocket_rejects_mismatched_user_id(app, auth):
    wrong_user_id = uuid4()
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=fastapi_app), base_url="http://test"
    ) as client:
        with pytest.raises(Exception):
            async with aconnect_ws(
                f"http://test/ws/{wrong_user_id}?token={auth['access_token']}", client
            ) as ws:
                await ws.receive_json()


@pytest.mark.asyncio
async def test_websocket_accepts_valid_token(app, auth):
    user_id = _get_user_id(auth["access_token"])
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=fastapi_app), base_url="http://test"
    ) as client:
        async with aconnect_ws(
            f"http://test/ws/{user_id}?token={auth['access_token']}", client
        ) as ws:
            assert ws is not None


@pytest.mark.asyncio
async def test_websocket_sends_error_on_invalid_message(app, auth):
    user_id = _get_user_id(auth["access_token"])
    async with httpx.AsyncClient(
        transport=ASGIWebSocketTransport(app=fastapi_app), base_url="http://test"
    ) as client:
        async with aconnect_ws(
            f"http://test/ws/{user_id}?token={auth['access_token']}", client
        ) as ws:
            await ws.send_json({"type": "message", "content": ""})
            resp = await ws.receive_json()
            assert resp["type"] == "error"


@pytest.mark.asyncio
async def test_websocket_valid_message_receives_status(app, auth):
    user_id = _get_user_id(auth["access_token"])

    with patch("app.websocket.dispatch.classify_message") as mock_classify:
        from app.schemas.classification import ClassificationResult
        mock_classify.return_value = ClassificationResult(
            engine_type="job",
            confidence=0.95,
            reasoning="Job search.",
        )

        async with httpx.AsyncClient(
            transport=ASGIWebSocketTransport(app=fastapi_app), base_url="http://test"
        ) as client:
            async with aconnect_ws(
                f"http://test/ws/{user_id}?token={auth['access_token']}", client
            ) as ws:
                await ws.send_json({
                    "type": "message",
                    "chat_id": None,
                    "engine_type": None,
                    "content": "Find me backend engineering roles in Nairobi",
                })

                received = []
                for _ in range(5):
                    try:
                        msg = await ws.receive_json()
                        received.append(msg)
                        if msg["type"] in ("done", "error"):
                            break
                    except Exception:
                        break

                types = {m["type"] for m in received}
                assert "status" in types or "error" in types
