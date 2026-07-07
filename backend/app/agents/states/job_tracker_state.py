from typing import Any
from typing_extensions import TypedDict

class TrackerState(TypedDict):
    application_data: dict[str, Any]
    analysis: dict[str, Any]
    error: str | None