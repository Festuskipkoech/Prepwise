import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts.classification import (
    CLASSIFICATION_HUMAN_TEMPLATE,
    CLASSIFICATION_SYSTEM_PROMPT,
)
from app.schemas.classification import ClassificationResult

logger = logging.getLogger(__name__)

async def classify_message(content: str, llm: ChatAnthropic) -> ClassificationResult:
    messages = [
        SystemMessage(
            content=[
                {
                    "type": "text",
                    "text": CLASSIFICATION_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        ),
        HumanMessage(content=CLASSIFICATION_HUMAN_TEMPLATE.format(content=content)),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    try:
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        result = ClassificationResult.model_validate_json(cleaned)
    except Exception:
        logger.warning(
            "Classification response could not be parsed — defaulting to unsupported. Raw: %r",
            raw,
        )
        result = ClassificationResult(
            engine_type="unsupported",
            confidence=0.0,
            reasoning="Parse failure — defaulted to unsupported.",
        )

    logger.debug(
        "Classified message as %r (confidence %.2f) — %s",
        result.engine_type,
        result.confidence,
        result.reasoning,
    )
    return result
