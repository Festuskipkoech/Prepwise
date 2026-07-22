import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.websocket.manager import ConnectionManager

USER_A = uuid4()
USER_B = uuid4()

def _mock_ws():
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws

# connect / disconnect / is_connected
def test_connect_registers_user():
    manager = ConnectionManager()
    ws = _mock_ws()
    manager.connect(USER_A, ws)
    assert manager.is_connected(USER_A)

def test_disconnect_removes_user():
    manager = ConnectionManager()
    ws = _mock_ws()
    manager.connect(USER_A, ws)
    manager.disconnect(USER_A)
    assert not manager.is_connected(USER_A)

def test_disconnect_nonexistent_user_does_not_raise():
    manager = ConnectionManager()
    manager.disconnect(USER_A)

def test_is_connected_returns_false_for_unknown_user():
    manager = ConnectionManager()
    assert not manager.is_connected(USER_A)

def test_connect_two_users():
    manager = ConnectionManager()
    manager.connect(USER_A, _mock_ws())
    manager.connect(USER_B, _mock_ws())
    assert manager.is_connected(USER_A)
    assert manager.is_connected(USER_B)

def test_disconnect_one_does_not_affect_other():
    manager = ConnectionManager()
    manager.connect(USER_A, _mock_ws())
    manager.connect(USER_B, _mock_ws())
    manager.disconnect(USER_A)
    assert not manager.is_connected(USER_A)
    assert manager.is_connected(USER_B)

def test_reconnect_overwrites_old_websocket():
    manager = ConnectionManager()
    ws_old = _mock_ws()
    ws_new = _mock_ws()
    manager.connect(USER_A, ws_old)
    manager.connect(USER_A, ws_new)
    assert manager.is_connected(USER_A)
    assert manager.active_count == 1

# active_count
def test_active_count_starts_at_zero():
    manager = ConnectionManager()
    assert manager.active_count == 0

def test_active_count_increments_on_connect():
    manager = ConnectionManager()
    manager.connect(USER_A, _mock_ws())
    assert manager.active_count == 1

def test_active_count_decrements_on_disconnect():
    manager = ConnectionManager()
    manager.connect(USER_A, _mock_ws())
    manager.connect(USER_B, _mock_ws())
    manager.disconnect(USER_A)
    assert manager.active_count == 1

# send
@pytest.mark.asyncio
async def test_send_calls_send_json_on_websocket():
    manager = ConnectionManager()
    ws = _mock_ws()
    manager.connect(USER_A, ws)
    message = {"type": "token", "content": "hello"}
    await manager.send(USER_A, message)
    ws.send_json.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_send_to_missing_user_does_not_raise():
    manager = ConnectionManager()
    await manager.send(USER_A, {"type": "token", "content": "hello"})

@pytest.mark.asyncio
async def test_send_failure_disconnects_user():
    manager = ConnectionManager()
    ws = _mock_ws()
    ws.send_json = AsyncMock(side_effect=Exception("connection dropped"))
    manager.connect(USER_A, ws)
    await manager.send(USER_A, {"type": "token", "content": "hello"})
    assert not manager.is_connected(USER_A)

@pytest.mark.asyncio
async def test_send_correct_message_payload():
    manager = ConnectionManager()
    ws = _mock_ws()
    manager.connect(USER_A, ws)
    payload = {"type": "status", "content": "Thinking..."}
    await manager.send(USER_A, payload)
    ws.send_json.assert_called_once_with(payload)
