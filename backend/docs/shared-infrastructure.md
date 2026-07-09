# Shared Infrastructure

This document covers everything that sits beneath and across all four engines: the WebSocket layer, Redis pub/sub, the classification system, LangGraph checkpointing and memory, the profile ingestion pipeline, the vector store design, and the model routing strategy. Every engine depends on these foundations.

---

## WebSocket Layer

### Connection lifecycle

Every authenticated user opens one persistent WebSocket connection at:

```
ws://host/ws/{user_id}?token=<access_token>
```

The handler sequence on connection:

1. Extract `token` from query params
2. Validate JWT: signature, expiry, `jti`, session not revoked
3. If invalid: `websocket.close(code=1008)` without accepting
4. If valid: `websocket.accept()`
5. Register connection in the local `ConnectionManager`
6. Subscribe to the user's Redis pub/sub channel: `stream:{user_id}`
7. Start two concurrent async tasks: one listening for client messages, one listening for Redis messages
8. On disconnect: unsubscribe from Redis, remove from `ConnectionManager`

### ConnectionManager

Holds in-process WebSocket references keyed by `user_id`. Handles sending messages to a specific connection on this worker. Does not know about connections on other workers — that is Redis's job.

```python
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        self.active[user_id] = ws

    def disconnect(self, user_id: str):
        self.active.pop(user_id, None)

    async def send(self, user_id: str, message: dict):
        ws = self.active.get(user_id)
        if ws:
            await ws.send_json(message)
```

Singleton instance initialised in the FastAPI lifespan context manager. Injected via `Depends()`.

### Redis pub/sub for multi-worker streaming

When a LangGraph graph streams a token, the streaming loop publishes the token to a Redis channel. The WebSocket handler subscribed to that channel relays it to the connected client. This means token streaming works correctly regardless of which Uvicorn worker is running the graph and which worker holds the WebSocket connection.

Channel naming: `stream:{user_id}`

Every streamed event goes through this channel. The WebSocket handler's Redis subscriber task receives it and calls `ConnectionManager.send()`.

This uses **Redis db=1** (WebSocket and pub/sub), completely isolated from auth token storage on db=0.

```python
class RedisPubSubManager:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._publisher: aioredis.Redis = None
        self._subscriber: aioredis.Redis = None

    async def startup(self):
        self._publisher = await aioredis.from_url(self.redis_url, db=1)
        self._subscriber = await aioredis.from_url(self.redis_url, db=1)

    async def publish(self, user_id: str, message: dict):
        await self._publisher.publish(
            f"stream:{user_id}",
            json.dumps(message)
        )

    async def subscribe(self, user_id: str):
        pubsub = self._subscriber.pubsub()
        await pubsub.subscribe(f"stream:{user_id}")
        return pubsub
```

### WebSocket message protocol

All messages are JSON. No raw text.

Client to server:
```json
{
  "type": "message",
  "chat_id": "uuid | null",
  "engine_type": "job | prep | document | tracker | null",
  "content": "user message text"
}
```

`chat_id` is null when starting a new conversation. `engine_type` is null when starting a new conversation (classification will determine it). Both are populated on follow-up turns.

Server to client:
```json
{ "type": "token", "content": "..." }
{ "type": "status", "content": "Searching jobs..." }
{ "type": "thinking", "content": "Checking your profile..." }
{ "type": "done", "chat_id": "uuid", "engine_type": "job", "title": "ML roles in Nairobi" }
{ "type": "error", "content": "Something went wrong, please try again." }
```

The `done` event carries the `chat_id` (newly created or existing) and the auto-generated title on the first turn of a new chat. The client stores these for subsequent turns.

---

## Classification Layer

Every new chat message where `engine_type` is null passes through classification before routing.

### Classifier

Uses Claude Haiku 4.5 for speed and cost. Single call, structured output via `llm.with_structured_output()` using a Pydantic schema.

```python
class ClassificationResult(BaseModel):
    engine_type: Literal["job", "prep", "document", "tracker", "unsupported"]
    confidence: float
    reasoning: str
```

The prompt instructs Haiku to classify the user's message into one of five categories based on intent:

- `job`: finding roles, searching, job recommendations
- `prep`: interview preparation, roadmaps, practice, quizzing
- `document`: resume, cover letter, writing, editing documents
- `tracker`: tracking applications, follow-ups, pipeline analysis, funnel discussion
- `unsupported`: anything outside these four domains

The `reasoning` field is used for logging and debugging, not shown to the user.

### Validation on continuing conversations

When `engine_type` is provided by the client (continuing conversation), the classifier runs a lightweight validation check. If the message content is strongly inconsistent with the declared engine type, the validator overrides it and treats it as a cross-engine request. This guards against client-side manipulation and handles natural conversation drift.

Cross-engine requests are handled gracefully: the agent in the current engine acknowledges the new intent and offers to open a new chat with relevant context carried over.

### Unsupported query handling

Unsupported queries never return a cold rejection. The response is warm and redirecting:

"That is outside what I am set up to help with. I can help you search for jobs, prepare for interviews, write your resume or cover letter, or analyse your application pipeline. Which of those would be useful right now?"

---

## LangGraph Checkpointing

### Short-term memory: AsyncPostgresSaver

Every engine's graph is compiled with `AsyncPostgresSaver` as the checkpointer. This persists the full graph state to PostgreSQL after every node execution.

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
    await checkpointer.setup()
    graph = engine_graph.compile(checkpointer=checkpointer)
```

The `thread_id` used in the config is always `{user_id}:{chat_id}`. This scopes state to the user and the specific conversation, ensuring complete isolation.

```python
config = {"configurable": {"thread_id": f"{user_id}:{chat_id}"}}
async for mode, chunk in graph.astream(state, config, stream_mode=["custom", "messages"]):
    ...
```

When a user resumes a chat, the graph is invoked with the same `thread_id`. LangGraph automatically loads the latest checkpoint and resumes from where the conversation left off. No manual history management is needed.

### Long-term memory: AsyncPostgresStore

Facts that should persist across separate chat sessions — target companies, preferred role types, stated skill gaps, communication style preferences — are stored in the LangGraph Store.

```python
from langgraph.store.postgres.aio import AsyncPostgresStore

store = AsyncPostgresStore.from_conn_string(DATABASE_URL)
await store.setup()
```

Namespace: `("memories", user_id)`

Each memory is a JSON document. The agent reads relevant memories at the start of every new conversation using semantic search over the store. The agent writes to the store when the user reveals something worth persisting — target company, timeline, stated weakness, preference.

This is what makes the agent feel like it knows the user across sessions without the user having to repeat themselves.

### Chat session index table

LangGraph's internal checkpoint tables are not designed for UI queries. The `chat_sessions` table is maintained separately for the sidebar and chat history UI:

```
chat_sessions
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
  engine_type       TEXT NOT NULL
  title             TEXT
  is_archived       BOOLEAN NOT NULL DEFAULT false
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
```

This table is written to when a new chat is created. The `title` is populated after the first message using a Haiku summarisation call on the first user message. Both `chat_sessions` and the LangGraph checkpointer are keyed by the same `chat_id`, tying them together.

### Conversation compression

Long conversations are compressed to prevent the context window from being exhausted and to control token costs.

Before each graph invocation, a pre-processing step counts the total token length of `state["messages"]`. If it exceeds 8,000 tokens:

1. All messages except the last 4 turns are extracted
2. A Haiku summarisation call converts them into a concise briefing
3. The briefing replaces the old messages as a single `SystemMessage`
4. The last 4 turns remain verbatim
5. The updated message list is written back to the checkpoint

The briefing format:

```
[Session summary]
User is preparing for a Google ML Engineer role.
Profile shows strong Python and NLP background.
Roadmap generated covering 5 subjects.
Currently on subject 2: ML Systems Design.
User prefers concise technical explanations.
User has confirmed strong knowledge of gradient descent and backpropagation.
```

This gives the model full context in a fraction of the tokens. The last 4 verbatim turns ensure the model has precise recent context for the current exchange.

---

## Profile Ingestion Pipeline

### Upload and extraction

User uploads a PDF or DOCX file. The backend:

1. Reads the file bytes
2. Routes to the correct extractor based on file type:
   - PDF: `pypdf2` — reads all pages, concatenates text
   - DOCX: `python-docx` — reads paragraphs and tables
3. Raw extracted text is stored in `user_profiles.raw_text`

### Normalisation

The raw text is passed to the large LLM with a structured normalisation prompt (preferred: Claude Sonnet 4.6). The prompt instructs the model to convert whatever format it receives into the canonical Prepwise profile markdown schema:

```markdown
# Name

## Identity
name, location, contact, target roles

## Skills
### Skill Name
Depth: 1-5
context and projects

## Projects
### Project Name
Stack: tool1, tool2
Metrics: scale numbers, impact
description

## Experience
### Role Title
Company: name
Period: dates
Stack: tool1, tool2
contributions and outcomes

## Achievements
awards, recognition

## Certifications
name, issuer, year
```

The normalised markdown is stored in `user_profiles.normalised_md`.

### Chunking and embedding

The chunker (`vector/chunks.py`) parses the normalised markdown:

- Each `### Skill` block becomes one chunk
- Each `### Project` block becomes one chunk
- Each `### Role` block becomes one chunk
- The `## Identity` block becomes one chunk

Each chunk carries metadata:

```python
{
    "user_id": "uuid",
    "type": "skill | project | experience | identity",
    "name": "block name",
    "stack_tags": ["python", "fastapi"],      # extracted from Stack: line
    "depth_level": 4,                          # extracted from Depth: line
    "period": "2023-2025"                      # extracted from Period: line
}
```

Chunks are embedded via Jina Embeddings v4 API using `task_type=retrieval.passage`. Stored in Qdrant collection `profile_chunks_{user_id}` — one collection per user, ensuring complete data isolation.

### Re-indexing

Re-upload triggers:
1. Delete all vectors for this user from Qdrant
2. Run extraction and normalisation again
3. Re-chunk and re-embed
4. Update `user_profiles.indexed_at`

---

## Vector Store Design

### Qdrant collections

Two logical collections per user:

`profile_chunks_{user_id}` — profile data
`prep_chunks_{user_id}` — generated subtopics and questions from prep sessions

Vector dimension: 1024 (Jina Embeddings v4)

Jina task types:
- `retrieval.passage` — when embedding content being stored
- `retrieval.query` — when embedding a search query

Using the correct task type materially improves retrieval accuracy. This must be enforced in the embeddings module.

### Retrieval pattern

Every engine that needs profile context calls `get_profile_context(query)`. This function:

1. Embeds the query with `task_type=retrieval.query`
2. Searches `profile_chunks_{user_id}` with a top-k of 5
3. Filters by `user_id` metadata to enforce isolation
4. Returns the top 5 chunks as formatted text

The agent never receives the full profile. It receives only what is semantically relevant to the current query. This keeps token usage low and keeps the model focused.

---

## Model Routing

### Provider agnosticism via LangChain

All LLM calls go through LangChain's `ChatAnthropic` interface (or the equivalent provider class). LangChain abstracts the provider behind a common interface — `invoke`, `stream`, `bind_tools`, `with_structured_output` — so switching the underlying model or provider requires changing an environment variable and the model class import, not rewriting any agent logic, graph nodes, or tool definitions.

The preferred provider is Anthropic. The preferred models are Claude Sonnet 4.6 for generation and Claude Haiku 4.5 for classification. These are defaults, not hard dependencies. If requirements change — cost, capability, latency, compliance — the model can be swapped at the configuration layer.

```python
from langchain_anthropic import ChatAnthropic
# swap to any other provider by changing this import and the model string
# from langchain_openai import ChatOpenAI
# from langchain_google_genai import ChatGoogleGenerativeAI

llm_large = ChatAnthropic(model=LLM_LARGE_MODEL)    # preferred: claude-sonnet-4-6
llm_small = ChatAnthropic(model=LLM_SMALL_MODEL)    # preferred: claude-haiku-4-5-20251001
```

Environment variables use generic names — `LLM_LARGE_MODEL` and `LLM_SMALL_MODEL` — not provider-specific names, reinforcing that the model string is a configuration concern, not an architectural one.

### Large model (default: Claude Sonnet 4.6)

Used for all generation tasks that require reasoning, writing quality, or nuanced understanding:

- Profile normalisation
- Resume and cover letter generation
- Roadmap generation
- Job description analysis
- Conversational responses in prep and document engines

### Small model (default: Claude Haiku 4.5)

Used for all classification, extraction, and scoring tasks where speed and cost matter more than generation quality:

- Engine classification
- Cross-engine validation
- Job result scoring
- Conversation compression and summarisation
- Auto-generating chat titles
- ATS keyword extraction

### Prompt caching

Where the active provider supports prompt caching (Anthropic does natively), the system prompt for each engine and the profile context are passed with `cache_control: ephemeral`. This reduces input token costs significantly on repeated calls within the cache TTL window. If the provider is switched to one that does not support prompt caching, this gracefully degrades — the calls still work, just without the cache discount.

A keepalive task pings the cached prompts every 4 minutes to maintain the cache TTL.

---

## Tool Architecture

All tools use the `@tool` decorator from `langchain_core.tools`. Bound to the LLM via `llm.bind_tools(tools)`. LangGraph's built-in `ToolNode` handles execution and automatically feeds results back into `state["messages"]` as `ToolMessage` objects.

### Shared tools (available to all engines)

```python
@tool
def get_profile_context(query: str) -> str:
    """Retrieve relevant sections of the user's professional profile
    based on the query. Use this when you need to know the user's
    skills, experience, or background."""
    ...

@tool
def get_recent_job_searches(limit: int = 5) -> list:
    """Retrieve the user's most recently saved or searched jobs.
    Use this to find context about what roles the user is targeting."""
    ...

@tool
def get_long_term_memories() -> str:
    """Retrieve facts remembered about this user from previous sessions,
    such as target companies, preferences, and stated goals."""
    ...
```

### Engine-specific tools

Defined in each engine's own `tools/` module. Detailed in each engine's document.

---

## Redis Database Allocation

Redis supports 16 logical databases (db=0 through db=15) on a single instance. Each concern gets its own dedicated database — zero key collision, clean isolation, independent flush without affecting other concerns.

```
db=0    auth sessions         access:{jti}, refresh:{token_hash}
db=1    websocket / pubsub    stream:{user_id}, presence:{user_id}
db=2    chat session cache    session:cache:{user_id}:{chat_id}, classification results
db=3    rate limiting         slowapi counters for login and API throttling
```

Each database gets its own connection pool initialised at startup. Services receive the pool relevant to their concern via `Depends()` — the auth service never touches db=1, the pub/sub manager never touches db=0.

---

## Singleton Initialisation

All infrastructure clients are initialised once in the FastAPI lifespan context manager and stored on `app.state`. They are never instantiated per request.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await create_async_engine(DATABASE_URL)

    # four isolated Redis connection pools, one per logical database
    app.state.redis_auth = await aioredis.from_url(REDIS_URL, db=0)
    app.state.redis_pubsub = RedisPubSubManager(REDIS_URL)
    await app.state.redis_pubsub.startup()              # connects on db=1
    app.state.redis_cache = await aioredis.from_url(REDIS_URL, db=2)
    app.state.redis_ratelimit = await aioredis.from_url(REDIS_URL, db=3)

    app.state.qdrant = QdrantClient(QDRANT_HOST, QDRANT_PORT)
    app.state.llm_large = ChatAnthropic(model=LLM_LARGE_MODEL)   # preferred: claude-sonnet-4-6
    app.state.llm_small = ChatAnthropic(model=LLM_SMALL_MODEL)   # preferred: claude-haiku-4-5-20251001
    app.state.checkpointer = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
    await app.state.checkpointer.setup()
    app.state.store = AsyncPostgresStore.from_conn_string(DATABASE_URL)
    await app.state.store.setup()
    app.state.connection_manager = ConnectionManager()
    yield
    await app.state.redis_pubsub.shutdown()
    await app.state.redis_auth.aclose()
    await app.state.redis_cache.aclose()
    await app.state.redis_ratelimit.aclose()
    await app.state.db_pool.dispose()
```

---

## Directory Structure

```
backend/
  app/
    core/
      config.py               environment variable loading
      security.py             JWT encode/decode, bcrypt
      dependencies.py         FastAPI Depends() providers
      compression.py          conversation compression logic
    websocket/
      manager.py              ConnectionManager
      pubsub.py               RedisPubSubManager
      router.py               ws endpoint, auth handshake, message dispatch
      schemas.py              WebSocket message Pydantic models
    classification/
      classifier.py           Haiku classification call
      validator.py            cross-engine validation
      schemas.py              ClassificationResult model
    agents/
      shared/
        tools/
          profile_tool.py
          job_history_tool.py
          memory_tool.py
        memory/
          store.py            AsyncPostgresStore read/write helpers
          compression.py      message compression logic
      job/
      prep/
      document/
      tracker/
    vector/
      qdrant_client.py        singleton Qdrant client
      embeddings.py           Jina embedding calls with correct task types
      chunks.py               profile markdown parser and chunker
    llm/
      client.py               ChatAnthropic singleton wrappers
      router.py               model selection logic
      cache.py                prompt cache keepalive
    profile/
      extractor.py            pypdf2 and python-docx extraction
      normaliser.py           Sonnet normalisation call
      indexer.py              chunking, embedding, Qdrant upsert
    db/
      session.py              async SQLAlchemy engine and session factory
      models/
        base.py
        users.py
        sessions.py
        chat_sessions.py
        jobs.py
        documents.py
        prep.py
        profile.py
    routes/
      auth.py
      profile.py
      tracker_panel.py
    services/
    repositories/
```

---

## Environment Variables

```
DATABASE_URL                  postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL                     redis://localhost:6379
REDIS_DB_AUTH                 0
REDIS_DB_PUBSUB               1
REDIS_DB_CACHE                2
REDIS_DB_RATELIMIT            3
QDRANT_HOST                   localhost
QDRANT_PORT                   6333
ANTHROPIC_API_KEY
LLM_LARGE_MODEL               claude-sonnet-4-6          # preferred large model
LLM_SMALL_MODEL               claude-haiku-4-5-20251001  # preferred small model
JINA_API_KEY
SERP_API_KEY
JWT_ACCESS_SECRET
JWT_REFRESH_SECRET
JWT_ACCESS_EXPIRY_MINUTES     15
JWT_REFRESH_EXPIRY_DAYS       30
BCRYPT_COST                   12
APP_ENV                       development | production
APP_HOST
APP_PORT
```