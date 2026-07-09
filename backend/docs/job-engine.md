# Job Search Engine

## Overview

The job search engine helps users find roles that match their background. It does not dump raw search results — it understands what the user is looking for, retrieves their profile context, searches intelligently, scores results against their background, and returns ranked results in markdown. The entire interaction is conversational and multi-turn.

---

## Conversation Design

### Agent personality

Sharp and efficient. Like a recruiter who knows the user's background deeply and does not waste time on irrelevant roles. Acts decisively when it has enough context. Asks exactly one focused question when it does not.

### Conversation flow

**Turn 1 — new chat, vague message ("help me find a job"):**

The agent does not immediately search. It calls `get_profile_context` silently to understand the user's background, then asks one targeted question informed by what it found:

"Based on your background in NLP and Python, are you targeting ML engineer roles or leaning more toward research positions?"

The question is personalised, not generic. It uses what the profile revealed.

**Turn 1 — new chat, specific message ("find me senior ML engineering roles in Nairobi"):**

The agent has enough. It calls `get_profile_context` to load relevant background, constructs a search query, calls `search_jobs`, scores the results internally, and returns the top 5-7 in markdown card format. No unnecessary questions.

**Turn 2+ — refinement ("these don't look right, I want remote roles"):**

The agent accumulates the new constraint in session state and searches again with the updated parameters. It does not re-explain. It says "got it, searching remote roles" and acts. Every constraint the user adds in the conversation is remembered for the remainder of the session.

**Picking a job ("I like the third one"):**

Agent saves the job to the database, confirms it, and offers the natural next step:

"Saved. Want me to tailor your resume for this role or start prepping for their interview process?"

If the user says yes to either, the agent signals a cross-engine handoff — it does not switch engines itself. It informs the user and suggests opening a new prep or document chat with this job's context pre-loaded.

### Cross-engine drift handling

If mid-conversation the user says "write me a cover letter for this job", the current engine agent responds:

"That is the document engine. Want me to open a new document chat with this job's description already loaded so you can jump straight into writing?"

It never tries to handle document generation itself.

---

## LangGraph Graph

### State

```python
class JobSearchState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    chat_id: str
    profile_context: str
    search_query: str
    search_filters: dict
    raw_results: list
    scored_results: list
    saved_job_ids: list[str]
    user_constraints: dict          # accumulated: location, remote, seniority, etc.
    last_action: str                # what the agent last did
    waiting_for: str                # what the agent is waiting for from the user, if anything
```

### Nodes

```
classify_intent
    Determines from the current message and state whether to:
    - ask a clarifying question
    - search with current context
    - refine an existing search
    - save a job
    - hand off to another engine

load_profile_context
    Calls get_profile_context tool with a query derived from the conversation
    Populates state["profile_context"]

construct_query
    Uses the large LLM to build an optimal SerpAPI query from:
    - the user's stated intent
    - accumulated constraints in state["user_constraints"]
    - profile context

search_jobs
    Calls the search_jobs tool
    Populates state["raw_results"]

score_results
    Small LLM call: scores each result 0-100 against profile context
    Filters results below threshold
    Sorts by score
    Populates state["scored_results"]

generate_response
    Large LLM call: formats scored_results into markdown card output
    Streams tokens via get_stream_writer and stream_mode=["messages"]

save_job
    Persists selected job to PostgreSQL jobs table
    Updates state["saved_job_ids"]

ask_clarification
    Generates a single focused clarifying question
    Updates state["waiting_for"]
```

### Edges

```
START -> classify_intent

classify_intent -> load_profile_context       (if profile not yet loaded)
classify_intent -> construct_query            (if enough context to search)
classify_intent -> ask_clarification          (if more context needed)
classify_intent -> save_job                   (if user picked a job)
classify_intent -> generate_response          (if responding to drift or handoff)

load_profile_context -> classify_intent       (re-evaluate with profile loaded)
construct_query -> search_jobs
search_jobs -> score_results
score_results -> generate_response
generate_response -> END
save_job -> generate_response
ask_clarification -> END
```

---

## Tools

```python
@tool
def get_profile_context(query: str) -> str:
    """Retrieve relevant sections from the user's profile based on the query.
    Use this to understand the user's background before searching."""

@tool
def get_recent_job_searches(limit: int = 5) -> list:
    """Retrieve the user's recently saved or searched jobs.
    Use to give context about what roles they have already explored."""

@tool
def search_jobs(query: str, location: str = "", filters: dict = {}) -> list:
    """Search for job listings using the provided query and optional filters.
    Filters can include: remote (bool), seniority (str), job_type (str)."""

@tool
def save_job(
    title: str,
    company: str,
    source_url: str,
    jd_text: str,
    source: str = "search"
) -> str:
    """Save a job to the user's tracker. Returns the new job_id."""

@tool
def get_long_term_memories() -> str:
    """Retrieve facts remembered about this user from previous sessions."""
```

---

## System Prompt

```
You are a sharp, efficient career advisor helping a job seeker find the right roles.

You have access to the user's professional profile and can search for job listings.

Your operating rules:
- Always load the user's profile context before searching — you need to understand their background to search intelligently and to personalise your questions.
- When you have enough context, search immediately. Do not ask unnecessary questions.
- When you need more information, ask exactly one focused question. Never ask two questions at once.
- Use what you know about the user from their profile to make your questions specific and relevant. Never ask generic questions.
- After searching, score and filter results yourself before presenting them. Return only the most relevant 5-7 results.
- Accumulate every constraint the user gives you across the conversation. Do not forget that they said "remote only" three turns ago.
- When the user picks a job, save it and offer the natural next step: resume tailoring or interview prep.
- If the user asks you to do something outside job search (write a resume, prep for an interview), acknowledge it and suggest opening the right chat for it. Do not attempt it yourself.
- Reference what the user told you earlier in the conversation naturally.
- Respond concisely. This is a conversation, not a report.

Response format for job results:
Return results as markdown. Each job is a card:

### [Job Title] at [Company]
**Match:** [brief reason this matches the user's background]
**Location:** [location or Remote]
**Link:** [url]

Return 5-7 results maximum. Order by relevance to the user's background.
```

---

## Database Interactions

### Reading

- `jobs` table: `get_recent_job_searches` retrieves saved jobs for this user
- `user_profiles` table: profile context via Qdrant (not direct SQL)

### Writing

- `jobs` table: `save_job` inserts a new row with `user_id`, `title`, `company`, `source_url`, `jd_text`, `source="search"`, `status="bookmarked"`
- `chat_sessions` table: new row created on first message, title populated after first agent response

---

## Database Schema (job engine relevant tables)

```
jobs
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
  title             TEXT NOT NULL
  company           TEXT
  source_url        TEXT
  jd_text           TEXT
  source            TEXT NOT NULL DEFAULT 'search'   -- search | manual
  status            TEXT NOT NULL DEFAULT 'bookmarked'
                    -- bookmarked | applied | screening | interview
                    -- offer | rejected | withdrawn
  applied_date      DATE
  follow_up_date    DATE
  rejection_reason  TEXT
  notes             TEXT
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
```

Indexes:
- `jobs(user_id)` for all user job queries
- `jobs(user_id, status)` for filtered status views
- `jobs(user_id, created_at DESC)` for recency ordering

---

## Streaming Pattern

The `generate_response` node uses `stream_mode=["custom", "messages"]`:

- Status events via `get_stream_writer()`: "Searching jobs...", "Scoring results..."
- Token events via `messages` mode: the markdown response streams token by token

The streaming loop publishes each event to `Redis channel: stream:{user_id}`. The WebSocket handler relays them to the client in real time. The client renders markdown incrementally as tokens arrive.

After streaming completes, the graph saves results to the database and emits the `done` event with `chat_id` and `engine_type`.

---

## Seamless Conversation Checklist

- Profile context loaded before any response, so the first question is always personalised
- Constraints accumulated in `state["user_constraints"]` across every turn
- `state["last_action"]` and `state["waiting_for"]` give the agent precise awareness of where it is in the conversation
- Long-term memories loaded from `AsyncPostgresStore` at session start so the agent knows the user's history
- One question per turn enforced in the system prompt
- Cross-engine drift handled gracefully with context-carry offer
- Chat title auto-generated from the first message via the small LLM after the first agent response