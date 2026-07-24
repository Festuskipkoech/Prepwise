import pytest
from unittest.mock import patch
from uuid import uuid4

from app.schemas.websocket import InboundMessage
from app.websocket.dispatch import _resolve_engine, _ensure_chat_session
from app.db.session import AsyncSessionFactory as DBSession
from app.repositories.auth_repository import UserRepository

async def _get_user_id(auth: dict) -> object:
    async with DBSession() as db:
        repo = UserRepository(db)
        user = await repo.get_by_email(auth["email"])
        return user.id

def _mock_classify(engine_type: str, confidence: float = 0.95):
    from app.schemas.classification import ClassificationResult
    return ClassificationResult(
        engine_type=engine_type,
        confidence=confidence,
        reasoning="test",
    )

@pytest.mark.asyncio
async def test_resolve_engine_new_conversation_calls_classifier(app):
    from app.main import app as fastapi_app
    with patch("app.websocket.dispatch.classify_message") as mock_classify:
        mock_classify.return_value = _mock_classify("job")
        message = InboundMessage(
            type="message",
            chat_id=None,
            engine_type=None,
            content="Find me ML roles in Nairobi",
        )
        result = await _resolve_engine(message, fastapi_app)
        assert result == "job"
        mock_classify.assert_called_once()

@pytest.mark.asyncio
async def test_resolve_engine_continuing_conversation_skips_classifier(app):
    with patch("app.websocket.dispatch.classify_message") as mock_classify:
        message = InboundMessage(
            type="message",
            chat_id=uuid4(),
            engine_type="prep",
            content="Continue my prep session",
        )
        result = await _resolve_engine(message, app)
        assert result == "prep"
        mock_classify.assert_not_called()

async def test_resolve_engine_returns_none_for_unsupported(app):
    from app.main import app as fastapi_app
    with patch("app.websocket.dispatch.classify_message") as mock_classify:
        mock_classify.return_value = _mock_classify("unsupported", confidence=0.1)
        message = InboundMessage(
            type="message",
            chat_id=None,
            engine_type=None,
            content="What is the weather today?",
        )
        result = await _resolve_engine(message, fastapi_app)
        assert result is None

@pytest.mark.asyncio
async def test_ensure_chat_session_creates_new_row_when_no_chat_id(auth):
    user_id = await _get_user_id(auth)

    async with DBSession() as db:
        chat_id, is_new = await _ensure_chat_session(
            user_id=user_id,
            engine_type="job",
            chat_id=None,
            db=db,
        )
    assert is_new is True
    assert chat_id is not None

@pytest.mark.asyncio
async def test_ensure_chat_session_returns_existing_chat_id(auth):
    user_id = await _get_user_id(auth)
    existing_chat_id = uuid4()

    async with DBSession() as db:
        chat_id, is_new = await _ensure_chat_session(
            user_id=user_id,
            engine_type="job",
            chat_id=existing_chat_id,
            db=db,
        )
    assert is_new is False
    assert chat_id == existing_chat_id

@pytest.mark.asyncio
async def test_dispatch_publishes_error_for_unsupported_message(app, auth):
    from app.main import app as fastapi_app
    from app.websocket.dispatch import dispatch

    user_id = await _get_user_id(auth)
    published_messages = []

    class MockPubSub:
        async def publish(self, user_id, message):
            published_messages.append(message)

        async def set_presence(self, user_id):
            pass

    with patch("app.websocket.dispatch.classify_message") as mock_classify:
        mock_classify.return_value = _mock_classify("unsupported", confidence=0.1)
        message = InboundMessage(
            type="message",
            chat_id=None,
            engine_type=None,
            content="Tell me a joke",
        )
        await dispatch(
            user_id=user_id,
            message=message,
            pubsub_manager=MockPubSub(),
            app=fastapi_app,
        )

    assert len(published_messages) == 1
    assert published_messages[0]["type"] == "error"

@pytest.mark.asyncio
async def test_dispatch_publishes_status_before_routing(app, auth):
    from app.main import app as fastapi_app
    from app.websocket.dispatch import dispatch

    user_id = await _get_user_id(auth)
    published_messages = []

    class MockPubSub:
        async def publish(self, user_id, message):
            published_messages.append(message)

        async def set_presence(self, user_id):
            pass

    with patch("app.websocket.dispatch.classify_message") as mock_classify:
        mock_classify.return_value = _mock_classify("job")
        message = InboundMessage(
            type="message",
            chat_id=None,
            engine_type=None,
            content="Find me backend roles",
        )
        await dispatch(
            user_id=user_id,
            message=message,
            pubsub_manager=MockPubSub(),
            app=fastapi_app,
        )

    status_messages = [m for m in published_messages if m["type"] == "status"]
    assert len(status_messages) >= 1
    assert status_messages[0]["content"] == "Thinking..."
