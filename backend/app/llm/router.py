from enum import StrEnum

from app.core.config import settings

class LLMTask(StrEnum):
    ROADMAP_GENERATION = "roadmap_generation"
    SUBTOPIC_GENERATION = "subtopic_generation"
    QUESTION_GENERATION = "question_generation"
    RESUME_GENERATION = "resume_generation"
    COVER_LETTER_GENERATION = "cover_letter_generation"
    JD_ANALYSIS = "jd_analysis"
    PREP_PATH_GENERATION = "prep_path_generation"
    JOB_SUBJECT_GENERATION = "job_subject_generation"
    JOB_SCORING = "job_scoring"
    TRACKER_SUMMARY = "tracker_summary"
    CLASSIFICATION = "classification"


SONNET_TASKS = {
    LLMTask.ROADMAP_GENERATION,
    LLMTask.SUBTOPIC_GENERATION,
    LLMTask.QUESTION_GENERATION,
    LLMTask.RESUME_GENERATION,
    LLMTask.COVER_LETTER_GENERATION,
    LLMTask.JD_ANALYSIS,
    LLMTask.PREP_PATH_GENERATION,
    LLMTask.JOB_SUBJECT_GENERATION,
}

HAIKU_TASKS = {
    LLMTask.JOB_SCORING,
    LLMTask.TRACKER_SUMMARY,
    LLMTask.CLASSIFICATION,
}


def resolve_model(task: LLMTask) -> str:
    if task in SONNET_TASKS:
        return settings.llm_large_model
    if task in HAIKU_TASKS:
        return settings.llm_small_model
    return settings.llm_large_model