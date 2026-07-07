from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph  import END, StateGraph

from app.agents.states.job_search_state import JobSearchState
from app.agents.tools.job_search import fetch_job_listings, score_all_jobs

async def search(state: JobSearchState) -> JobSearchState:
    raw_results = await fetch_job_listings(
        query = state["query"],
        locations = state["location"],
        limit = state["limit"],
    )
    return {**state, "raw_results": raw_results, "error": None}

async def score(state: JobSearchState) -> JobSearchState:
    scored = await score_all_jobs(
        jobs = state["raw_results"],
        profile_text = state["profile_text"],
    )
    return {**state, "scored_results": scored}

def build_job_search_graph(llm: BaseChatModel) -> StateGraph:
    graph = StateGraph(JobSearchState)

    graph.add_node("search", search)
    graph.add_node("score", score)

    graph.set_entry_point("search")
    graph.add_edge("search", "score")
    graph.add_edge("score", END)

    return graph.compile()