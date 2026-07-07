from qdrant_client import AsyncQdrantClient

from app.repositories.profile_repository import ProfileRepository
from app.vector.embeddings import embed_query


async def retrieve_relevant_chunks(
    jd_text: str,
    qdrant: AsyncQdrantClient,
    limit: int = 5,
) -> list[dict]:
    query_vector = await embed_query(jd_text)
    repo = ProfileRepository(qdrant)
    return await repo.search(query_vector=query_vector, limit=limit)


def parse_jd_analysis(raw: str) -> dict:
    result = {}
    for line in raw.strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def parse_document_output(raw: str) -> dict:
    content: dict = {}
    current_key = None
    current_value_lines: list[str] = []

    for line in raw.strip().splitlines():
        if ":" in line:
            colon_index = line.index(":")
            potential_key = line[:colon_index].strip()
            if potential_key and " " not in potential_key:
                if current_key:
                    content[current_key] = " ".join(current_value_lines).strip()
                current_key = potential_key
                current_value_lines = [line[colon_index + 1:].strip()]
                continue
        if current_key:
            current_value_lines.append(line.strip())

    if current_key:
        content[current_key] = " ".join(current_value_lines).strip()

    return _structure_document(content)


def _structure_document(flat: dict) -> dict:
    structured: dict = {}

    for key, value in flat.items():
        if not value:
            continue

        if key == "profile_summary":
            structured["profile_summary"] = value

        elif key == "skills":
            structured["skills"] = value

        elif key == "education":
            structured["education"] = value

        elif key == "certifications":
            structured["certifications"] = value

        elif key.startswith("experience_"):
            parts = key.split("_")
            if len(parts) < 3:
                continue
            index = parts[1]
            field = "_".join(parts[2:])
            experiences = structured.setdefault("experience", {})
            entry = experiences.setdefault(index, {})
            if field.startswith("bullet"):
                entry.setdefault("bullets", []).append(value)
            else:
                entry[field] = value

        elif key.startswith("project_"):
            parts = key.split("_")
            if len(parts) < 3:
                continue
            index = parts[1]
            field = "_".join(parts[2:])
            projects = structured.setdefault("projects", {})
            entry = projects.setdefault(index, {})
            entry[field] = value

        elif key in (
            "opening_paragraph",
            "body_paragraph_1",
            "body_paragraph_2",
            "closing_paragraph",
        ):
            structured[key] = value

    if "experience" in structured:
        structured["experience"] = list(structured["experience"].values())

    if "projects" in structured:
        structured["projects"] = list(structured["projects"].values())

    return structured