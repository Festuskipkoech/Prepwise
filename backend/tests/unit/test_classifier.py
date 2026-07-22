import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.classification.classifier import classify_message
from app.schemas.classification import ClassificationResult

# Helpers
def _make_mock_llm(response_text: str):
    """Return a mock LLM whose ainvoke returns a message with the given text."""
    mock_message = MagicMock()
    mock_message.content = response_text

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_message)
    return mock_llm

def _valid_response(engine_type: str, confidence: float = 0.95) -> str:
    return json.dumps({
        "engine_type": engine_type,
        "confidence": confidence,
        "reasoning": f"Message is clearly about {engine_type}.",
    })

# Correct classification for each engine type
@pytest.mark.asyncio
async def test_classifies_job():
    llm = _make_mock_llm(_valid_response("job"))
    result = await classify_message("Find me ML roles in Nairobi", llm)
    assert result.engine_type == "job"
    assert result.confidence == 0.95

@pytest.mark.asyncio
async def test_classifies_prep():
    llm = _make_mock_llm(_valid_response("prep"))
    result = await classify_message("Help me prepare for a data science interview", llm)
    assert result.engine_type == "prep"

@pytest.mark.asyncio
async def test_classifies_document():
    llm = _make_mock_llm(_valid_response("document"))
    result = await classify_message("Write me a resume for this Safaricom role", llm)
    assert result.engine_type == "document"

@pytest.mark.asyncio
async def test_classifies_tracker():
    llm = _make_mock_llm(_valid_response("tracker"))
    result = await classify_message("Why am I not getting past first rounds?", llm)
    assert result.engine_type == "tracker"

@pytest.mark.asyncio
async def test_classifies_unsupported():
    llm = _make_mock_llm(_valid_response("unsupported", confidence=0.1))
    result = await classify_message("What is the weather today?", llm)
    assert result.engine_type == "unsupported"

# Confidence boundary
# @pytest.mark.asyncio
async def test_confidence_zero_point_zero_is_valid():
    llm = _make_mock_llm(_valid_response("unsupported", confidence=0.0))
    result = await classify_message("gibberish", llm)
    assert result.confidence == 0.0

@pytest.mark.asyncio
async def test_confidence_one_point_zero_is_valid():
    llm = _make_mock_llm(_valid_response("job", confidence=1.0))
    result = await classify_message("Find me a job", llm)
    assert result.confidence == 1.0

# Parse failure fallback
@pytest.mark.asyncio
async def test_malformed_json_defaults_to_unsupported():
    llm = _make_mock_llm("this is not json at all")
    result = await classify_message("some message", llm)
    assert result.engine_type == "unsupported"
    assert result.confidence == 0.0

@pytest.mark.asyncio
async def test_empty_response_defaults_to_unsupported():
    llm = _make_mock_llm("")
    result = await classify_message("some message", llm)
    assert result.engine_type == "unsupported"

@pytest.mark.asyncio
async def test_partial_json_defaults_to_unsupported():
    llm = _make_mock_llm('{"engine_type": "job"')
    result = await classify_message("some message", llm)
    assert result.engine_type == "unsupported"

@pytest.mark.asyncio
async def test_json_with_unknown_engine_type_fails_validation():
    bad = json.dumps({
        "engine_type": "unknown_engine",
        "confidence": 0.9,
        "reasoning": "test",
    })
    llm = _make_mock_llm(bad)
    result = await classify_message("some message", llm)
    assert result.engine_type == "unsupported"

# Result is always a ClassificationResult
@pytest.mark.asyncio
async def test_result_is_classification_result_instance():
    llm = _make_mock_llm(_valid_response("job"))
    result = await classify_message("Find me a job", llm)
    assert isinstance(result, ClassificationResult)

@pytest.mark.asyncio
async def test_reasoning_field_is_populated_on_success():
    llm = _make_mock_llm(_valid_response("prep"))
    result = await classify_message("Prep me for interviews", llm)
    assert isinstance(result.reasoning, str)
    assert len(result.reasoning) > 0
    
@pytest.mark.asyncio
async def test_reasoning_field_populated_on_parse_failure():
    llm = _make_mock_llm("not json")
    result = await classify_message("anything", llm)
    assert "Parse failure" in result.reasoning
