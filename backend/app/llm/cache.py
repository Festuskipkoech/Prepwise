import asyncio
from typing import Any
 
from anthropic import AsyncAnthropic

from app.core.config import settings

def build_cached_system_message(profile_text: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": profile_text,
            "cache_control": {"type": "ephemeral"},
        }
    ]

def build_cached_messages(
    profile_text: str,
    user_message: str,
) -> dict[str, Any]:
    return {
        "system": build_cached_system_message(profile_text),
        "messages": [
            {"role": "user", "content": user_message}
        ],
    }

class CacheKeepalive:
    def __init__(self, profile_text: str, interval_seconds: int = 240) -> None:
        self.profile_text = profile_text
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _ping(self) -> None:
        await self._client.messages.create(
            model = settings.llm_small_model,
            max_tokens=1,
            system=build_cached_system_message(self.profile_text),
            messages=[{"role": "user", "content": "ping"}]
        )
    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            try:
                await self._ping()
            except Exception:
                pass
    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
    
