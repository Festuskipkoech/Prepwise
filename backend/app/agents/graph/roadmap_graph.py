from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph
 
from app.agents.prompts.prep_prompts import ROADMAP_GENERATION_PROMPT
from app.agents.prompts.system_prompts import build_system_prompt
from app.agents.states.prep_state import RoadmapState
from app.agents.tools.prep_utils import parse_json_response

def make_generate_roadmap(llm: BaseChatModel):
    async def generate_roadmap(state: RoadmapState)-> RoadmapState:
        profile_text = state["profile_text"]
        system = build_system_prompt(profile_text)

        response = await llm.ainvoke(
            [                
                {"role": "system", "content": system},
                {"role": "user", "content": ROADMAP_GENERATION_PROMPT},
            ]
        )

        try:
            parsed = parse_json_response(response.content)
        except Exception as exc:
            return {**state, "subjects": [], "error": None}
        
        return {**state, "subjects":parsed, "error": None}
    
    return generate_roadmap

def build_roadmap_graph(llm: BaseChatModel) -> StateGraph:
    graph = StateGraph(RoadmapState)
    graph.add_node("generate_roadmap", make_generate_roadmap(llm))

    graph.set_entry_point("generate_roadmap")
    graph.add_edge("generate_roadmap", END)

    return graph.compile()