import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts.normalisation import (
    NORMALISATION_HUMAN_TEMPLATE,
    NORMALISATION_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

async def normalise_profile(raw_text: str, llm: ChatAnthropic) -> str:
    messages = [
        SystemMessage(
            content=[
                {
                    "type": "text",
                    "text": NORMALISATION_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        ),
        HumanMessage(content=NORMALISATION_HUMAN_TEMPLATE.format(raw_text=raw_text)),
    ]

    logger.debug(
        "Sending profile normalisation request — %d characters of raw text", len(raw_text)
    )
    response = await llm.ainvoke(messages)
    normalised = response.content.strip()

    if not normalised:
        raise ValueError("Profile normalisation returned empty output.")

    logger.debug("Normalised profile — %d characters", len(normalised))
    return normalised