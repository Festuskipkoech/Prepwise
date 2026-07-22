import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.websocket.pubsub import RedisPubSubManager

# Helpers
def _make_manager_with_mocks():
    """Return a RedisPubSubManager with mocked publisher and subscriber."""
    manager = RedisPubSubManager.__new__(RedisPubSubManager)
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    publisher.set = AsyncMock()
    publisher.delete = AsyncMock()

    subscriber = MagicMock()
    pubsub_obj = MagicMock()
    pubsub_obj.subscribe = AsyncMock()
    pubsub_obj.unsubscribe = AsyncMock()
    pubsub_obj.aclose = AsyncMock()
    subscriber.pubsub = MagicMock(return_value=pubsub_obj)

    manager._publisher = publisher
    manager._subscriber = subscriber
    return manager, publisher, subscriber, pubsub_obj

# publish
@pytest.mark.asyncio
async def test_publish_sends_to_correct_channel():
    manager, publisher, _, _ = _make_manager_with_mocks()
    await manager.publish("user-123", {"type": "token", "content": "hi"})
    publisher.publish.assert_called_once()
    call_args = publisher.publish.call_args
    assert call_args[0][0] == "stream:user-123"

@pytest.mark.asyncio
async def test_publish_serialises_message_as_json():
    manager, publisher, _, _ = _make_manager_with_mocks()
    message = {"type": "status", "content": "Thinking..."}
    await manager.publish("user-123", message)
    call_args = publisher.publish.call_args
    sent_data = call_args[0][1]
    assert json.loads(sent_data) == message

@pytest.mark.asyncio
async def test_publish_raises_if_not_started():
    manager = RedisPubSubManager.__new__(RedisPubSubManager)
    manager._publisher = None
    manager._subscriber = None
    with pytest.raises(RuntimeError, match="not been started"):
        await manager.publish("user-123", {"type": "token", "content": "x"})

# subscribe
@pytest.mark.asyncio
async def test_subscribe_subscribes_to_correct_channel():
    manager, _, _, pubsub_obj = _make_manager_with_mocks()
    result = await manager.subscribe("user-123")
    pubsub_obj.subscribe.assert_called_once_with("stream:user-123")
    assert result is pubsub_obj

@pytest.mark.asyncio
async def test_subscribe_raises_if_not_started():
    manager = RedisPubSubManager.__new__(RedisPubSubManager)
    manager._publisher = None
    manager._subscriber = None
    with pytest.raises(RuntimeError, match="not been started"):
        await manager.subscribe("user-123")

# unsubscribe
@pytest.mark.asyncio
async def test_unsubscribe_calls_unsubscribe_and_close():
    manager, _, _, pubsub_obj = _make_manager_with_mocks()
    await manager.unsubscribe("user-123", pubsub_obj)
    pubsub_obj.unsubscribe.assert_called_once_with("stream:user-123")
    pubsub_obj.aclose.assert_called_once()

# set_presence / clear_presence
@pytest.mark.asyncio
async def test_set_presence_uses_correct_key_and_ttl():
    manager, publisher, _, _ = _make_manager_with_mocks()
    await manager.set_presence("user-123")
    publisher.set.assert_called_once()
    call_args = publisher.set.call_args
    assert call_args[0][0] == "presence:user-123"
    assert call_args[0][1] == "1"
    assert call_args[1].get("ex") == 90

@pytest.mark.asyncio
async def test_clear_presence_deletes_correct_key():
    manager, publisher, _, _ = _make_manager_with_mocks()
    await manager.clear_presence("user-123")
    publisher.delete.assert_called_once_with("presence:user-123")

@pytest.mark.asyncio
async def test_set_presence_no_op_if_not_started():
    manager = RedisPubSubManager.__new__(RedisPubSubManager)
    manager._publisher = None
    manager._subscriber = None
    await manager.set_presence("user-123")

@pytest.mark.asyncio
async def test_clear_presence_no_op_if_not_started():
    manager = RedisPubSubManager.__new__(RedisPubSubManager)
    manager._publisher = None
    manager._subscriber = None
    await manager.clear_presence("user-123")

# iter_messages
@pytest.mark.asyncio
async def test_iter_messages_yields_parsed_json():
    manager, _, _, pubsub_obj = _make_manager_with_mocks()

    raw_messages = [
        {"type": "subscribe", "data": 1},
        {"type": "message", "data": json.dumps({"type": "token", "content": "hello"})},
        {"type": "message", "data": json.dumps({"type": "done", "chat_id": "abc"})},
    ]

    async def _listen():
        for m in raw_messages:
            yield m

    pubsub_obj.listen = _listen

    results = []
    async for msg in manager.iter_messages(pubsub_obj):
        results.append(msg)

    assert len(results) == 2
    assert results[0] == {"type": "token", "content": "hello"}
    assert results[1] == {"type": "done", "chat_id": "abc"}

@pytest.mark.asyncio
async def test_iter_messages_skips_non_message_types():
    manager, _, _, pubsub_obj = _make_manager_with_mocks()

    raw_messages = [
        {"type": "subscribe", "data": 1},
        {"type": "psubscribe", "data": 1},
        {"type": "unsubscribe", "data": 0},
    ]

    async def _listen():
        for m in raw_messages:
            yield m

    pubsub_obj.listen = _listen

    results = []
    async for msg in manager.iter_messages(pubsub_obj):
        results.append(msg)

    assert results == []

@pytest.mark.asyncio
async def test_iter_messages_skips_malformed_json():
    manager, _, _, pubsub_obj = _make_manager_with_mocks()

    raw_messages = [
        {"type": "message", "data": "not valid json {{{"},
        {"type": "message", "data": json.dumps({"type": "token", "content": "good"})},
    ]

    async def _listen():
        for m in raw_messages:
            yield m

    pubsub_obj.listen = _listen

    results = []
    async for msg in manager.iter_messages(pubsub_obj):
        results.append(msg)

    assert len(results) == 1
    assert results[0]["type"] == "token"
