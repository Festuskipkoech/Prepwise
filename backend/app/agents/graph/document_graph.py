from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
from qdrant_client import AsyncQdrantClient

from app.agents.prompts.document_prompts import (
    COVER_LETTER_GENERATION_PROMPT,
    JD_ANALYSIS_PROMPT,
    RESUME_GENERATION_PROMPT,
)
from app.agents.prompts.system_prompts import build_system_prompt
from app.agents.states.document_state import DocumentState
from app.agents.tools.document_utils import (
    parse_jd_analysis,
    retrieve_relevant_chunks,
)
from app.core.config import settings

def make_retrieve(qdrant: AsyncQdrantClient):
    async def retrieve(state: DocumentState) -> DocumentState:
        writer = get_stream_writer()
        writer({"type": "status", "message": "Retrieving relevant profile sections"})

        chunks = await retrieve_relevant_chunks(
            jd_text=state["jd_text"],
            qdrant=qdrant,
        )
        return {**state, "retrieved_chunks": chunks, "error": None}

    return retrieve

def make_analyse_jd(llm: BaseChatModel):
    async def analyse_jd(state: DocumentState) -> DocumentState:
        writer = get_stream_writer()
        writer({"type": "status", "message": "Analysing job description"})

        profile_text = Path(settings.profile_path).read_text(encoding="utf-8")
        system = build_system_prompt(profile_text)
        prompt = JD_ANALYSIS_PROMPT.format(jd_text=state["jd_text"])

        response = await llm.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )
        analysis = parse_jd_analysis(response.content)
        return {**state, "jd_analysis": analysis}

    return analyse_jd

def make_generate(llm: BaseChatModel):
    async def generate(state: DocumentState) -> DocumentState:
        writer = get_stream_writer()
        writer({"type": "status", "message": "Generating document"})

        profile_text = Path(settings.profile_path).read_text(encoding="utf-8")
        system = build_system_prompt(profile_text)

        chunks_text = "\n\n".join(
            chunk.get("text", "") for chunk in state["retrieved_chunks"]
        )

        prompt_template = (
            RESUME_GENERATION_PROMPT
            if state["document_type"] == "resume"
            else COVER_LETTER_GENERATION_PROMPT
        )
        prompt = prompt_template.format(
            jd_analysis=state["jd_analysis"],
            retrieved_chunks=chunks_text,
        )

        response = await llm.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]
        )

        return {**state, "generated_content": response.content}

    return generate

def build_document_graph(
    llm: BaseChatModel, qdrant: AsyncQdrantClient
) -> StateGraph:
    graph = StateGraph(DocumentState)

    graph.add_node("retrieve", make_retrieve(qdrant))
    graph.add_node("analyse_jd", make_analyse_jd(llm))
    graph.add_node("generate", make_generate(llm))

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "analyse_jd")
    graph.add_edge("analyse_jd", "generate")
    graph.add_edge("generate", END)

    return graph.compile()