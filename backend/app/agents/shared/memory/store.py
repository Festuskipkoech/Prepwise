import logging
from typing import Any
 
from langchain_core.messages import BaseMessage
from langgraph.store.postgres.aio import AsyncPostgresStore
 
logger = logging.getLogger(__name__)
 
_MEMORY_NAMESPACE = "memories"
_MEMORY_KEY = "facts"
 
 
def _namespace(user_id: str) -> tuple[str, str]:
    return (_MEMORY_NAMESPACE, user_id)

async def get_memories(user_id: str, store: AsyncPostgresStore) -> str:
    """Retrieve persisted facts about the user from the long-term store.
 
    Returns a formatted string ready to be injected into the agent's
    system prompt. Returns an empty string if no memories exist yet.
    """
    try:
        item = await store.aget(namespace=_namespace(user_id), key=_MEMORY_KEY)
        if item is None or not item.value:
            return ""
        facts: list[str] = item.value.get("facts", [])
        if not facts:
            return ""
        formatted = "\n".join(f"- {fact}" for fact in facts)
        logger.debug("Loaded %d memory facts for user %s", len(facts), user_id)
        return formatted
    except Exception:
        logger.warning("Failed to load memories for user %s", user_id, exc_info=True)
        return ""
    
async def save_memory(user_id: str, fact: str, store: AsyncPostgresStore) -> None:
    """Append a new fact to the user's long-term memory.
 
    Reads the existing facts list, appends the new fact, and writes back.
    Duplicate facts are silently ignored.
    """
    try:
        item = await store.aget(namespace=_namespace(user_id), key=_MEMORY_KEY)
        facts: list[str] = []
        if item is not None and item.value:
            facts = item.value.get("facts", [])
        
        if fact in facts:
            logger.debug("Memory fact already exists for user %s — skipping", user_id)
            return

        facts.append(fact)
        await store.aput(
            namespace=_namespace(user_id),
            key=_MEMORY_KEY,
            value={"facts": facts},
        )
        logger.debug("Saved memory fact for user %s: %r", user_id, fact)
    except Exception:
        logger.warning("Failed to save memory for user %s", user_id, exc_info=True)

async def delete_memory(user_id: str, fact: str, store: AsyncPostgresStore) -> None:
    """Remove a specific fact from the user's long-term memory."""
    try:
        item = await store.aget(namespace=_namespace(user_id), key=_MEMORY_KEY)
        if item is None or not item.value:
            return
        facts: list[str] = item.value.get("facts", [])
        updated = [f for f in facts if f != fact]
        await  store.aput(
            namespace=_namespace(user_id),
            key=_MEMORY_KEY,
            value={"facts": updated},
        )
        logger.debug("Deleted memory fact for user %s: %r", user_id, fact)
    except Exception:
        logger.warning("Failed to delete memory for user %s", user_id, exc_info=True)

async def clear_memories(user_id: str, store: AsyncPostgresStore) -> None:
    """Remove all persisted memory for a user."""
    try:
        await store.adelete(namespace=_namespace(user_id), key=_MEMORY_KEY)
        logger.info("Cleared all memories for user %s", user_id)
    except Exception:
        logger.warning("Failed to clear memories for user %s", user_id, exc_info=True)