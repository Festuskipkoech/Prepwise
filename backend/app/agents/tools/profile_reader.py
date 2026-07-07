from pathlib import Path

from langchain_core.tools import tool

from app.core.config import settings
from app.exceptions.profile import ProfileNotFoundError
from app.vector.chunks import chunk_profile

@tool
def read_profile() -> dict:
    """
    Reads the master profile markdown file from disk and chunks it
    into structured segments ready for embedding.
    """
    profile_path = Path(settings.profile_path)

    if not profile_path.exists():
        raise ProfileNotFoundError()

    profile_text = profile_path.read_text(encoding="utf-8")
    chunks = chunk_profile(profile_text)

    return {
        "profile_text": profile_text,
        "chunks": [
            {"id": c.id, "text": c.text, "metadata": c.metadata}
            for c in chunks
        ],
    }