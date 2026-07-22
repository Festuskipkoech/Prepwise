from uuid import UUID

from fastapi import APIRouter, WebSocket

from app.websocket.handler import handle_websocket_connection

router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: UUID) -> None:
    await handle_websocket_connection(websocket, user_id)