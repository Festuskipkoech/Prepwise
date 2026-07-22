from app.vector.chunks import parse_profile_chunks

# Fixtures — markdown samples
FULL_PROFILE_MD = """
## Identity
Name: Festus Koech
Location: Nairobi, Kenya
Email: festus@example.com
Target Role: ML Engineer

## Skills

### Python
Stack: Python, FastAPI, SQLAlchemy
Depth: 5

### Machine Learning
Stack: PyTorch, scikit-learn, HuggingFace
Depth: 4

## Projects

### Prepwise
Stack: FastAPI, LangGraph, Qdrant, Next.js
An intelligent job search operating system.

### Sentiment Analyser
Stack: Python, BERT, Flask
Real-time sentiment classification API.

## Experience

### Senior ML Engineer at Safaricom
Period: 2022-2025
Stack: Python, TensorFlow, Spark
Led the ML platform team.

### Junior Data Scientist at Equity Bank
Period: 2020-2022
Stack: Python, pandas, scikit-learn
Built credit scoring models.

## Achievements
- Won the 2023 Nairobi AI Hackathon
- Published paper on bias detection

## Certifications
- AWS Certified ML Specialist
- Google Professional Data Engineer
"""

IDENTITY_ONLY_MD = """
## Identity
Name: Test User
"""

SKILLS_ONLY_MD = """
## Skills

### Python
Stack: Python, FastAPI
Depth: 3
"""

EMPTY_MD = ""

MISSING_SECTIONS_MD = """
## Identity
Name: Someone

## Skills

### Go
Stack: Go, gRPC
Depth: 2
"""

# Full profile — counts and types
def test_full_profile_produces_correct_chunk_count():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    assert len(chunks) == 9

def test_full_profile_has_one_identity_chunk():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    identity = [c for c in chunks if c.type == "identity"]
    assert len(identity) == 1

def test_full_profile_has_correct_skill_count():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    skills = [c for c in chunks if c.type == "skill"]
    assert len(skills) == 2

def test_full_profile_has_correct_project_count():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    projects = [c for c in chunks if c.type == "project"]
    assert len(projects) == 2

def test_full_profile_has_correct_experience_count():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    experience = [c for c in chunks if c.type == "experience"]
    assert len(experience) == 2

def test_full_profile_has_one_achievement_chunk():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    achievements = [c for c in chunks if c.type == "achievement"]
    assert len(achievements) == 1

def test_full_profile_has_one_certification_chunk():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    certs = [c for c in chunks if c.type == "certification"]
    assert len(certs) == 1

# user_id propagation
def test_all_chunks_carry_correct_user_id():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-xyz")
    assert all(c.user_id == "user-xyz" for c in chunks)

# Skill chunk — stack_tags and depth_level extraction
def test_skill_chunk_extracts_stack_tags():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    python_chunk = next(c for c in chunks if c.type == "skill" and c.name == "Python")
    assert "Python" in python_chunk.stack_tags
    assert "FastAPI" in python_chunk.stack_tags
    assert "SQLAlchemy" in python_chunk.stack_tags

def test_skill_chunk_extracts_depth_level():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    python_chunk = next(c for c in chunks if c.type == "skill" and c.name == "Python")
    assert python_chunk.depth_level == 5

def test_skill_chunk_without_stack_has_empty_tags():
    md = """
## Skills

### Soft Skills
Good communicator and team player.
"""
    chunks = parse_profile_chunks(md, "user-abc")
    assert chunks[0].stack_tags == []

# Experience chunk — period extraction
def test_experience_chunk_extracts_period():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    senior = next(
        c for c in chunks
        if c.type == "experience" and "Safaricom" in c.name
    )
    assert senior.period == "2022-2025"

def test_experience_chunk_without_period_is_none():
    md = """
## Experience

### Some Role
Led a team.
"""
    chunks = parse_profile_chunks(md, "user-abc")
    assert chunks[0].period is None

# Project chunk — stack_tags 
def test_project_chunk_extracts_stack_tags():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    prepwise = next(c for c in chunks if c.type == "project" and c.name == "Prepwise")
    assert "FastAPI" in prepwise.stack_tags
    assert "LangGraph" in prepwise.stack_tags

# Identity chunk — text content
def test_identity_chunk_contains_section_header():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    identity = next(c for c in chunks if c.type == "identity")
    assert identity.text.startswith("## Identity")

# Edge cases
def test_empty_markdown_returns_empty_list():
    assert parse_profile_chunks(EMPTY_MD, "user-abc") == []

def test_missing_sections_only_returns_present_chunks():
    chunks = parse_profile_chunks(MISSING_SECTIONS_MD, "user-abc")
    types = {c.type for c in chunks}
    assert "identity" in types
    assert "skill" in types
    assert "project" not in types
    assert "experience" not in types
    assert "achievement" not in types
    assert "certification" not in types

def test_identity_only_returns_one_chunk():
    chunks = parse_profile_chunks(IDENTITY_ONLY_MD, "user-abc")
    assert len(chunks) == 1
    assert chunks[0].type == "identity"

def test_skills_only_returns_one_skill_chunk():
    chunks = parse_profile_chunks(SKILLS_ONLY_MD, "user-abc")
    assert len(chunks) == 1
    assert chunks[0].type == "skill"
    assert chunks[0].name == "Python"

def test_chunk_text_is_non_empty_for_all_types():
    chunks = parse_profile_chunks(FULL_PROFILE_MD, "user-abc")
    for chunk in chunks:
        assert chunk.text.strip(), f"Empty text on chunk: {chunk.name}"
