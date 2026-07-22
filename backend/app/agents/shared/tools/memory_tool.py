import logging
 
from langchain_core.tools import tool
from langgraph.store.postgres.aio import AsyncPostgresStore
 
from app.agents.shared.memory.store import get_memories, save_memory
 
logger = logging.getLogger(__name__)

def build_memory(user_id: str, store: AsyncPostgresStore):
    @tool
    async def get_long_term_memories() -> str:
        """Retrieve facts remembered about this user from previous sessions.
        This includes target companies, preferred role types, stated skill gaps,
        communication preferences, and any other details the user has shared
        across past conversations. Call this at the start of every new conversation."""
        result = await get_memories(useR_id=user_id, store=store)
        if not result:
            return "No long-term memories found for this user."
        return result

    @tool
    async def remember_fact(fact:str) -> str:
        """Persist an important fact about the user to long-term memory.
        Use this when the user reveals something worth remembering across sessions:
        a target company, a preferred work style, a stated skill gap, a timeline,
        a preference, or any detail that would help future conversations.
        Write the fact as a single clear sentence in third person.
        Example: 'User is targeting ML engineering roles at Kenyan fintechs.'"""
        await save_memory(user_id = user_id, fact=fact, store=store)
        return f"Remembered: {fact}"
    
    return [get_long_term_memories, remember_fact]