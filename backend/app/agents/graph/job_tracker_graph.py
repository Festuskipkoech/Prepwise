import json

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from app.agents.prompts.job_tracker_prompts import PATTERN_ANALYSIS_PROMPT
from app.agents.states.job_tracker_state import TrackerState
from app.agents.tools.prep_utils import parse_json_response

def make_analyse(llm: BaseChatModel):
    async def analyse(state: TrackerState) -> TrackerState:
        writer = get_stream_writer()
        writer({"type": "status", "message": "Analysing your application history"})

        prompt = PATTERN_ANALYSIS_PROMPT.format(
            application_data=json.dumps(state["application_data"], indent=2)
        )

        response = await llm.ainvoke(
            [{"role": "user", "content": prompt}]
        )

        writer({"type": "status", "message": "Building pattern report"})

        try:
            parsed = parse_json_response(response.content)
        except Exception as exc:
            return {**state, "analysis": {}, "error": str(exc)}

        return {**state, "analysis": parsed, "error": None}

    return analyse

def build_tracker_graph(llm: BaseChatModel) -> StateGraph:
    graph = StateGraph(TrackerState)

    graph.add_node("analyse", make_analyse(llm))

    graph.set_entry_point("analyse")
    graph.add_edge("analyse", END)

    return graph.compile()