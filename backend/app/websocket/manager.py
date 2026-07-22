import logging
from uuid import UUID
 
from fastapi import Request, WebSocket
 
logger = logging.getLogger(__name__)

class ConnectionManager:
    """Holds live WebSocket connections for users on this worker.
 
    Does not know about connections on other Uvicorn workers.
    Cross-worker delivery is handled by Redis pub/sub in RedisPubSubManager.
    """

    def __init__(self) -> None:
        self._active: dict[str, WebSocket] = {}
    
    def connect(self, user_id: UUID, ws: WebSocket) -> None:
        key = str(user_id)
        self._active[key] = ws
        logger.debug("WebSocket connected — user %s  total active: %d", key, len(self._active))
    
    def disconnect(self, user_id: UUID) -> None:
        key = str(user_id)
        self._active.pop(key, None)
        logger.debug("WebSocket disconnected — user %s  total active: %d", key, len(self._active))
    
    async def send(self, user_id: UUID, message: dict) -> None:
        key = str(user_id)
        ws = self._active.get(key)
        if ws is None:
            logger.debug("send() called for user %s but no active connection on this worker", key)
            return
        
        try:
            await ws.send_json(message)
        except Exception:
            logger.warning("Failed to send message to user %s — connection may be closing", key, exc_info=True)
            self.disconnect(user_id)
    
    def is_connected(self, user_id: UUID) -> bool:
        return str(user_id) in self._active
    
    @property
    def active_count(self) -> int:
        return len(self._active)

def get_connection_manager(request: Request) -> ConnectionManager:
    return request.app.state.connection_manager
