from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
 
from app.agents.prompts.prep_prompts import (
    PREP_PATH_ANALYSIS_PROMPT,
    SUBTOPIC_GENERATION_PROMPT,
    QUESTION_GENERATION_PROMPT,
)
from app.agents.prompts.system_prompts import build_system_prompt
from app.agents.states.prep_state import (
    PrepPathState,
    QuestionState,
    SubtopicState,
)
from app.agents.tools.prep_utils import parse_json_response

def make_analyse_jd(llm: BaseChatModel):
    async def analyse_jd(state: PrepPathState) -> PrepPathState:
        writer = get_stream_writer()
        writer({"type": "status", "message": "Analysing job description against your profile"})
 
        profile_text = state["profile_text"]
        system = build_system_prompt(profile_text)
 
        prompt = PREP_PATH_ANALYSIS_PROMPT.format(jd_text=state["jd_text"])
        response = await llm.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
 
        try:
            parsed = parse_json_response(response.content)
        except Exception as exc:
            return {**state, "analysis": {}, "error": str(exc)}
 
        return {**state, "analysis": parsed, "error": None}
 
    return analyse_jd 
 
def make_build_prep_path(llm: BaseChatModel):
    async def build_prep_path(state: PrepPathState) -> PrepPathState:
        writer = get_stream_writer()
        writer({"type": "status", "message": "Building your prep path"})
 
        analysis = state["analysis"]
 
        generated_subject = analysis.get("job_subject", {})
 
        prep_path_data = {
            "strong_matches": analysis.get("strong_matches", {}),
            "needs_sharpening": analysis.get("needs_sharpening", {}),
            "gaps": analysis.get("gaps", {}),
            "likely_angles": {"angles": analysis.get("likely_angles", [])},
        }
 
        writer({"type": "status", "message": "Prep path ready"})
 
        return {
            **state,
            "generated_subject": generated_subject,
            "prep_path_data": prep_path_data,
        }
 
    return build_prep_path

def make_generate_subtopics(llm: BaseChatModel):
    async def generate_subtopics(state: SubtopicState) -> SubtopicState:
        profile_text = state["profile_text"]
        system = build_system_prompt(profile_text)
 
        prompt = SUBTOPIC_GENERATION_PROMPT.format(
            subject_name=state["subject_name"],
            topic_name=state["topic_name"],
            profile_text=profile_text,
        )
        response = await llm.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
 
        try:
            parsed = parse_json_response(response.content)
        except Exception as exc:
            return {**state, "subtopics": [], "error": str(exc)}
 
        return {**state, "subtopics": parsed, "error": None}
 
    return generate_subtopics 
 
def make_generate_questions(llm: BaseChatModel):
    async def generate_questions(state: QuestionState) -> QuestionState:
        profile_text = state["profile_text"]
        system = build_system_prompt(profile_text)
 
        prompt = QUESTION_GENERATION_PROMPT.format(
            subtopic_name=state["subtopic_name"],
            concept=state["concept"],
            project_evidence=state["project_evidence"],
        )
        response = await llm.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
 
        try:
            parsed = parse_json_response(response.content)
        except Exception as exc:
            return {**state, "questions": [], "error": str(exc)}
 
        return {**state, "questions": parsed, "error": None}
 
    return generate_questions

def build_prep_path_graph(llm:BaseChatModel) -> StateGraph:
    graph = StateGraph(PrepPathState)

    graph.add_node("analyse_jd",make_analyse_jd(llm))
    graph.add_node("build_prep_path", make_build_prep_path(llm))

    graph.set_entry_point("analyse_jd")
    graph.add_edge("analyse_jd", "build_prep_path")
    graph.add_edge("build_prep_path", END)

    return graph.complie()

def build_subtopic_graph(llm: BaseChatModel) -> StateGraph:
    graph = StateGraph(SubtopicState)
 
    graph.add_node("generate_subtopics", make_generate_subtopics(llm))
 
    graph.set_entry_point("generate_subtopics")
    graph.add_edge("generate_subtopics", END)
 
    return graph.compile()
 
 
def build_question_graph(llm: BaseChatModel) -> StateGraph:
    graph = StateGraph(QuestionState)
 
    graph.add_node("generate_questions", make_generate_questions(llm))
 
    graph.set_entry_point("generate_questions")
    graph.add_edge("generate_questions", END)
 
    return graph.compile()