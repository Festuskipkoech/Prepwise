import json
import re

from datetime import datetime, timezone

def parse_json_response(raw: str) -> list | dict:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)

def build_roadmap_subjects_data(
    parsed: list[dict],
) -> tuple[list[dict], list[dict]]:
    subjects_data = []
    topics_data = []

    for subject_index, subject in enumerate(parsed):
        subjects_data.append(
            {
                "name": subject["name"],
                "description": subject.get("description", ""),
                "order_index": subject_index,
                "source": "roadmap",
            }
        )
        for topic_index, topic in enumerate(subject.get("topics", [])):
            topics_data.append(
                {
                    "subject_name": subject["name"],
                    "name": topic["name"],
                    "description": topic.get("description", ""),
                    "order_index": topic_index,
                    "status": "not_started",
                }
            )

    return subjects_data, topics_data

def build_subtopics_data(
    topic_id: str, parsed: list[dict]
) -> list[dict]:
    return [
        {
            "topic_id": topic_id,
            "name": item["name"],
            "concept": item.get("concept", ""),
            "project_evidence": item.get("project_evidence", ""),
            "order_index": item.get("order_index", index),
            "status": "not_started",
            "generated_at": datetime.now(timezone.utc),
        }
        for index, item in enumerate(parsed)
    ]

def build_questions_data(
    subtopic_id: str, parsed: list[dict]
) -> list[dict]:
    return [
        {
            "subtopic_id": subtopic_id,
            "type": item.get("type", "theoretical"),
            "question": item["question"],
            "answer": item["answer"],
            "order_index": item.get("order_index", index),
            "generated_at": datetime.now(timezone.utc),
        }
        for index, item in enumerate(parsed)
    ]