import json
import httpx
from langchain_core.language_models.chat_models  import BaseChatModel

from app.agents.prompts.job_search_prompts import JOB_SCORING_PROMPT
from app.agents.prompts.job_search_context_prompts import SEARCH_CONTEXT_PROMPT
from app.agents.prompts.system_prompts import build_system_prompt
from app.core.config import settings
from app.llm.router import LLMTask, resolve_model
from app.llm.client import build_llm_client

SERP_API_URL = "https://serpapi.com/search"

async def fetch_job_listings(query: str, location: str, limit: int) -> list[dict]:
    params = {
        "engine": "google_jobs",
        "q":f"{query} {location}",
        "api_key": settings.serp_api_key,
        "num": limit
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(SERP_API_URL, params=params)
        response.raise_for_status()
    data = response.json()
    job_results = data.get("jobs_results", [])
    
    results = []
    for job in job_results[:limit]:
        title = job.get("link", "").strip()
        source_url = job.get("link", "").strip()

        if not title or not source_url:
            continue

        snippet = job.get("description", "")
        if not snippet:
            extensions = job.get("extensions", [])
            snippet = " ".join(extensions) if extensions else ""
        results.append(
            {
                "title": title,
                "company": job.get("company_name", "").strip(),
                "source_url": source_url,
                "job_id": job.get("job_id", ""),
                "location": job.get("location", ""),
                "via": job.get("via", ""),
                "snippet": snippet[:500],
            }
        )
        return results
    
async def score_job(
    job: dict,
    profile_summary: str,
) -> dict:
    model_name = resolve_model(LLMTask.JOB_SCORING)
    haiku = build_llm_client(model_name)
    prompt = JOB_SCORING_PROMPT.format(
        profile_summary = profile_summary,
        title = job.get("title", ""),
        company = job.get("company", ""),
        snippet = job.get("snippet", "")
    )
    response = await haiku.ainvoke([{"role": "user", "content": prompt}])
    try:
        parsed = json.loads(response.content)
        fit_score = parsed.get("fit_score", 0)
        fit_reason = parsed.get("fit_reason", "")
    except (json.JSONDecodeError, AttributeError):
        fit_score = 0
        fit_reason = "Could not score this listing"
    return {**job, "fit_score": fit_score, "fit_reason": fit_reason}

async def score_all_jobs(
    jobs: list[dict],
    profile_text: str,
    llm: BaseChatModel,
) -> list[dict]:
    profile_summary = profile_text[:1500]

    scored = []
    for job in jobs:
        scored_job  = await score_job(job, profile_summary, llm)
        scored.append(scored_job)
    return sorted(scored, key = lambda x: x["fit_score"], reverse=True)

async def generate_search_context(
    prfoile_text: str,
    llm: BaseChatModel,
) -> dict:
    system = build_system_prompt(prfoile_text)
    response  = await llm.ainvoke(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": SEARCH_CONTEXT_PROMPT},
        ]
    )

    try:
        return json.loads(response.content)
    except (json.JSONDecodeError, AttributeError):
        return {
            "suggested_titles": [],
            "recommended_keywords": [],
            "avoid_titles": [],
            "strongest_lane": ""
        }
