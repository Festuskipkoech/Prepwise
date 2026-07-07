import re
import uuid
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

def _new_id() -> str:
    return str(uuid.uuid4())

def _extract_section(markdown: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, markdown, re.DOTALL)
    return match.group(1).strip() if match else ""

def chunk_profile(profile_text: str) -> list[Chunk]:
    chunks: list[Chunk] = []

    projects_raw = _extract_section(profile_text, "Projects")
    if projects_raw:
        project_blocks = re.split(r"\n###\s+", projects_raw)
        for block in project_blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            name = lines[0].strip("# ").strip()
            body = "\n".join(lines[1:]).strip()

            stack_match = re.search(r"Stack:\s*(.+)", body)
            stack_tags = (
                [t.strip() for t in stack_match.group(1).split(",")]
                if stack_match
                else []
            )

            metrics_match = re.search(r"Metrics:\s*(.+)", body)
            scale_metrics = metrics_match.group(1).strip() if metrics_match else ""

            chunks.append(
                Chunk(
                    id=_new_id(),
                    text=f"Project: {name}\n{body}",
                    metadata={
                        "type": "project",
                        "project_name": name,
                        "stack_tags": stack_tags,
                        "scale_metrics": scale_metrics,
                    },
                )
            )

    skills_raw = _extract_section(profile_text, "Skills")
    if skills_raw:
        skill_blocks = re.split(r"\n###\s+", skills_raw)
        for block in skill_blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            skill_name = lines[0].strip("# ").strip()
            body = "\n".join(lines[1:]).strip()

            depth_match = re.search(r"Depth:\s*(\d)", body)
            depth_level = int(depth_match.group(1)) if depth_match else 0

            chunks.append(
                Chunk(
                    id=_new_id(),
                    text=f"Skill: {skill_name}\n{body}",
                    metadata={
                        "type": "skill",
                        "skill_name": skill_name,
                        "depth_level": depth_level,
                    },
                )
            )

    experience_raw = _extract_section(profile_text, "Experience")
    if experience_raw:
        exp_blocks = re.split(r"\n###\s+", experience_raw)
        for block in exp_blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            role_name = lines[0].strip("# ").strip()
            body = "\n".join(lines[1:]).strip()

            company_match = re.search(r"Company:\s*(.+)", body)
            period_match = re.search(r"Period:\s*(.+)", body)
            stack_match = re.search(r"Stack:\s*(.+)", body)

            chunks.append(
                Chunk(
                    id=_new_id(),
                    text=f"Experience: {role_name}\n{body}",
                    metadata={
                        "type": "experience",
                        "role_name": role_name,
                        "company": company_match.group(1).strip() if company_match else "",
                        "period": period_match.group(1).strip() if period_match else "",
                        "stack_tags": (
                            [t.strip() for t in stack_match.group(1).split(",")]
                            if stack_match
                            else []
                        ),
                    },
                )
            )

    return chunks

def chunk_subtopic(
    subtopic_id: str,
    subject: str,
    topic: str,
    subtopic_name: str,
    concept: str,
    project_evidence: str,
    skill_tags: list[str],
) -> Chunk:
    text = (
        f"Subject: {subject}\n"
        f"Topic: {topic}\n"
        f"Subtopic: {subtopic_name}\n\n"
        f"Concept:\n{concept}\n\n"
        f"Project Evidence:\n{project_evidence}"
    )
    return Chunk(
        id=subtopic_id,
        text=text,
        metadata={
            "type": "subtopic",
            "subject": subject,
            "topic": topic,
            "subtopic": subtopic_name,
            "skill_tags": skill_tags,
        },
    )