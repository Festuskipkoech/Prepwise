import asyncio
import logging
 
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
 
logger = logging.getLogger(__name__)
 
_KEEPALIVE_INTERVAL_SECONDS = 240
_KEEPALIVE_PROMPT = "keepalive"

# System prompts eligible for prompt caching.
# Each engine registers its system prompt here at startup so the keepalive
# task can ping them all and hold the cache TTL open.

_registered_system_prompts: list[str] = []

def register_system_prompt(prompt: str) -> None:
    _registered_system_prompts.append(prompt)

async def _ping_prompt(llm: ChatAnthropic, system_prompt: str) -> None:

    try:
        messages = [
            SystemMessage(
                content = [
                    {
                        "type": "text",
                        "text":system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            ),
            HumanMessage(content=_KEEPALIVE_PROMPT),
        ]
        await llm.ainvoke(messages)
        logger.debug("Prompt cache keepalive ping sent.")
    except Exception:
        logger.warning("Prompt cache keepalive ping failed.", exc_info=True)

async  def run_cache_keepalive(llm: ChatAnthropic) -> None:
    logger.info("Prompt cache keepalive task started.")

    while True:
        await asyncio.sleep(_KEEPALIVE_INTERVAL_SECONDS)
        if not _registered_system_prompts:
            continue
        for prompt in _registered_system_prompts:
            await _ping_prompt(llm, prompt)