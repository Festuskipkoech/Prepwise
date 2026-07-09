from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings

def build_llm_client(model_name: str | None = None) -> BaseChatModel:
    target = model_name or settings.llm_large_model
    if "claude" in target:
        return ChatAnthropic(
            model = target,
            api_key = settings.anthropic_api_key,
            streaming =True,
        )
    if "gpt" in target:
        return ChatOpenAI(
            model=target,
            api_key = settings.openai_api_key,
            streaming=True,
        )
    raise ValueError(f"Unsupported mode: {target}")