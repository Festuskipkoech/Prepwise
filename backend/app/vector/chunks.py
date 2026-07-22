import logging
import re
from dataclasses import dataclass, field
from typing import Literal
 
logger = logging.getLogger(__name__)
 
ChunkType = Literal["identity", "skill", "project", "experience", "achievement", "certification"] 
 
@dataclass
class ProfileChunk:
    user_id: str
    type: ChunkType
    name: str
    text: str
    stack_tags: list[str] = field(default_factory=list)
    depth_level: int | None = None
    period: str | None = None

def _extract_stack_tags(block: str) -> list[str]:
    match = re.search(r"Stack:\s*(.+)", block, re.IGNORECASE)
    if not match:
        return []
    raw = match.group(1)
    return [tag.strip() for tag in raw.split(",") if tag.strip()]

def _extract_depth(block: str) -> int | None:
    match = re.search(r"Depth:\s*(\d)", block, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)) 
 
def _extract_period(block: str) -> str | None:
    match = re.search(r"Period:\s*(.+)", block, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()

def _split_h3_blocks(section: str) -> list[tuple[str, str]]:
    """Split a markdown section into (heading_name, block_text) pairs on ### boundaries."""
    pattern = re.compile(r"^###\s+(.+)$", re.MULTILINE)

    headings =list(pattern.finditer(section))
    if not headings:
        return []

    blocks = []
    for i, match in enumerate(headings):
        name = match.group(1).strip()
        start = match.end()
        end = headings[i + 1].start() if i +1 < len(headings) else len(section)
        body = section[start:end].strip()
        blocks.append((name, f"### {name}\n{body}"))

    return blocks

def parse_profile_chunks(normalised_md: str, user_id: str) -> list[ProfileChunk]:
    chunks: list[ProfileChunk] = []

    section_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    section_matches = list(section_pattern.finditer(normalised_md))

    sections: dict[str, str]  = {}
    for i, match in enumerate(section_matches):
        heading = match.group(1).strip().lower()
        start = match.end()
        end = section_matches[i + 1].start() if i + 1 < len(section_matches) else len(normalised_md)
        sections[heading] = normalised_md[start:end].strip()

    # Identity block — the entire ## Identity section is one chunk
    if "identity" in sections:
        chunks.append(
            ProfileChunk(
                user_id=user_id,
                type="identity",
                name="Identity",
                text=f"## Identity\n{sections['identity']}",
            )
        )
 
    # Skills — one chunk per ### Skill block
    if "skills" in sections:
        for name, block in _split_h3_blocks(sections["skills"]):
            chunks.append(
                ProfileChunk(
                    user_id=user_id,
                    type="skill",
                    name=name,
                    text=block,
                    stack_tags=_extract_stack_tags(block),
                    depth_level=_extract_depth(block),
                )
            )
 
    # Projects — one chunk per ### Project block
    if "projects" in sections:
        for name, block in _split_h3_blocks(sections["projects"]):
            chunks.append(
                ProfileChunk(
                    user_id=user_id,
                    type="project",
                    name=name,
                    text=block,
                    stack_tags=_extract_stack_tags(block),
                )
            )
 
    # Experience — one chunk per ### Role block
    if "experience" in sections:
        for name, block in _split_h3_blocks(sections["experience"]):
            chunks.append(
                ProfileChunk(
                    user_id=user_id,
                    type="experience",
                    name=name,
                    text=block,
                    stack_tags=_extract_stack_tags(block),
                    period=_extract_period(block),
                )
            )
 
    # Achievements — entire section as one chunk
    if "achievements" in sections:
        chunks.append(
            ProfileChunk(
                user_id=user_id,
                type="achievement",
                name="Achievements",
                text=f"## Achievements\n{sections['achievements']}",
            )
        )
 
    # Certifications — entire section as one chunk
    if "certifications" in sections:
        chunks.append(
            ProfileChunk(
                user_id=user_id,
                type="certification",
                name="Certifications",
                text=f"## Certifications\n{sections['certifications']}",
            )
        )
 
    logger.debug("Parsed %d chunks for user %s", len(chunks), user_id)
    return chunks

 