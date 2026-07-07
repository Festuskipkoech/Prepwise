# Prepwise — Architecture

This document covers the full technical architecture of Prepwise. For a non-technical
overview of what the product does and why it exists, see the
[README](../README.md).

---

## Guiding Principles

- One source of truth: the master profile drives every AI operation
- Generate once, store and retrieve: no content is regenerated unless explicitly requested
- Four-level lazy generation: subjects, topics, subtopics, questions — each level only
  generated when the user explicitly drills into it
- Tight context: RAG retrieval keeps token counts low per Claude call
- Model routing: task complexity determines which Claude model is invoked
- Plain text output from Claude: the frontend owns all visual presentation and formatting
- Clean layer separation: routes hold no logic, services hold business logic, repositories
  hold all database querying
- Singleton instances: LLM client, Qdrant client, and DB pool are initialized once at
  app startup and injected per request — never instantiated per request
- No N+1 queries: all related data fetched in single queries using joins or batch fetches

---

## System Stack

| Layer          | Technology                                              |
|----------------|---------------------------------------------------------|
| Frontend       | Next.js, TailwindCSS                                    |
| API            | FastAPI (async)                                         |
| Streaming      | SSE via sse-starlette                                   |
| Agent          | LangGraph                                               |
| LLM            | Anthropic Claude via LangChain (Sonnet 4.6 / Haiku 4.5) |
| Embeddings     | Jina Embeddings v4 API (free tier)                      |
| Vector DB      | Qdrant v1.15.5 (local Docker)                           |
| Relational DB  | PostgreSQL 18.4                                         |
| Job Search     | SerpAPI (Google Jobs engine)                            |
| Auth           | JWT via python-jose, bcrypt via passlib                 |
| Document Gen   | react-pdf / docx.js — frontend only                     |

---

## Directory Structure

```
prepwise/
  backend/
    .env
    .env.example
    Dockerfile
    docker-compose.yml
    requirements.txt
    alembic.ini
    scripts/
      create_user.py
    profile/
      master_profile.md
    app/
      main.py
      core/
        config.py
        security.py
        dependencies.py
        logging.py
      exceptions/
        base.py
        auth.py
        profile.py
        jobs.py
        documents.py
        prep.py
        handlers.py
      agents/
        graph/
          profile_graph.py
          job_search_graph.py
          document_graph.py
          roadmap_graph.py
          prep_graph.py
          job_tracker_graph.py
        prompts/
          system_prompts.py
          profile_prompts.py
          job_search_prompts.py
          job_search_context_prompts.py
          document_prompts.py
          prep_prompts.py
          job_tracker_prompts.py
        tools/
          profile_reader.py
          job_search.py
          document_utils.py
          prep_utils.py
        states/
          profile_state.py
          job_search_state.py
          document_state.py
          prep_state.py
          job_tracker_state.py
      routes/
        auth.py
        profile.py
        jobs.py
        documents.py
        prep.py
        tracker.py
      services/
        auth_service.py
        profile_service.py
        job_service.py
        document_service.py
        prep_service.py
        tracker_service.py
      repositories/
        user_repository.py
        job_repository.py
        document_repository.py
        prep_repository.py
        profile_repository.py
      db/
        session.py
        models/
          base.py
          users.py
          jobs.py
          documents.py
          prep.py
      vector/
        qdrant_client.py
        embeddings.py
        chunks.py
      llm/
        client.py
        router.py
        cache.py
      schemas/
        auth.py
        profile.py
        jobs.py
        documents.py
        prep.py
        tracker.py
  docs/
    architecture.md
  README.md
```

---

## Authentication

Single-user JWT authentication. One script creates the user account. All routes except
`POST /auth/login` require a valid Bearer token.

Token expiry: 30 days. No refresh token. User creation runs once:

```bash
python scripts/create_user.py --email you@email.com --password yourpassword
```

---

## Streaming and Communication Pattern

All generation operations stream from server to client via SSE. All client-to-server
communication uses standard HTTP POST. There are no WebSockets.

```
Client                             Server

POST /documents/generate  ------>  FastAPI receives job_id + document_type
                                   LangGraph graph starts
                          <------  text/event-stream opens
                          <------  data: {"type": "status", "message": "..."}\n\n
                          <------  data: {"type": "chunk", "content": "..."}\n\n
                          <------  data: {"type": "done", "document_id": "..."}\n\n
```

Three event types flow over every SSE stream:

- `status` — progress messages from `get_stream_writer()` inside graph nodes
- `chunk` — raw LLM token content surfaced via `stream_mode=["messages"]`
- `done` — signals completion, carries any final IDs or result data

The interview session maintains conversation context by including the full message
history in every POST payload. The server is stateless between turns.

---

## LangGraph Streaming Pattern

Graphs that need token streaming use `stream_mode=["custom", "messages"]`.
Graphs that only need status updates use `stream_mode=["custom", "updates"]`.

```python
async for mode, chunk in graph.astream(
    initial_state,
    stream_mode=["custom", "messages"],
):
    if mode == "custom":
        yield json.dumps(chunk)
    elif mode == "messages":
        message_chunk, metadata = chunk
        token = getattr(message_chunk, "content", "")
        if token and metadata.get("langgraph_node") == "generate":
            yield json.dumps({"type": "chunk", "content": token})
```

`get_stream_writer()` is called inside graph nodes to push status events between
LLM calls where the model is silent but work is in progress.

---

## The Master Profile

Stored at `backend/profile/master_profile.md`. Maintained manually. Never stored in
the database. Read from disk, passed to Claude via the system message with prompt
caching enabled.

Expected structure:

```markdown
# Name

## Identity
name, location, contact, target roles

## Skills
### Skill Name
Depth: 1
context of use and projects where applied

## Projects
### Project Name
Stack: tool1, tool2
Metrics: scale numbers, impact
description of what was built and key decisions made

## Experience
### Role Title
Company: name
Period: dates
Stack: tool1, tool2
what was shipped, measurable outcomes

## Achievements
awards, recognition, institutional partnerships

## Certifications
certifications with issuer and year
```

The chunker in `vector/chunks.py` parses this structure. Top-level sections use `##`
headings. Subsections use `###` headings. Fields like `Stack:`, `Metrics:`, `Depth:`,
`Company:`, `Period:` must appear on their own lines inside each block.

---

## Vector Store Design

Two Qdrant collections. Vector dimension: 1024 (Jina Embeddings v4).

**profile_chunks**

| Chunk unit      | Metadata                                          |
|-----------------|---------------------------------------------------|
| Each project    | type, project_name, stack_tags, scale_metrics     |
| Each skill      | type, skill_name, depth_level                     |
| Each experience | type, role_name, company, period, stack_tags      |

**prep_chunks**

| Chunk unit    | Metadata                                            |
|---------------|-----------------------------------------------------|
| Each subtopic | type, subject, topic, subtopic, skill_tags          |

Jina uses task-specific embeddings: `retrieval.passage` for content being stored,
`retrieval.query` for search queries. Using the correct task type materially improves
retrieval accuracy.

---

## LLM Cost Strategy

**Prompt caching** — the master profile is passed in the system message with
`cache_control: ephemeral`. Cache reads cost 10% of normal input token price.
A keepalive task pings every 4 minutes to maintain the 5-minute TTL.

**Model routing**

```
Claude Haiku 4.5   job scoring, tracker pattern analysis, classification
Claude Sonnet 4.6  resume generation, cover letters, roadmap generation,
                   subtopic and question generation, JD analysis, prep paths
```

**Generate once** — every piece of generated content carries a `generated_at`
timestamp. The service checks this before any Claude call. Content that already
exists is served from PostgreSQL.

**RAG over full profile dump** — document generation retrieves 5 semantically
relevant profile chunks per JD rather than sending the entire profile.

**Batch API** — roadmap skeleton generation runs as an Anthropic Batch API job
at 50% of standard pricing.

---

## Database Schema

### users
```sql
id              UUID PRIMARY KEY
email           TEXT UNIQUE NOT NULL
password_hash   TEXT NOT NULL
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### jobs
```sql
id              UUID PRIMARY KEY
title           TEXT NOT NULL
company         TEXT
source_url      TEXT
jd_text         TEXT
source          TEXT        -- "search" | "manual"
status          TEXT        -- "bookmarked" | "applied" | "screening"
                            -- "interview" | "offer" | "rejected" | "withdrawn"
applied_date    DATE
follow_up_date  DATE
rejection_reason TEXT
notes           TEXT
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### documents
```sql
id              UUID PRIMARY KEY
job_id          UUID REFERENCES jobs(id) ON DELETE CASCADE
type            TEXT        -- "resume" | "cover_letter"
content         JSONB
version         INTEGER
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### roadmap_subjects
```sql
id              UUID PRIMARY KEY
name            TEXT NOT NULL
description     TEXT
order_index     INTEGER
source          TEXT        -- "roadmap" | "job_prep"
job_id          UUID REFERENCES jobs(id) ON DELETE CASCADE
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### roadmap_topics
```sql
id              UUID PRIMARY KEY
subject_id      UUID REFERENCES roadmap_subjects(id) ON DELETE CASCADE
name            TEXT NOT NULL
description     TEXT
order_index     INTEGER
status          TEXT        -- "not_started" | "in_progress" | "done"
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### roadmap_subtopics
```sql
id              UUID PRIMARY KEY
topic_id        UUID REFERENCES roadmap_topics(id) ON DELETE CASCADE
name            TEXT NOT NULL
concept         TEXT
project_evidence TEXT
order_index     INTEGER
status          TEXT
generated_at    TIMESTAMP
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### roadmap_questions
```sql
id              UUID PRIMARY KEY
subtopic_id     UUID REFERENCES roadmap_subtopics(id) ON DELETE CASCADE
type            TEXT        -- "theoretical" | "practical"
question        TEXT NOT NULL
answer          TEXT NOT NULL
order_index     INTEGER
generated_at    TIMESTAMP
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### job_prep_paths
```sql
id                    UUID PRIMARY KEY
job_id                UUID REFERENCES jobs(id) ON DELETE CASCADE UNIQUE
generated_subject_id  UUID REFERENCES roadmap_subjects(id) ON DELETE SET NULL
strong_matches        JSONB
needs_sharpening      JSONB
gaps                  JSONB
roadmap_links         JSONB
talking_points        JSONB
likely_angles         JSONB
generated_at          TIMESTAMP
created_at            TIMESTAMP
updated_at            TIMESTAMP
```

---

## The Five Engines

Each engine is an independent vertical slice owning its exceptions, schemas,
repository, service, agent state, prompts, tools, graph, and route.

### Profile Engine

Reads `master_profile.md`, chunks it, embeds via Jina, stores in Qdrant.
Auto-indexes on startup if the collection is empty. Re-indexes on demand when
the profile is updated. Generates a profile quality analysis via Claude on
every index run and on a dedicated analysis endpoint.

Endpoints: `GET /profile/status`, `POST /profile/index`, `GET /profile/analysis`

### Job Search Engine

Returns AI-generated search suggestions from the profile before any search fires.
Calls SerpAPI, scores each result against the profile via Haiku, returns ranked
results. Supports saving from search results or manual job entry.

Endpoints: `GET /jobs/search-context`, `POST /jobs/search`, `POST /jobs/from-search`,
`POST /jobs/`, `GET /jobs/`, `GET /jobs/{id}`, `PATCH /jobs/{id}/status`,
`DELETE /jobs/{id}`

### Document Engine

Three-node LangGraph pipeline: retrieve relevant profile chunks from Qdrant, analyse
the JD, generate document. Streams token by token via SSE using
`stream_mode=["custom", "messages"]`. Output is plain structured text parsed into
JSONB. Frontend renders into visual PDF or Word template. Claude never formats.

Endpoints: `POST /documents/generate`, `GET /documents/job/{id}`,
`GET /documents/job/{id}/latest`, `GET /documents/{id}`

### Prep Engine

Four-level lazy generation. Level 1 generates the roadmap skeleton via Batch API.
Level 2 generates subtopics per topic on first access. Level 3 generates questions
per subtopic on first access. Level 4 is a live conversational interview session,
stateless on the server, with full conversation history sent in every POST.

Job-specific prep paths generate a dedicated subject scoped to the role's domain,
tagged `source="job_prep"`, following the same lazy generation pattern.

Endpoints: `GET /prep/roadmap`, `POST /prep/roadmap/generate`,
`GET /prep/subjects/{id}`, `GET /prep/topics/{id}`, `PATCH /prep/topics/{id}/status`,
`GET /prep/subtopics/{id}`, `PATCH /prep/subtopics/{id}/status`,
`POST /prep/interview/session`, `POST /prep/jobs/{id}/prep-path`,
`GET /prep/jobs/{id}/prep-path`

### Tracker Engine

Dashboard aggregation computed directly from PostgreSQL with no LLM involvement.
Follow-up alerts split into due today, overdue, and upcoming. Cursor-paginated
application history. Pattern analysis via a LangGraph graph backed by Haiku,
streamed via SSE, diagnosing funnel drop-off and returning data-grounded
recommendations.

Endpoints: `GET /tracker/dashboard`, `GET /tracker/follow-ups`,
`GET /tracker/history`, `GET /tracker/patterns`

---

## Pagination

Application history uses cursor pagination on `(created_at DESC, id DESC)`.
The client passes the `id` of the last received record as `cursor_id`. The server
returns records strictly before that position. Stable under concurrent writes,
performant at any scale, no duplicates or skipped records.

```
GET /tracker/history?page_size=20
GET /tracker/history?page_size=20&cursor_id=<id_from_previous_response>
```

---

## Singleton Management

LLM client, Qdrant client, and DB pool initialised once in the FastAPI lifespan
context manager. Stored on `app.state`. Injected via `Depends()`. Never
instantiated per request.

---

## Engineering Practices

- Routes contain no business logic
- Services own all orchestration
- Repositories own all database queries
- All singletons initialised in lifespan, injected via `Depends()`
- All related data fetched with `selectinload` or `joinedload`, never in loops
- All DB operations async via SQLAlchemy async session
- All exceptions typed, inherit from `AppException`, handled centrally
- All streaming via SSE, all writes via POST
- LLM client on LangChain for provider portability
- Claude returns plain structured text only

---

## Deployment

```
Azure VPS
  PostgreSQL 18.4    Docker, volume-mounted
  Qdrant v1.15.5     Docker, volume-mounted
  FastAPI            Docker, behind NGINX

Vercel
  Next.js frontend
```

---

## Environment Variables

```
APP_ENV                 development | production
APP_HOST
APP_PORT
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
DATABASE_URL            postgresql+asyncpg://user:pass@host:5432/db
QDRANT_HOST
QDRANT_PORT
ANTHROPIC_API_KEY
OPENAI_API_KEY
LLM_SONNET_MODEL        claude-sonnet-4-6
LLM_HAIKU_MODEL         claude-haiku-4-5-20251001
JINA_API_KEY
SERP_API_KEY
JWT_SECRET_KEY
JWT_ALGORITHM           HS256
JWT_EXPIRY_DAYS         30
PROFILE_PATH            profile/master_profile.md
```