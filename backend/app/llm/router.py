from enum import StrEnum

from langchain_anthropic import ChatAnthropic
from fastapi import Request

from app.llm.client import LLMClient

class LLMTask(StrEnum):
    # Large model tasks — require reasoning, writing quality, nuanced understanding
    PROFILE_NORMALISE = "profile_normalise"
    RESUME_GENERATE = "resume_generate"
    COVER_LETTER_GENERATE = "cover_letter_generate"
    ROADMAP_GENERATE = "roadmap_generate"
    JD_ANALYSE = "jd_analyse"
    AGENT_RESPONSE = "agent_response"

    # Small model tasks — classification, extraction, scoring, summarisation
    ENGINE_CLASSIFY = "engine_classify"
    ENGINE_VALIDATE = "engine_validate"
    JOB_SCORE = "job_score"
    CONVERSATION_COMPRESS = "conversation_compress"
    CHAT_TITLE = "chat_title"
    ATS_EXTRACT = "ats_extract"

_SMALL_TASKS = {
    LLMTask.ENGINE_CLASSIFY,
    LLMTask.ENGINE_VALIDATE,
    LLMTask.JOB_SCORE,
    LLMTask.CONVERSATION_COMPRESS,
    LLMTask.CHAT_TITLE,
    LLMTask.ATS_EXTRACT,
}

def get_llm(client: LLMClient, task: LLMTask) -> ChatAnthropic:
    if task in _SMALL_TASKS:
        return client.small
    return client.large

def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client