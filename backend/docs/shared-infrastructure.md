# Shared Infrastructure

This document covers everything that sits beneath and across all four engines: the WebSocket layer, Redis pub/sub, the classification system, LangGraph checkpointing and memory, the profile ingestion pipeline, the vector store design, and the model routing strategy. Every engine depends on these foundations.

---

## Coding Practices and Patterns

These rules apply to every file in the codebase without exception. They are not preferences — they are constraints. Any new file must conform to all of them.

### Async throughout

Every function that touches a database, Redis, the filesystem, an HTTP client, or an LLM is async. No sync calls on the event loop. Background work that is too heavy for the request path goes to a task queue, not `asyncio.create_task`.

### Singleton infrastructure

All infrastructure clients — database engine, Redis pools, Qdrant client, LLM clients, embeddings, ConnectionManager, RedisPubSubManager, LangGraph checkpointer and store — are initialised once in the FastAPI lifespan context manager and stored on `app.state`. They are never instantiated per request.

### Dependency injection

Request handlers receive infrastructure via FastAPI `Depends()` providers. Providers pull from `request.app.state`. Repositories receive `db` and `redis` as constructor arguments. Nothing is imported as a global instance outside of `app.state`.

```python
def get_qdrant_client(request: Request) -> AsyncQdrantClient:
    return request.app.state.qdrant_client
```

### ORM everywhere

All database reads and writes use SQLAlchemy ORM style — `select()`, `db.add()`, `db.commit()`, `db.refresh()`. Raw SQL via `text()` is not used except in migrations. This applies to every layer including tools, indexers, and background tasks.

### Repository pattern

All database access goes through repository classes. Routes and agents never query the database directly. Repositories take `db: AsyncSession` and `redis: aioredis.Redis` as constructor arguments — never pulled from global state inside the repository.

### Custom exceptions

HTTP errors are raised as custom exception classes, never as raw `HTTPException`. Exception handlers are registered once in `main.py` via `register_exception_handlers(app)`.

### No hardcoded constants

Thresholds, model names, TTLs, limits, and any value that could change between environments live in `settings` via `config.py`. Environment variables use generic names — `LLM_LARGE_MODEL` not `ANTHROPIC_MODEL` — so the provider can be swapped at configuration time.

---

## File Naming and Directory Conventions

### Separation of concerns — three mandatory folders

Every concern is split across exactly three locations:

```
app/schemas/          — all Pydantic models for request/response/internal contracts
app/agents/prompts/   — all LLM system prompts and human message templates
app/routes/           — all FastAPI route definitions, minimal code only
```

No schema lives inside a feature folder. No prompt lives inside a route or service file. No heavy logic lives inside a routes file.

### Routes are minimal

Route files contain only the endpoint function and its dependency declarations. All logic is imported from the relevant module. The pattern is:

```python
# routes/websocket.py — correct
from app.websocket.handler import handle_websocket_connection

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: UUID) -> None:
    await handle_websocket_connection(websocket, user_id)
```

If a route function exceeds roughly 10 lines, the logic belongs elsewhere.

### Prompts are constants

Prompt files in `app/agents/prompts/` export named string constants and nothing else. No logic, no imports, no LLM calls. One file per concern, named by the concern it serves.

```
app/agents/prompts/
  classification.py     — CLASSIFICATION_SYSTEM_PROMPT, CLASSIFICATION_HUMAN_TEMPLATE
  normalisation.py      — NORMALISATION_SYSTEM_PROMPT, NORMALISATION_HUMAN_TEMPLATE
  compression.py        — COMPRESSION_SYSTEM_PROMPT, COMPRESSION_HUMAN_TEMPLATE
  job.py                — job engine system prompt
  prep.py               — prep engine system prompt
  document.py           — document engine system prompt
  tracker.py            — tracker engine system prompt
```

### Schemas are contracts

Schema files in `app/schemas/` export Pydantic models and type aliases only. One file per domain.

```
app/schemas/
  websocket.py          — InboundMessage, OutboundToken, OutboundStatus, OutboundThinking,
                          OutboundDone, OutboundError, OutboundMessage, EngineType
  classification.py     — ClassificationResult, ExtendedEngineType
  profile.py            — ProfileUploadResponse, ProfileStatusResponse
  jobs.py               — JobSchema, JobStatusUpdate
  documents.py          — DocumentSchema
  prep.py               — RoadmapSchema, TopicMasterySchema
  tracker.py            — TrackerSummarySchema
```

### File naming

All files use `snake_case`. No abbreviations except well-established ones (`llm`, `jti`, `db`). Names describe what the file does, not what framework it uses:

```
handler.py        not websocket_handler.py
classifier.py     not llm_classifier.py
embeddings.py     not jina_embeddings.py
indexer.py        not qdrant_indexer.py
```

### Engine structure

Each engine follows the same internal layout:

```
agents/
  job/
    graph.py        — LangGraph graph definition, node wiring
    nodes.py        — individual graph node functions
    tools.py        — engine-specific @tool definitions
    runner.py       — async run() entry point called by dispatch
    state.py        — TypedDict state definition for this engine
```

Engine-specific schemas go in `app/schemas/`. Engine-specific prompts go in `app/agents/prompts/`. Nothing engine-specific leaks into the shared infrastructure.

### Builder functions

Infrastructure modules expose a `build_*` factory function that is called once in lifespan and returns a typed instance stored on `app.state`. The module never holds a module-level instance itself.

```python
# correct
def build_llm_client() -> LLMClient: ...
app.state.llm_client = build_llm_client()

# never do this
llm_client = build_llm_client()   # module-level global
```

---

## WebSocket Layer

### Connection lifecycle

Every authenticated user opens one persistent WebSocket connection at:

```
ws://host/ws/{user_id}?token=<access_token>
```

The handler sequence on connection:

1. Extract token from query params
2. Validate JWT: signature, expiry, jti, session not revoked — all before `accept()`
3. If invalid: `websocket.close(code=1008)` without accepting, return
4. Confirm path `user_id` matches token `user_id`
5. `websocket.accept()`
6. Register connection in `ConnectionManager`
7. Set presence key in Redis
8. Start three concurrent async tasks: `_listen_client`, `_listen_pubsub`, `_heartbeat`
9. `asyncio.wait(FIRST_COMPLETED)` — when any task exits, cancel the others
10. Finally block: disconnect from manager, clear presence

### Three concurrent tasks

`_listen_client` — sits in a loop on `receive_json()`. On each message, validates it as `InboundMessage` and fires `dispatch()` as `asyncio.create_task`. Returns immediately to `receive_json()` without waiting for the engine to finish. Exits on `WebSocketDisconnect`.

`_listen_pubsub` — subscribes to Redis channel `stream:{user_id}`. Forwards every message published to that channel directly to the WebSocket client. This is the only path by which engine tokens reach the client — the engine publishes to Redis, this task delivers. Exits when the connection closes or Redis errors.

`_heartbeat` — sends a WebSocket ping frame every 30 seconds. If the send does not complete within 10 seconds, the connection is declared dead, closed with code `1001`, and the task exits triggering full cleanup. The browser handles pong responses automatically at the protocol level — no client-side code needed.

### Why `asyncio.create_task` in `_listen_client`

If `dispatch()` were awaited directly, the client listener would block for the entire engine run — potentially 10–30 seconds. During that time the client could not send another message. `create_task` hands dispatch off to the event loop and the listener returns to `receive_json()` immediately, staying fully responsive throughout.

### ConnectionManager

Holds in-process WebSocket references keyed by `user_id`. Handles delivery to connections on this worker only. Cross-worker delivery is Redis's responsibility.

### Redis pub/sub for multi-worker streaming

Token streaming works correctly regardless of which Uvicorn worker runs the LangGraph graph and which holds the WebSocket connection. The engine publishes to `stream:{user_id}` on Redis `db=1`. The `_listen_pubsub` task on the WebSocket worker picks up and delivers.

Publisher and subscriber use separate Redis connections — a connection in subscribe mode cannot issue regular commands.

### Heartbeat configuration

```
_HEARTBEAT_INTERVAL_SECONDS = 30
_HEARTBEAT_TIMEOUT_SECONDS  = 10
```

Worst case: a dead connection is detected and cleaned up within 40 seconds.

### WebSocket message protocol

All messages are JSON. No raw text.

**Client to server:**

```json
{
  "type": "message",
  "chat_id": "uuid | null",
  "engine_type": "job | prep | document | tracker | null",
  "content": "user message text"
}
```

`chat_id` is null on a new conversation. `engine_type` is null on a new conversation — classification determines it. Both are populated on all follow-up turns.

**Server to client:**

```json
{ "type": "token",    "content": "..." }
{ "type": "status",   "content": "Searching jobs..." }
{ "type": "thinking", "content": "Checking your profile..." }
{ "type": "done",     "chat_id": "uuid", "engine_type": "job", "title": "ML roles in Nairobi" }
{ "type": "error",    "content": "Something went wrong, please try again." }
```

The `done` event carries `chat_id` and the auto-generated title on the first turn. The client stores these for subsequent turns.

### File layout

```
app/
  websocket/
    handler.py      — _authenticate, _listen_client, _listen_pubsub,
                      _heartbeat, handle_websocket_connection
    manager.py      — ConnectionManager
    pubsub.py       — RedisPubSubManager
    dispatch.py     — _resolve_engine, _ensure_chat_session, _route_to_engine, dispatch

  routes/
    websocket.py    — @router.websocket("/ws/{user_id}"), calls handle_websocket_connection

  schemas/
    websocket.py    — InboundMessage, OutboundToken, OutboundStatus, OutboundThinking,
                      OutboundDone, OutboundError, OutboundMessage, EngineType
```

---

## Classification Layer

### New conversation only

The classifier runs once — on the first message of a new conversation where `chat_id` is null. This is the only time engine type is unknown.

For continuing conversations (`chat_id` is present), the declared `engine_type` is trusted and passed straight through to the engine. No validator, no second LLM call. The engine's own LLM has the full conversation checkpoint and handles drift naturally in its response — it tells the user to start a new chat if the message is clearly off-topic. This eliminates an unnecessary round trip on every continuing message.

```python
async def _resolve_engine(message, app) -> EngineType | None:
    if message.chat_id is not None:
        return message.engine_type   # continuing — trust and pass through

    result = await classify_message(message.content, small_llm)
    return None if result.engine_type == "unsupported" else result.engine_type
```

### Classifier

Uses Claude Haiku 4.5. Single call, JSON output parsed into `ClassificationResult`.

```python
class ClassificationResult(BaseModel):
    engine_type: Literal["job", "prep", "document", "tracker", "unsupported"]
    confidence: float
    reasoning: str
```

Categories:

- **job** — finding roles, searching, job recommendations
- **prep** — interview preparation, roadmaps, practice, quizzing
- **document** — resume, cover letter, writing, editing documents
- **tracker** — tracking applications, follow-ups, pipeline analysis
- **unsupported** — anything outside these four domains

`reasoning` is used for logging and debugging only, never shown to the user.

### Unsupported query handling

```
"That is outside what I am set up to help with. I can help you search for jobs,
prepare for interviews, write your resume or cover letter, or analyse your
application pipeline. Which of those would be useful right now?"
```

### File layout

```
app/
  classification/
    classifier.py   — classify_message(), imports prompt from agents/prompts/

  agents/
    prompts/
      classification.py   — CLASSIFICATION_SYSTEM_PROMPT, CLASSIFICATION_HUMAN_TEMPLATE

  schemas/
    classification.py     — ClassificationResult, ExtendedEngineType, EngineType
```

---

## LangGraph Checkpointing

### Short-term memory: AsyncPostgresSaver

Every engine's graph is compiled with `AsyncPostgresSaver` as the checkpointer. It is entered as an async context manager in the FastAPI lifespan so LangGraph manages its own connection pool independently of SQLAlchemy.

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
async with checkpointer as cp:
    await cp.setup()
    app.state.checkpointer = cp
    yield
```

The `thread_id` is always `{user_id}:{chat_id}`, scoping state to the user and conversation.

```python
config = {"configurable": {"thread_id": f"{user_id}:{chat_id}"}}
async for mode, chunk in graph.astream(state, config, stream_mode=["custom", "messages"]):
    ...
```

When a user resumes a chat, the same `thread_id` is used and LangGraph loads the latest checkpoint automatically. No manual history management.

### Long-term memory: AsyncPostgresStore

Facts that persist across separate chat sessions — target companies, preferred role types, stated skill gaps, communication preferences — are stored in the LangGraph Store.

```python
from langgraph.store.postgres.aio import AsyncPostgresStore

store = AsyncPostgresStore.from_conn_string(DATABASE_URL)
await store.setup()
app.state.store = store
```

Namespace: `("memories", user_id)`

The agent reads relevant memories at the start of every new conversation and writes to the store when the user reveals something worth persisting. This is what makes the agent feel like it knows the user across sessions.

### Chat session index table

LangGraph checkpoint tables are not designed for UI queries. The `chat_sessions` table is maintained separately for the sidebar. Both are keyed by the same `chat_id`.

The title is populated after the first agent response using a Haiku summarisation call on the first user message.

### Conversation compression

Before each graph invocation, if `state["messages"]` exceeds the engine's token threshold:

1. All messages except the last N turns are extracted
2. A Haiku summarisation call produces a concise briefing
3. The briefing replaces the old messages as a single `SystemMessage`
4. The tail turns remain verbatim
5. The updated message list is written back to the checkpoint

**Engine-specific thresholds — all environment-configurable:**

| Engine   | Token threshold | Verbatim tail | Notes |
|----------|-----------------|---------------|-------|
| prep     | 12,000          | 6 turns       | Fast accumulation. Briefing must carry a serialised `topic_mastery` snapshot to prevent re-quizzing covered material. |
| job      | 8,000           | 4 turns       | Episodic searches. Default settings appropriate. |
| document | 8,000           | 4 turns       | Short iterative conversations. Compression rarely triggers. |
| tracker  | 8,000           | 4 turns       | Read-heavy, short exchanges. Default settings appropriate. |

Compression briefing format:

```
[Session summary]
User is preparing for a Google ML Engineer role.
Profile shows strong Python and NLP background.
Roadmap generated covering 5 subjects.
Currently on subject 2: ML Systems Design.
User prefers concise technical explanations.
User has confirmed strong knowledge of gradient descent and backpropagation.
```

---

## Profile Ingestion Pipeline

### Upload and extraction

User uploads a PDF or DOCX file. The backend:

1. Reads the file bytes
2. Detects file type from filename and content-type header
3. Routes to the correct extractor:
   - PDF: `pypdf` — reads all pages, concatenates text
   - DOCX: `python-docx` — reads paragraphs and tables
4. Stores raw extracted text in `user_profiles.raw_text`

### Normalisation

The raw text is passed to the large LLM (Claude Sonnet 4.6) with the normalisation system prompt from `app/agents/prompts/normalisation.py`. Output is the canonical Prepwise profile markdown stored in `user_profiles.normalised_md`.

The system prompt is passed with `cache_control: ephemeral` for prompt caching.

### Chunking

The chunker (`vector/chunks.py`) parses the normalised markdown into typed `ProfileChunk` objects. Chunking strategy is structured block chunking — not sliding window — because the normalised profile is already pre-structured into discrete semantic units. Each block is independently meaningful; overlapping chunks would produce vectors spanning two unrelated concepts and degrade retrieval accuracy.

One chunk per block:
- Each `### Skill` block
- Each `### Project` block
- Each `### Role` block in Experience
- The `## Identity` block
- The `## Achievements` block
- The `## Certifications` block

Sliding window chunking (`RecursiveCharacterTextSplitter`) is used for job descriptions in the job engine, where the source is unstructured prose.

### Embedding and indexing

Chunks are embedded via the custom `JinaEmbeddings` wrapper (`vector/embeddings.py`) and upserted to the shared `profile_chunks` Qdrant collection with `user_id` as a payload field. Re-upload deletes all existing vectors for the user before re-indexing. `user_profiles.indexed_at` is updated via ORM after successful indexing.

### File layout

```
app/
  profile/
    extractor.py    — extract_text(), detect_file_type()
    normaliser.py   — normalise_profile(), imports prompt from agents/prompts/
    indexer.py      — index_profile(), _delete_user_vectors(), _embed_chunks(),
                      _upsert_points(), _mark_indexed() via ORM

  vector/
    chunks.py       — ProfileChunk dataclass, parse_profile_chunks()
    embeddings.py   — JinaEmbeddings, build_embeddings()
    qdrant_client.py — build_qdrant_client(), setup_collections(),
                       get_qdrant_client()

  agents/
    prompts/
      normalisation.py  — NORMALISATION_SYSTEM_PROMPT, NORMALISATION_HUMAN_TEMPLATE
```

---

## Vector Store Design

### Qdrant collections

Two shared collections serve all users. Isolation is enforced by filtering on `user_id` metadata on every query without exception, enforced unconditionally at the repository layer.

| Collection      | Purpose |
|-----------------|---------|
| `profile_chunks` | Profile data — skills, projects, experience, identity blocks |
| `prep_chunks`    | Generated subtopics and questions from prep sessions |

Per-user collections do not scale — Qdrant is optimised for a small number of large collections. One collection per user introduces memory fragmentation, slower cluster rebalancing, and collection management overhead that compounds as user count grows.

**Vector dimension:** 2048 (Jina Embeddings v4 single-vector mode, truncatable to 128 via MRL)
**Distance metric:** Cosine
**Payload index:** `user_id` field indexed as `KEYWORD` on both collections for fast filtered queries.

### Payload schema — profile_chunks

```json
{
  "user_id": "uuid",
  "type": "skill | project | experience | identity | achievement | certification",
  "name": "block name",
  "stack_tags": ["python", "fastapi"],
  "depth_level": 4,
  "period": "2023-2025",
  "text": "full chunk text"
}
```

### Payload schema — prep_chunks

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

### Custom JinaEmbeddings wrapper

The `langchain-community` `JinaEmbeddings` class does not pass the `task` parameter to the Jina API for v3+ models. Both `embed_documents` and `embed_query` make identical API calls, silently disabling the task-specific LoRA adapters and degrading retrieval accuracy.

The custom `JinaEmbeddings` class in `vector/embeddings.py` fixes this:

```
embed_documents()  →  task: retrieval.passage
embed_query()      →  task: retrieval.query
```

It inherits from LangChain's `Embeddings` base class. Switching providers requires changing only the class import and the `EMBEDDING_MODEL` env var — no call sites change.

```python
# current
from app.vector.embeddings import JinaEmbeddings
embeddings = JinaEmbeddings(model=settings.embedding_model)

# switching to Google — only these two lines change
from langchain_google_genai import GoogleGenerativeAIEmbeddings
embeddings = GoogleGenerativeAIEmbeddings(model=settings.embedding_model)
```

### Retrieval pattern

`get_profile_context(query)` in the shared tools layer:

1. Embeds the query with `task: retrieval.query`
2. Searches `profile_chunks` filtered by `user_id`, top-k of 5
3. Returns the top 5 chunks as formatted text

The agent never receives the full profile — only what is semantically relevant to the current query.

---

## Model Routing

### Provider agnosticism via LangChain

All LLM calls go through LangChain's provider interface. Switching provider requires changing the import and the model string in `llm/client.py` — no agent logic, graph nodes, or tool definitions change.

```python
from langchain_anthropic import ChatAnthropic
llm_large = ChatAnthropic(model=settings.llm_large_model)
llm_small = ChatAnthropic(model=settings.llm_small_model)
```

### Task routing

`llm/router.py` exposes `LLMTask` (a `StrEnum`) and `get_llm(client, task)` which returns the large or small model based on task type.

**Large model tasks** — require reasoning, writing quality, nuanced understanding:
profile normalisation, resume/cover letter generation, roadmap generation, JD analysis, conversational agent responses.

**Small model tasks** — classification, extraction, scoring, summarisation:
engine classification, job result scoring, conversation compression, chat title generation, ATS keyword extraction.

### Prompt caching

System prompts and profile context are passed with `cache_control: ephemeral` on providers that support it (Anthropic natively). A keepalive task in `llm/cache.py` pings registered prompts every 4 minutes to hold the cache TTL open. Engines register their system prompt via `register_system_prompt()` at startup.

### File layout

```
app/
  llm/
    client.py     — LLMClient dataclass, build_llm_client()
    router.py     — LLMTask StrEnum, get_llm(), get_llm_client()
    cache.py      — run_cache_keepalive(), register_system_prompt()
```

---

## Tool Architecture

All tools use the `@tool` decorator from `langchain_core.tools`. Bound to the LLM via `llm.bind_tools(tools)`. LangGraph's built-in `ToolNode` handles execution and feeds results back into `state["messages"]` as `ToolMessage` objects automatically.

### Shared tools

```
app/agents/shared/tools/
  profile_tool.py       — get_profile_context
  job_history_tool.py   — get_recent_job_searches
  memory_tool.py        — get_long_term_memories
```

### Engine-specific tools

Defined in each engine's `tools.py`. Detailed in each engine's document.

---

## Redis Database Allocation

```
db=0    auth sessions         access:{jti}, refresh:{token_hash}
db=1    websocket / pubsub    stream:{user_id}, presence:{user_id}
db=2    chat session cache    session:cache:{user_id}:{chat_id}
db=3    rate limiting         slowapi counters for login and API throttling
```

Each database has its own connection pool initialised at startup. Services receive only the pool relevant to their concern via `Depends()`.

---

## Singleton Initialisation

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_pools = build_redis_pools()
    app.state.redis_auth      = redis_pools["auth"]
    app.state.redis_pubsub    = RedisPubSubManager()
    await app.state.redis_pubsub.startup()
    app.state.redis_cache     = redis_pools["cache"]
    app.state.redis_ratelimit = redis_pools["ratelimit"]

    app.state.llm_client  = build_llm_client()
    app.state.embeddings  = build_embeddings()

    qdrant = build_qdrant_client()
    await setup_collections(qdrant)
    app.state.qdrant_client = qdrant

    async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
        await checkpointer.setup()
        app.state.checkpointer = checkpointer

        app.state.store = AsyncPostgresStore.from_conn_string(DATABASE_URL)
        await app.state.store.setup()

        app.state.connection_manager = ConnectionManager()

        asyncio.create_task(run_cache_keepalive(app.state.llm_client.large))

        await _check_dependencies(app)
        yield

    await app.state.redis_pubsub.shutdown()
    await close_redis_pools(redis_pools)
    await app.state.qdrant_client.close()
```

---

## Directory Structure

```
backend/
  app/
    agents/
      prompts/
        classification.py     CLASSIFICATION_SYSTEM_PROMPT, CLASSIFICATION_HUMAN_TEMPLATE
        normalisation.py      NORMALISATION_SYSTEM_PROMPT, NORMALISATION_HUMAN_TEMPLATE
        compression.py        COMPRESSION_SYSTEM_PROMPT
        job.py                JOB_SYSTEM_PROMPT
        prep.py               PREP_SYSTEM_PROMPT
        document.py           DOCUMENT_SYSTEM_PROMPT
        tracker.py            TRACKER_SYSTEM_PROMPT
      shared/
        tools/
          profile_tool.py
          job_history_tool.py
          memory_tool.py
        memory/
          store.py            AsyncPostgresStore read/write helpers
          compression.py      message compression logic
      job/
        graph.py
        nodes.py
        tools.py
        runner.py
        state.py
      prep/
        graph.py
        nodes.py
        tools.py
        runner.py
        state.py
      document/
        graph.py
        nodes.py
        tools.py
        runner.py
        state.py
      tracker/
        graph.py
        nodes.py
        tools.py
        runner.py
        state.py
    classification/
      classifier.py
    core/
      config.py
      security.py
      dependencies.py
    db/
      session.py
      redis.py
      models/
        base.py
        users.py
        sessions.py
        chat_sessions.py
        jobs.py
        documents.py
        prep.py
        profile.py
    llm/
      client.py
      router.py
      cache.py
    profile/
      extractor.py
      normaliser.py
      indexer.py
    routes/
      auth.py
      websocket.py
      profile.py
      tracker_panel.py
    schemas/
      websocket.py
      classification.py
      profile.py
      jobs.py
      documents.py
      prep.py
      tracker.py
    vector/
      qdrant_client.py
      embeddings.py
      chunks.py
    websocket/
      handler.py
      manager.py
      pubsub.py
      dispatch.py
    main.py
```

---

## Environment Variables

```
DATABASE_URL                        postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL                           redis://localhost:6379
REDIS_PASSWORD
REDIS_DB_AUTH                       0
REDIS_DB_PUBSUB                     1
REDIS_DB_CACHE                      2
REDIS_DB_RATELIMIT                  3
QDRANT_HOST                         localhost
QDRANT_PORT                         6333
ANTHROPIC_API_KEY
LLM_LARGE_MODEL                     claude-sonnet-4-6
LLM_SMALL_MODEL                     claude-haiku-4-5-20251001
JINA_API_KEY
EMBEDDING_MODEL                     jina-embeddings-v4
EMBEDDING_DIMENSIONS                2048
SERP_API_KEY
JWT_ACCESS_SECRET
JWT_REFRESH_SECRET
JWT_ACCESS_EXPIRY_MINUTES           15
JWT_REFRESH_EXPIRY_DAYS             30
BCRYPT_COST                         12
APP_ENV                             development | production
APP_HOST
APP_PORT

# Compression thresholds — tunable per engine without code changes
COMPRESSION_THRESHOLD_PREP          12000
COMPRESSION_THRESHOLD_JOB           8000
COMPRESSION_THRESHOLD_DOCUMENT      8000
COMPRESSION_THRESHOLD_TRACKER       8000
COMPRESSION_TAIL_TURNS_PREP         6
COMPRESSION_TAIL_TURNS_JOB          4
COMPRESSION_TAIL_TURNS_DOCUMENT     4
COMPRESSION_TAIL_TURNS_TRACKER      4
```