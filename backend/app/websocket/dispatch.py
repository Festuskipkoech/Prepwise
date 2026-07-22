import logging
from uuid import UUID

from fastapi import FastAPI
from fastapi.websockets import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.classification.classifier import classify_message
from app.schemas.classification import EngineType
from app.schemas.websocket import (
    InboundMessage,
    OutboundError,
    OutboundStatus,
)
from app.db.session import AsyncSessionFactory
from app.db.models.chat_sessions import ChatSession
from app.llm.router import LLMTask, get_llm
from app.websocket.pubsub import RedisPubSubManager
# from app.agents.job.runner import run as run_job
# from app.agents.prep.runner import run as run_prep
# from app.agents.document.runner import run as run_document
# from app.agents.tracker.runner import run as run_tracker

logger = logging.getLogger(__name__)

_UNSUPPORTED_RESPONSE = (
    "That is outside what I am set up to help with. "
    "I can help you search for jobs, prepare for interviews, "
    "write your resume or cover letter, or analyse your application pipeline. "
    "Which of those would be useful right now?"
)

async def _resolve_engine(
    message: InboundMessage,
    app: FastAPI,
) -> EngineType | None:
    """Return the resolved engine type or None if the query is unsupported.

    New conversation (chat_id is None) — run the classifier.
    Continuing conversation (chat_id present) — trust the declared engine_type
    and pass straight through. The engine's own LLM has the full checkpoint
    history and handles drift naturally in its response without an extra
    validation round trip.
    """
    if message.chat_id is not None:
        return message.engine_type

    llm_client = app.state.llm_client
    small_llm = get_llm(llm_client, LLMTask.ENGINE_CLASSIFY)
    result = await classify_message(message.content, small_llm)

    if result.engine_type == "unsupported":
        return None

    return result.engine_type

async def _ensure_chat_session(
    user_id: UUID,
    engine_type: EngineType,
    chat_id: UUID | None,
    db: AsyncSession,
) -> tuple[UUID, bool]:
    """Return (chat_id, is_new). Creates a new chat_sessions row if needed."""
    
    if chat_id is not None:
        return chat_id, False

    session = ChatSession(
        user_id=user_id,
        engine_type=engine_type,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.debug(
        "Created chat session %s for user %s engine %s",
        session.id,
        user_id,
        engine_type,
    )
    return session.id, True

async def dispatch(
    user_id: UUID,
    message: InboundMessage,
    pubsub_manager: RedisPubSubManager,
    app: FastAPI,
) -> None:
    """Classify, route, and hand off a message to the correct engine graph."""
    try:
        engine_type = await _resolve_engine(message, app)

        if engine_type is None:
            await pubsub_manager.publish(
                str(user_id),
                OutboundError(content=_UNSUPPORTED_RESPONSE).model_dump(),
            )
            return

        async with AsyncSessionFactory() as db:
            chat_id, is_new = await _ensure_chat_session(
                user_id=user_id,
                engine_type=engine_type,
                chat_id=message.chat_id,
                db=db,
            )

        await _route_to_engine(
            user_id=user_id,
            chat_id=chat_id,
            engine_type=engine_type,
            message=message,
            is_new_chat=is_new,
            pubsub_manager=pubsub_manager,
            app=app,
        )

    except Exception:
        logger.exception("Unhandled error in dispatch — user %s", user_id)
        await pubsub_manager.publish(
            str(user_id),
            OutboundError(content="Something went wrong. Please try again.").model_dump(),
        )

async def _route_to_engine(
    user_id: UUID,
    chat_id: UUID,
    engine_type: EngineType,
    message: InboundMessage,
    is_new_chat: bool,
    pubsub_manager: RedisPubSubManager,
    app: FastAPI,
) -> None:
    """Hand off to the correct engine runner.

    Each engine runner invokes its LangGraph graph, streams tokens via
    pubsub_manager.publish(), and sends the final OutboundDone event.
    Lazy imports keep the dispatch layer decoupled from engine implementations.
    """
    await pubsub_manager.publish(
        str(user_id),
        OutboundStatus(content="Thinking...").model_dump(),
    )

    # if engine_type == "job":
    #     await run_job(user_id, chat_id, message, is_new_chat, pubsub_manager, app)
    # elif engine_type == "prep":
    #     await run_prep(user_id, chat_id, message, is_new_chat, pubsub_manager, app)
    # elif engine_type == "document":
    #     await run_document(user_id, chat_id, message, is_new_chat, pubsub_manager, app)
    # elif engine_type == "tracker":
    #     await run_tracker(user_id, chat_id, message, is_new_chat, pubsub_manager, app)
    # else:
    #     logger.error("Unknown engine type in _route_to_engine: %r", engine_type)
    #     await pubsub_manager.publish(
    #         str(user_id),
    #         OutboundError(content="Something went wrong. Please try again.").model_dump(),
    #     )

