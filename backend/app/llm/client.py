import logging
from dataclasses import dataclass
 
from langchain_anthropic import ChatAnthropic
 
from app.core.config import settings
 
logger = logging.getLogger(__name__)

@dataclass
class LLMClient:
    large: ChatAnthropic
    small: ChatAnthropic

def build_llm_client() -> LLMClient:
    large = ChatAnthropic(
        model = settings.llm_large_model,
        anthropic_api_key = settings.anthropic_api_key,
        max_tokens = 8096,
        temperature=0.7
    )
    small = ChatAnthropic(
        model=settings.llm_small_model,
        anthropic_api_key=settings.anthropic_api_key,
        max_tokens=2048,
        temperature=0.0,
    )
        
    logger.info(
        "LLM client initialised — large: %s  small: %s",
        settings.llm_large_model,
        settings.llm_small_model,
    )
    return LLMClient(large=large, small=small)