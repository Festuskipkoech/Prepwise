import logging
from dataclasses import dataclass
 
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
 
from app.agents.prompts.compression import (
    COMPRESSION_HUMAN_TEMPLATE,
    COMPRESSION_SYSTEM_PROMPT,
)
from app.core.config import settings
 
logger = logging.getLogger(__name__)

@dataclass
class CompressionConfig:
    token_threshold: int
    tail_turns: int

_ENGINE_CONFIGS: dict[str, CompressionConfig] = {
    "prep": CompressionConfig(
        token_threshold=settings.compression_threshold_prep,
        tail_turns=settings.compression_tail_turns_prep,
    ),
    "job": CompressionConfig(
        token_threshold=settings.compression_threshold_job,
        tail_turns=settings.compression_tail_turns_job,
    ),
    "document": CompressionConfig(
        token_threshold=settings.compression_threshold_document,
        tail_turns=settings.compression_tail_turns_document,
    ),
    "tracker": CompressionConfig(
        token_threshold=settings.compression_threshold_tracker,
        tail_turns=settings.compression_tail_turns_tracker,
    ),
}

def get_compression_config(engine_type: str) -> CompressionConfig:
    config = _ENGINE_CONFIGS.get(engine_type)

    if config is None:
        raise ValueError(f"Unknown engine type for compression config: {engine_type!r}")
    return config

def _estimate_tokens(messages: list[BaseMessage]) -> int:
    """Rough token estimate — 4 characters per token.
 
    Exact token counting would require a tokenizer call per message.
    This estimate is conservative enough to trigger compression before
    the context window is actually exhausted.
    """
    # Requires further assessment
    total_chars = sum(
        len(m.content) if isinstance(m.content, str) else sum(
            len(block.get("text", "")) for block in m.content if isinstance(block, dict)
        )
        for m in messages
    )
    return total_chars // 4

def _extract_tail(
    messages: list[BaseMessage],
    tail_turns: int,
) -> tuple[list[BaseMessage], list[BaseMessage]]:
    """Split messages into (to_compress, tail_to_keep).
 
    A turn is a human message and the assistant response that follows it.
    We keep the last `tail_turns` human+assistant pairs verbatim.
    """

    # Require's further review as well
    turn_boundary_indices: list[int] = []
    for i, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            turn_boundary_indices.append(i)
 
    if len(turn_boundary_indices) <= tail_turns:
        return [], messages
 
    split_at = turn_boundary_indices[-tail_turns]
    return messages[:split_at], messages[split_at:]

async def maybe_compress(
    messages: list[BaseMessage],
    engine_type: str,
    llm: ChatAnthropic,
    extra_context: str = "",
) -> list[BaseMessage]:
    """Compress messages if they exceed the engine's token threshold.
 
    Returns the original message list unchanged if compression is not needed.
    For the prep engine, pass the serialised topic_mastery JSON as
    extra_context so the model does not re-quiz covered material after
    compression.
    """
    # Subject o review as well
    config = get_compression_config(engine_type)
    estimated_tokens = _estimate_tokens(messages)


    if estimated_tokens <= config.tokens_threshold:
        return messages

    logger.info(
        "Compressing conversation for engine %r — estimated tokens: %d  threshold: %d",
        engine_type,
        estimated_tokens,
        config.token_threshold,
    )

    to_compress, tail = _extract_tail(messages, config.tail_turns)

    if not to_compress:
        logger.debug("Nothing to compress after tail extraction — skipping")
        return
     
    history_text = "\n\n".join(
        f"{m.__class__.__name__}: {m.content if isinstance(m.content, str) else str(m.content)}"
        for m in to_compress
    )

    human_content = COMPRESSION_HUMAN_TEMPLATE.format(
        history = history_text,
        extra_context=f"\n\nAdditional context to preserve:\n{extra_context}" if extra_context else "",
    )

    response = await llm.ainvoke([
        SystemMessage(content=COMPRESSION_SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ])
    briefing = SystemMessage(content=f"[Session summary]\n{response.content.strip()}")

    compressed= [briefing] + list[tail]

    logger.info(
        "Compression complete — %d messages → 1 briefing + %d tail messages",
        len(to_compress),
        len(tail),
    )

    return compressed

    