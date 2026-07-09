# Database Design

## Overview

Prepwise uses PostgreSQL 18.4 as its primary relational store. All tables are designed for multi-user commercial operation from the ground up — every table carrying user data has a `user_id` foreign key and every query filters by it. LangGraph's checkpointer and store add their own tables to the same database, managed by LangGraph itself. Redis handles ephemeral session data and pub/sub. Qdrant handles vector storage.

---

## Design Principles

- Every user-owned table has `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- All primary keys are UUIDs generated with `gen_random_uuid()`
- All timestamps use `TIMESTAMPTZ` (timezone-aware) and default to `now()`
- Soft deletes are not used — hard deletes with `ON DELETE CASCADE` propagation
- No N+1 queries — all related data fetched with joins or batch fetches
- All DB operations async via SQLAlchemy async session
- Cursor pagination on all list endpoints that could grow unbounded

---

## Schema

### users

```sql
CREATE TABLE users (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email             TEXT UNIQUE NOT NULL,
    password_hash     TEXT NOT NULL,
    full_name         TEXT,
    is_active         BOOLEAN NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);
```

### sessions

```sql
CREATE TABLE sessions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token     TEXT UNIQUE NOT NULL,
    access_token_jti  TEXT UNIQUE NOT NULL,
    device_info       TEXT,
    ip_address        INET,
    expires_at        TIMESTAMPTZ NOT NULL,
    last_used_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at        TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_refresh_token ON sessions(refresh_token);
CREATE INDEX idx_sessions_access_token_jti ON sessions(access_token_jti);
CREATE INDEX idx_sessions_active ON sessions(user_id) WHERE revoked_at IS NULL;
```

### user_profiles

```sql
CREATE TABLE user_profiles (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    raw_text          TEXT,
    normalised_md     TEXT,
    file_name         TEXT,
    file_type         TEXT,
    indexed_at        TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_profiles_user_id UNIQUE (user_id)
);
```

One profile per user enforced by the unique constraint on `user_id`.

### chat_sessions

```sql
CREATE TABLE chat_sessions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    engine_type       TEXT NOT NULL
                      CHECK (engine_type IN ('job', 'prep', 'document', 'tracker')),
    title             TEXT,
    is_archived       BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_user_engine ON chat_sessions(user_id, engine_type);
CREATE INDEX idx_chat_sessions_updated ON chat_sessions(user_id, updated_at DESC);
CREATE INDEX idx_chat_sessions_active ON chat_sessions(user_id)
    WHERE is_archived = false;
```

This table is the sidebar index. LangGraph checkpoint tables store the actual conversation state. Both are keyed by the same `chat_id` as `thread_id`.

`thread_id` used in LangGraph config: `{user_id}:{chat_id}`

### jobs

```sql
CREATE TABLE jobs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title             TEXT NOT NULL,
    company           TEXT,
    source_url        TEXT,
    jd_text           TEXT,
    source            TEXT NOT NULL DEFAULT 'manual'
                      CHECK (source IN ('search', 'manual')),
    status            TEXT NOT NULL DEFAULT 'bookmarked'
                      CHECK (status IN (
                          'bookmarked', 'applied', 'screening',
                          'interview', 'offer', 'rejected', 'withdrawn'
                      )),
    applied_date      DATE,
    follow_up_date    DATE,
    rejection_reason  TEXT,
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_user_status ON jobs(user_id, status);
CREATE INDEX idx_jobs_user_applied_date ON jobs(user_id, applied_date);
CREATE INDEX idx_jobs_user_follow_up ON jobs(user_id, follow_up_date)
    WHERE follow_up_date IS NOT NULL;
CREATE INDEX idx_jobs_cursor ON jobs(user_id, created_at DESC, id DESC);
```

### documents

```sql
CREATE TABLE documents (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id            UUID REFERENCES jobs(id) ON DELETE SET NULL,
    chat_session_id   UUID REFERENCES chat_sessions(id) ON DELETE SET NULL,
    type              TEXT NOT NULL
                      CHECK (type IN ('resume', 'cover_letter')),
    content_md        TEXT NOT NULL,
    version           INTEGER NOT NULL DEFAULT 1,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_job_id ON documents(job_id);
CREATE INDEX idx_documents_chat_session ON documents(chat_session_id, type, version DESC);
CREATE INDEX idx_documents_latest ON documents(job_id, type, version DESC);
```

Each edit creates a new row. Version numbers are scoped to `(chat_session_id, type)`. The latest version for any session and type is the row with the highest version number.

### prep_roadmaps

```sql
CREATE TABLE prep_roadmaps (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_session_id       UUID REFERENCES chat_sessions(id) ON DELETE SET NULL,
    job_id                UUID REFERENCES jobs(id) ON DELETE SET NULL,
    target_role           TEXT NOT NULL,
    target_company        TEXT,
    raw_roadmap           JSONB NOT NULL DEFAULT '{}',
    current_subject_index INTEGER NOT NULL DEFAULT 0,
    current_topic_index   INTEGER NOT NULL DEFAULT 0,
    topic_mastery         JSONB NOT NULL DEFAULT '{}',
    status                TEXT NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'completed')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_prep_roadmaps_user_id ON prep_roadmaps(user_id);
CREATE INDEX idx_prep_roadmaps_user_status ON prep_roadmaps(user_id, status);
CREATE INDEX idx_prep_roadmaps_chat_session ON prep_roadmaps(chat_session_id);
CREATE INDEX idx_prep_roadmaps_job ON prep_roadmaps(job_id);
```

Multiple active roadmaps per user are fully supported. Each is independent with its own `chat_session_id` and its own LangGraph `thread_id`.

`raw_roadmap` JSONB structure:
```json
{
  "subjects": [
    {
      "name": "ML Fundamentals",
      "topics": [
        {
          "name": "Bias-Variance Tradeoff",
          "depth": "standard",
          "subtopics": ["definition", "in practice", "common interview angles"]
        }
      ]
    }
  ]
}
```

`topic_mastery` JSONB structure:
```json
{
  "Bias-Variance Tradeoff": "strong",
  "Gradient Descent": "surface",
  "Regularisation": "not_covered"
}
```

---

## LangGraph Infrastructure Tables

These tables are created automatically by calling `checkpointer.setup()` and `store.setup()` during application startup. They live in the same PostgreSQL database. Do not define or migrate them manually.

```
checkpoints               stores graph state snapshots per thread_id
checkpoint_writes         stores intermediate write operations
checkpoint_migrations     tracks LangGraph schema migrations
store                     stores long-term memory entries per namespace
```

The `thread_id` used across all LangGraph tables follows the pattern `{user_id}:{chat_id}`. This ensures complete user isolation within the shared LangGraph infrastructure tables.

---

## Redis

Redis serves two roles: a token cache layer on top of PostgreSQL, and a pub/sub message bus for WebSocket streaming. PostgreSQL is always the source of truth. Redis is a fast read-through cache that degrades gracefully — if Redis is unavailable, all operations fall back to PostgreSQL and users stay logged in.

### Database allocation

Redis supports 16 logical databases on a single instance. Each concern is assigned its own database for complete key isolation. No cross-contamination, and each database can be flushed independently in an emergency.

```
db=0    auth sessions         access:{jti}, refresh:{token_hash}
db=1    websocket / pubsub    stream:{user_id}, presence:{user_id}
db=2    chat session cache    session:cache:{user_id}:{chat_id}, classification results
db=3    rate limiting         slowapi counters for login and API throttling
```

### Key patterns and TTLs per database

```
db=0
  access:{jti}                        TTL 15 minutes     value: user_id
  refresh:{token_hash}                TTL 30 days        value: session_id

db=1
  stream:{user_id}                    no TTL             pub/sub channel, live connection only
  presence:{user_id}                  TTL 90 seconds     renewed by heartbeat

db=2
  session:cache:{user_id}:{chat_id}   TTL 30 minutes     active chat type and classification result

db=3
  ratelimit:{ip}                      TTL 15 minutes     login attempt counter per IP
```

### Token cache behaviour

On login: both token keys written to Redis db=0 after PostgreSQL session row is created. Redis write failure does not fail the login.

On validation: Redis db=0 checked first. On miss, PostgreSQL is the fallback and Redis is re-populated.

On logout: both Redis db=0 keys deleted immediately for instant revocation. PostgreSQL `revoked_at` set for durability.

On Redis outage: all token validation falls back to PostgreSQL. Performance degrades, sessions do not drop.

Nothing in Redis is the sole source of truth. Every key can be reconstructed from PostgreSQL if lost.

---

## Qdrant (vector storage)

Two logical collection namespaces. Isolation is enforced by filtering on `user_id` metadata on every query.

### profile_chunks

One collection named `profile_chunks`. All users' profile vectors stored here, separated by `user_id` metadata field.

Vector dimension: 1024 (Jina Embeddings v4)
Distance metric: Cosine

Payload schema per vector:
```json
{
  "user_id": "uuid",
  "type": "skill | project | experience | identity",
  "name": "block name",
  "stack_tags": ["python", "fastapi"],
  "depth_level": 4,
  "period": "2023-2025",
  "text": "full chunk text"
}
```

### prep_chunks

One collection named `prep_chunks`. Covered subtopics from prep sessions.

Payload schema per vector:
```json
{
  "user_id": "uuid",
  "roadmap_id": "uuid",
  "subject": "ML Fundamentals",
  "topic": "Bias-Variance Tradeoff",
  "subtopic": "in practice",
  "skill_tags": ["machine learning", "statistics"],
  "mastery_level": "strong",
  "session_date": "2025-07-09"
}
```

---

## Alembic Migrations

All schema changes go through Alembic. The `alembic/` directory holds migration scripts. The LangGraph tables are excluded from Alembic management — they are managed by LangGraph's own setup methods.

Migration naming convention: `{revision_id}_{short_description}.py`

Production migration procedure:
1. Generate migration: `alembic revision --autogenerate -m "description"`
2. Review generated migration carefully before applying
3. Apply: `alembic upgrade head`
4. LangGraph setup runs separately at application startup via `checkpointer.setup()` and `store.setup()`

---

## Entity Relationship Summary

```
users
  |-- sessions (one user, many sessions)
  |-- user_profiles (one user, one profile)
  |-- chat_sessions (one user, many chats)
  |-- jobs (one user, many jobs)
  |-- documents (one user, many documents)
  |-- prep_roadmaps (one user, many roadmaps)

chat_sessions
  |-- documents (one session, many document versions)
  |-- prep_roadmaps (one session, one roadmap)

jobs
  |-- documents (one job, many document versions across sessions)
  |-- prep_roadmaps (one job, many roadmaps)
```

---

## Query Patterns by Engine

### Auth engine
- `SELECT` user by email for login
- `INSERT` session on login
- `UPDATE` session on refresh (new tokens, last_used_at)
- `UPDATE` session.revoked_at on logout
- `SELECT` session by jti for access token validation

### Job engine
- `INSERT` job on save from search
- `SELECT` jobs by user_id ordered by created_at DESC for recent searches
- `SELECT` job by id for JD retrieval

### Prep engine
- `INSERT` prep_roadmap on roadmap generation
- `SELECT` prep_roadmaps by user_id and status for listing active roadmaps
- `UPDATE` prep_roadmap current_subject_index, current_topic_index, topic_mastery on progress
- `UPDATE` prep_roadmap status to completed

### Document engine
- `INSERT` document on every new version (never UPDATE content)
- `SELECT` documents by chat_session_id and type ordered by version DESC for history
- `SELECT` document by id and version for revert operations

### Tracker engine (panel)
- `INSERT` job on manual application entry
- `UPDATE` job.status, notes, follow_up_date, rejection_reason
- `SELECT` jobs by user_id with status filter for dashboard
- `SELECT` jobs by user_id where follow_up_date is due for follow-up alerts
- Cursor paginated `SELECT` for application history

### Tracker engine (chat analysis)
- Aggregated `SELECT` queries for conversion rates, counts per status, application rate trends
- All read-only. No writes from the chat interface.

### Chat sessions (all engines)
- `INSERT` chat_sessions on new conversation
- `UPDATE` chat_sessions.title after first agent response
- `UPDATE` chat_sessions.updated_at on every turn
- `SELECT` chat_sessions by user_id ordered by updated_at DESC for sidebar
- `SELECT` chat_sessions by user_id and engine_type for filtered views