import asyncio
import logging
from uuid import UUID

from anyio import ClosedResourceError
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.core.security import decode_access_token
from app.core.exceptions.auth import InvalidTokenError
from app.db.session import AsyncSessionFactory
from app.repositories.session_repository import SessionRepository
from app.schemas.websocket import InboundMessage, OutboundError
from app.websocket.dispatch import dispatch
from app.websocket.manager import ConnectionManager
from app.websocket.pubsub import RedisPubSubManager

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_SECONDS = 30
_HEARTBEAT_TIMEOUT_SECONDS = 10

async def _authenticate(websocket: WebSocket) -> UUID | None:
    """Validate the access token from the query string.

    Returns the user_id UUID on success, None on failure.
    Closes the WebSocket with code 1008 if authentication fails.
    All validation happens before websocket.accept() is called.
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return None

    try:
        decoded = decode_access_token(token)
    except InvalidTokenError:
        await websocket.close(code=1008, reason="Invalid token")
        return None

    jti = decoded["jti"]
    user_id_str = decoded["user_id"]

    try:
        redis_auth = websocket.app.state.redis_auth
        async with AsyncSessionFactory() as db:
            session_repo = SessionRepository(db, redis_auth)
            cached = await session_repo.get_cached_access_token(jti)
            if cached:
                if cached != user_id_str:
                    await websocket.close(code=1008, reason="Token mismatch")
                    return None
            else:
                session = await session_repo.get_by_jti(jti)
                if not session:
                    await websocket.close(code=1008, reason="Session not found")
                    return None
                await session_repo.cache_access_token(jti, str(session.user_id))
    except Exception:
        logger.exception("Error during WebSocket token validation")
        await websocket.close(code=1008, reason="Authentication error")
        return None

    return UUID(user_id_str)

async def _listen_client(
    websocket: WebSocket,
    user_id: UUID,
    pubsub_manager: RedisPubSubManager,
) -> None:
    """Receive messages from the client and fire dispatch as a concurrent task.

    Returns immediately to receive_json() after each dispatch so the client
    listener stays responsive throughout long engine runs.
    """
    try:
        while True:
            raw = await websocket.receive_json()
            try:
                message = InboundMessage.model_validate(raw)
            except Exception:
                await websocket.send_json(
                    OutboundError(content="Invalid message format.").model_dump()
                )
                continue

            asyncio.create_task(
                dispatch(
                    user_id=user_id,
                    message=message,
                    pubsub_manager=pubsub_manager,
                    app=websocket.app,
                )
            )
    except (WebSocketDisconnect, ClosedResourceError):
        logger.debug("Client disconnected — user %s", user_id)
    except Exception:
        logger.exception("Unexpected error in client listener — user %s", user_id)
        
async def _listen_pubsub(
    websocket: WebSocket,
    user_id: UUID,
    pubsub_manager: RedisPubSubManager,
    connection_manager: ConnectionManager,
) -> None:
    """Forward Redis pub/sub messages to the connected WebSocket client.

    This is the only path by which engine tokens reach the client.
    The engine publishes to Redis; this task picks up and delivers.
    """
    pubsub = await pubsub_manager.subscribe(str(user_id))
    try:
        async for message in pubsub_manager.iter_messages(pubsub):
            if websocket.client_state != WebSocketState.CONNECTED:
                break
            await connection_manager.send(user_id, message)
    except Exception:
        logger.exception("Unexpected error in pubsub listener — user %s", user_id)
    finally:
        await pubsub_manager.unsubscribe(str(user_id), pubsub)

async def _heartbeat(websocket: WebSocket, user_id: UUID) -> None:
    """Send a WebSocket ping frame every 30 seconds.

    If the send does not complete within 10 seconds the connection is
    considered dead, closed with 1001, and the FIRST_COMPLETED path
    triggers full cleanup. The browser handles pong automatically at
    the protocol level — no client-side code needed.
    """
    try:
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)

            if websocket.client_state != WebSocketState.CONNECTED:
                logger.debug(
                    "Heartbeat stopping — connection no longer open — user %s", user_id
                )
                return

            try:
                await asyncio.wait_for(
                    websocket.send_bytes(b"ping"),
                    timeout=_HEARTBEAT_TIMEOUT_SECONDS,
                )
                logger.debug("Heartbeat ping sent — user %s", user_id)
            except asyncio.TimeoutError:
                logger.warning(
                    "Heartbeat timed out after %ds — closing — user %s",
                    _HEARTBEAT_TIMEOUT_SECONDS,
                    user_id,
                )
                await websocket.close(code=1001, reason="Heartbeat timeout")
                return
    except Exception:
        logger.debug("Heartbeat task exiting — user %s", user_id, exc_info=True)

async def handle_websocket_connection(websocket: WebSocket, user_id: UUID) -> None:
    """Full lifecycle for a single WebSocket connection.

    Authenticates, accepts, runs three concurrent tasks, and cleans up
    regardless of how the connection ends.
    """
    authenticated_user_id = await _authenticate(websocket)
    if authenticated_user_id is None:
        return

    if authenticated_user_id != user_id:
        await websocket.close(code=1008, reason="User ID mismatch")
        return

    await websocket.accept()

    connection_manager: ConnectionManager = websocket.app.state.connection_manager
    pubsub_manager: RedisPubSubManager = websocket.app.state.redis_pubsub

    connection_manager.connect(user_id, websocket)
    await pubsub_manager.set_presence(str(user_id))

    logger.info("WebSocket accepted — user %s", user_id)

    client_task = asyncio.create_task(
        _listen_client(websocket, user_id, pubsub_manager)
    )
    pubsub_task = asyncio.create_task(
        _listen_pubsub(websocket, user_id, pubsub_manager, connection_manager)
    )
    heartbeat_task = asyncio.create_task(
        _heartbeat(websocket, user_id)
    )

    try:
        done, pending = await asyncio.wait(
            [client_task, pubsub_task, heartbeat_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        connection_manager.disconnect(user_id)
        await pubsub_manager.clear_presence(str(user_id))
        logger.info("WebSocket cleaned up — user %s", user_id)
