# Document Engine

## Overview

The document engine generates tailored resumes and cover letters through conversation. It retrieves the most relevant parts of the user's profile for the target role, analyses the job description, writes a polished draft, streams it in real time, and then enters an iterative editing loop where the user can request any changes through natural conversation. Output is always markdown. The frontend renders it to PDF. The agent never thinks about formatting.

---

## Conversation Design

### Agent personality

A precise, experienced writer who understands ATS systems, hiring managers, and how to make experience land on paper. Direct. Does not pad. Confident enough to write without asking unnecessary questions. Asks one clarifying question only when the decision would materially change the document.

### Conversation flow

**Turn 1 — with a job reference ("write me a resume for the Safaricom ML role"):**

The agent checks if this job is saved. If it is, it retrieves the JD. It calls `retrieve_relevant_profile_chunks` with the JD as the query to get the most relevant profile sections. It calls `extract_jd_keywords` to understand what the role is optimising for. Then it writes. No questions unless there is a genuine ambiguity that would materially change the document.

**Turn 1 — without a job reference ("write me a resume"):**

The agent checks recent job searches. If there are saved jobs, it surfaces them:

"Which role is this for? I can see you have a few saved — pick one and I will tailor it properly."

If no saved jobs, it asks one question:

"What role are you applying for? Paste the job description or describe the position and I will build from there."

**Turn 1 — specific enough to write immediately:**

The agent acknowledges and begins writing:

"On it. Pulling the most relevant parts of your profile for this role."

A status event fires. The document streams in real time. The user watches it being written.

**Turn 2+ — editing:**

The user can say anything. The agent treats every message as a precise editorial instruction:

- "Make the experience section more concise" → tightens only the experience section
- "Add more emphasis on the NLP projects" → moves or expands NLP content
- "The tone feels too formal" → rewrites in a warmer register
- "Can you rewrite the summary?" → rewrites only the summary
- "Add a skills section" → adds it without changing the rest

The agent applies the change, streams the updated document, and briefly notes what changed. It does not rewrite sections that were not asked to change.

**User preference accumulation:**

If the user asks for conciseness twice, the agent learns that conciseness is a priority for this user and applies it as a lens to all subsequent edits without being told again. Preferences accumulate in `state["user_preferences"]`.

**Document versioning:**

Every time the agent produces a new version of the document — initial draft or any edit — a new row is written to the `documents` table with an incremented `version` number. The full markdown content is stored. The user can request previous versions in conversation: "go back to the version before you added the skills section."

**Cover letter after resume:**

When the user is satisfied with the resume and asks for a cover letter, the agent writes it immediately — the role context is already loaded. No re-explanation needed.

**Download:**

When the user is satisfied, the frontend renders the current markdown to PDF via `react-pdf`. No backend involvement in rendering. The backend only stores markdown.

---

## LangGraph Graph

### State

```python
class DocumentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    chat_id: str
    document_type: str                  # resume | cover_letter
    job_id: str
    jd_text: str
    jd_keywords: list[str]
    profile_chunks: list[str]
    current_document_md: str            # the live markdown draft
    document_version: int
    document_id: str                    # UUID of current documents row
    edit_history: list[dict]            # {version, instruction, changed_sections}
    user_preferences: dict              # conciseness, tone, emphasis accumulated
    waiting_for: str
```

### Nodes

```
assess_context
    Determines if enough context exists to write immediately
    Checks for: document_type, job reference, JD text
    Routes to load_job or ask_clarification accordingly

load_job
    Retrieves JD from PostgreSQL if job_id is known
    Or parses JD text the user provided directly
    Populates state["jd_text"]

extract_jd_context
    Small LLM call: extracts ATS keywords, required skills, role priorities
    Populates state["jd_keywords"]

retrieve_profile_chunks
    Calls retrieve_relevant_profile_chunks tool with JD as query
    Returns top 5-7 semantically relevant profile sections
    Populates state["profile_chunks"]

generate_document
    Large LLM call: writes the full document in markdown
    Has access to: profile_chunks, jd_text, jd_keywords, document_type, user_preferences
    Saves new version to documents table
    Increments state["document_version"]
    Populates state["current_document_md"] and state["document_id"]
    Streams token by token

apply_edit
    Parses the user's edit instruction
    Identifies which sections of the document are affected
    Large LLM call: applies the edit surgically — only changes what was asked
    Saves new version to documents table
    Increments state["document_version"]
    Updates state["current_document_md"]
    Updates state["edit_history"]
    Updates state["user_preferences"] if a pattern is detected
    Streams the updated document

revert_version
    Loads a previous version from documents table by version number
    Restores state["current_document_md"]
    Updates state["document_version"]

ask_clarification
    Generates one targeted clarifying question
    Updates state["waiting_for"]

generate_response
    For conversational turns that do not produce a new document version
    Acknowledges, confirms, offers next steps
```

### Edges

```
START -> assess_context

assess_context -> load_job                  (job reference exists)
assess_context -> ask_clarification         (need role or JD)
assess_context -> apply_edit                (document exists, user requesting change)
assess_context -> revert_version            (user requesting previous version)
assess_context -> generate_document         (JD provided inline, no saved job needed)

load_job -> extract_jd_context
extract_jd_context -> retrieve_profile_chunks
retrieve_profile_chunks -> generate_document

generate_document -> END
apply_edit -> END
revert_version -> END
ask_clarification -> END
generate_response -> END
```

---

## Tools

```python
@tool
def get_recent_job_searches(limit: int = 5) -> list:
    """Retrieve the user's recently saved jobs.
    Use when the user has not specified a target role."""

@tool
def get_job_description(job_id: str) -> str:
    """Retrieve the full job description for a saved job by its ID."""

@tool
def retrieve_relevant_profile_chunks(jd_text: str, top_k: int = 7) -> list[str]:
    """Retrieve the most relevant sections of the user's profile
    for the given job description using semantic search.
    Always use this before generating a document — never use the full profile."""

@tool
def extract_jd_keywords(jd_text: str) -> list[str]:
    """Extract ATS keywords, required skills, and role priorities from a job description.
    Use this to ensure the document uses the right language."""

@tool
def save_document_version(
    job_id: str,
    chat_session_id: str,
    document_type: str,
    content_md: str,
    version: int
) -> str:
    """Save a document version to the database. Returns the document_id."""

@tool
def get_document_version(document_id: str, version: int) -> str:
    """Retrieve a specific version of a document by version number.
    Use when the user asks to revert to a previous version."""

@tool
def get_long_term_memories() -> str:
    """Retrieve facts remembered about this user from previous sessions."""
```

---

## System Prompt

```
You are a precise, experienced professional writer who specialises in job application documents.
You understand how ATS systems work, how hiring managers read resumes, and how to make
experience land on paper.

Your operating rules:
- Always use the provided profile chunks and JD keywords — never invent experience or skills.
- Write in the language of the job description. If the JD says "cross-functional collaboration",
  the document should say "cross-functional collaboration", not "worked with other teams".
- Place ATS keywords naturally. Never stuff them. If a keyword does not fit naturally, leave it out.
- Be specific and metric-driven wherever the profile provides numbers. "Reduced latency by 40%"
  is always better than "improved system performance".
- When editing, change only what was asked. Do not touch sections the user did not mention.
- Accumulate the user's preferences across the conversation. If they asked for conciseness twice,
  it is a priority — apply it going forward without being asked again.
- After every edit, briefly state what changed: "Tightened the experience section and removed
  the objective statement as requested."
- When asked to revert, do so cleanly and confirm the version you reverted to.
- Do not explain your writing choices unless asked. Just write.
- Do not pad. Every sentence must earn its place.

Output format:
Always return the full document in markdown. Use these section headers exactly:

For resumes:
# [Full Name]
[contact line]

## Summary
## Experience
### [Role Title] — [Company] ([Period])
## Skills
## Projects
### [Project Name]
## Education
## Certifications

For cover letters:
[Date]
[Hiring Manager Name if known, else "Hiring Team"]
[Company]

[Opening paragraph]
[Body paragraphs]
[Closing paragraph]

[Sign-off]
[Name]

Return the full document every time, even for small edits. The frontend always renders
the complete current version.
```

---

## Database Schema

```
documents
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
  job_id            UUID REFERENCES jobs(id) ON DELETE SET NULL
  chat_session_id   UUID REFERENCES chat_sessions(id) ON DELETE SET NULL
  type              TEXT NOT NULL               -- resume | cover_letter
  content_md        TEXT NOT NULL               -- full markdown content
  version           INTEGER NOT NULL DEFAULT 1
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
```

Each edit creates a new row. Version numbers are scoped to the `(chat_session_id, type)` combination. Retrieving version history: query by `chat_session_id` and `type`, order by `version DESC`.

Indexes:
- `documents(user_id)` for all user documents
- `documents(job_id)` for documents tied to a specific job
- `documents(chat_session_id, type, version DESC)` for version history retrieval

---

## Frontend Rendering

The frontend receives markdown from the server. `react-pdf` renders it into a polished PDF. The rendering logic lives entirely in the frontend — the backend never touches PDF generation.

The frontend maintains a live preview that updates as each token arrives during streaming. The user sees the document being written in real time in the preview pane.

Download triggers `react-pdf`'s `PDFDownloadLink` component. No backend round-trip for download.

---

## Streaming Pattern

`generate_document` and `apply_edit` both stream via `stream_mode=["custom", "messages"]`:

- Status events before writing begins: "Analysing the job description...", "Pulling your most relevant experience..."
- Token events: the markdown document streams character by character
- Done event: carries `document_id` and `version` number so the frontend can store the reference

The entire document streams even on edits. The frontend replaces the current preview with the incoming stream.

---

## Seamless Conversation Checklist

- `state["current_document_md"]` always holds the latest draft — agent never loses what it wrote
- `state["user_preferences"]` accumulates editing patterns without the user having to repeat themselves
- `state["edit_history"]` gives the agent memory of what changed and when across the session
- `state["jd_keywords"]` loaded once, used on every subsequent edit to maintain keyword integrity
- `state["profile_chunks"]` loaded once, available throughout the session
- Surgical edits — only changed sections rewritten, rest preserved intact
- Version revert supported through explicit database versioning
- Cover letter after resume requires no re-loading of context
- Long-term memories loaded at session start for user preference continuity across sessions