# Authentication and Session Management

## Overview

Prepwise uses a dual-token authentication system built for commercial scale. Every user registers independently, owns their data in isolation, and maintains sessions across multiple devices. There is no single-user assumption anywhere in the architecture.

---

## Token Strategy

### Access Token

- Format: JWT signed with HS256
- Expiry: 15 minutes
- Payload: `user_id`, `email`, `jti` (unique token ID), `iat`, `exp`
- Transmitted: `Authorization: Bearer <token>` header on all HTTP requests
- For WebSocket: passed as `?token=<access_token>` query parameter on the upgrade handshake

### Refresh Token

- Format: JWT signed with a separate secret (RS256 in production)
- Expiry: 30 days
- Stored: hashed in PostgreSQL `sessions` table (source of truth) and cached in Redis
- Transmitted: `HttpOnly`, `Secure`, `SameSite=Strict` cookie only
- One refresh token per session (device)
- Rotating: every refresh call issues a new refresh token and invalidates the old one

### Why two tokens

The access token is short-lived so that if it is leaked, the damage window is small. The refresh token is long-lived and stored in an HttpOnly cookie so JavaScript cannot read it, which eliminates the most common XSS theft vector. The combination gives the user a seamless experience (they do not log in every 15 minutes) while keeping the security surface tight.

---

## Redis Caching Layer

Both tokens are cached in Redis on top of PostgreSQL. PostgreSQL is always the source of truth. Redis is a fast read-through cache that makes validation cheap and revocation instant.

### Why both tokens in Redis

- Access token cache: every protected request validates the token. At commercial scale this is a high-frequency operation. Redis brings it to sub-millisecond without hitting PostgreSQL on every request.
- Refresh token cache: every token refresh validates the refresh token. Caching it avoids a database read on every refresh cycle.
- Instant revocation: deleting a key from Redis is immediate. The user is effectively logged out the moment logout is called, even before the access token's 15-minute TTL expires.

### Redis database

Auth token caching uses **Redis db=0**, dedicated exclusively to session management. No other part of the application writes to db=0. This means auth keys can never collide with pub/sub channels, cache entries, or rate limit counters from other concerns, and db=0 can be flushed independently in an emergency without affecting any other system.

### Redis key structure

```
db=0    access:{jti}              TTL 15 minutes    value: user_id
db=0    refresh:{token_hash}      TTL 30 days       value: session_id
```

### Read path (validation)

1. Check Redis for the key
2. If found and valid: proceed — no database hit
3. If not found (cold start, TTL expired, Redis was down): fall back to PostgreSQL, validate there, re-populate Redis
4. If found in neither: reject the token

### Write path (login)

1. Write session row to PostgreSQL first
2. Write both token keys to Redis with their TTLs
3. If the Redis write fails: log the failure, do not fail the login — PostgreSQL has it and the fallback path will re-populate Redis on the next request

### Revocation path (logout)

1. Delete both Redis keys immediately — instant revocation
2. Set `revoked_at` in PostgreSQL — durable revocation
3. If Redis delete fails: PostgreSQL revocation catches it on the next fallback lookup

### Rotation path (token refresh)

1. Delete old refresh key from Redis
2. Write new access and refresh keys to Redis
3. Update PostgreSQL session row atomically
4. The old refresh token is invalid from the moment its Redis key is deleted

### Redis outage behaviour

If Redis is unavailable, all validation falls back to PostgreSQL. Users remain logged in. Performance degrades gracefully — slightly slower requests, not broken sessions. This is the critical advantage of keeping PostgreSQL as the source of truth.

---

## Database Tables

### users

```sql
id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
email             TEXT UNIQUE NOT NULL
password_hash     TEXT NOT NULL
full_name         TEXT
is_active         BOOLEAN NOT NULL DEFAULT true
created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
```

### sessions

```sql
id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
refresh_token     TEXT UNIQUE NOT NULL          -- bcrypt hash of the raw token
access_token_jti  TEXT UNIQUE NOT NULL          -- jti of the most recent access token
device_info       TEXT                          -- user-agent string
ip_address        INET
expires_at        TIMESTAMPTZ NOT NULL          -- refresh token expiry
last_used_at      TIMESTAMPTZ
created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
revoked_at        TIMESTAMPTZ                   -- null means active
```

Indexes:
- `sessions(user_id)` for listing a user's sessions
- `sessions(refresh_token)` for fallback token lookup
- `sessions(access_token_jti)` for fallback access token validation
- `sessions(user_id) WHERE revoked_at IS NULL` partial index for active session queries

---

## Endpoints

All auth endpoints are standard HTTP. No WebSocket involvement at this layer.

### POST /auth/register

Accepts `email`, `password`, `full_name`. Validates email format and password strength. Hashes password with bcrypt (cost factor 12). Creates user row. Does not auto-login — returns a success response and the client proceeds to login.

Password requirements: minimum 8 characters, at least one number, at least one special character.

### POST /auth/login

Accepts `email`, `password`. Looks up user by email. Verifies bcrypt hash. On success:

1. Generates access token JWT with a fresh `jti`
2. Generates refresh token JWT
3. Writes session row to PostgreSQL with hashed refresh token and `jti`
4. Writes `access:{jti}` to Redis with 15-minute TTL
5. Writes `refresh:{token_hash}` to Redis with 30-day TTL
6. Returns access token in response body
7. Sets refresh token as `HttpOnly` cookie

Returns `401` if credentials are wrong. Returns `403` if the account is inactive.

### POST /auth/refresh

Reads the refresh token from the cookie. Validates via Redis first, falls back to PostgreSQL. Validates:
- Token exists and is not revoked
- `expires_at` is in the future

On success:
1. Generates new access token with a fresh `jti`
2. Generates new refresh token (rotation)
3. Deletes old Redis keys: `access:{old_jti}` and `refresh:{old_token_hash}`
4. Writes new Redis keys with new TTLs
5. Updates PostgreSQL session row: new hashed refresh token, new `access_token_jti`, updated `last_used_at`
6. Returns new access token in response body
7. Sets new refresh token cookie, clears old one

Replay attack detection: if the old refresh token arrives after rotation, it will not be found in Redis and the PostgreSQL lookup will show `revoked_at` is set. The entire session is immediately revoked.

### POST /auth/logout

Reads the refresh token from the cookie:
1. Deletes `access:{jti}` from Redis — immediate access token invalidation
2. Deletes `refresh:{token_hash}` from Redis — immediate refresh token invalidation
3. Sets `revoked_at` in PostgreSQL — durable record of revocation
4. Clears the cookie

### POST /auth/logout-all

Revokes all active sessions for the current user:
1. Queries PostgreSQL for all active sessions for this user
2. Deletes all corresponding Redis keys in a pipeline (atomic batch delete)
3. Sets `revoked_at` on all session rows in PostgreSQL
4. Clears the cookie

### GET /auth/sessions

Returns active sessions for the current user: `device_info`, `ip_address`, `created_at`, `last_used_at`. Powers the account settings panel where users can see and revoke individual sessions.

### DELETE /auth/sessions/{session_id}

Revokes a specific session remotely:
1. Loads session from PostgreSQL to get the `jti` and `refresh_token` hash
2. Deletes both Redis keys
3. Sets `revoked_at` in PostgreSQL

---

## WebSocket Authentication

The browser WebSocket API does not support custom headers, so the `Authorization: Bearer` pattern used on HTTP endpoints cannot be used on the WebSocket upgrade request.

The approach is the query parameter pattern:

```
ws://host/ws/{user_id}?token=<access_token>
```

The access token is short-lived at 15 minutes, limiting exposure in server logs. The WebSocket handler validates before calling `websocket.accept()`:

1. Extract `token` from query parameters
2. Decode and validate the JWT: signature, expiry, `jti`
3. Check Redis for `access:{jti}` — if missing, fall back to PostgreSQL session check
4. If invalid or revoked: `websocket.close(code=1008)` without accepting
5. If valid: `websocket.accept()` and proceed

The connection stays alive for its duration. Re-authentication happens at reconnection. The client refreshes the access token via `/auth/refresh` before reconnecting if disconnected.

---

## Profile Check on First Login

After login the client calls `GET /profile/status`. If no profile exists, the client redirects to the profile upload flow before rendering the chat interface. This check is enforced on the frontend only.

---

## Multi-Tenancy

Every table carrying user data has a `user_id` foreign key. Every repository query filters by `user_id` from the validated JWT. No global data or shared state between users at any layer.

LangGraph checkpointer tables are namespaced by `thread_id` which is always `{user_id}:{chat_id}`. Qdrant vectors are namespaced by `user_id` metadata on every query.

---

## Security Considerations

### Password storage

bcrypt with cost factor 12. Never stored or logged in plain text.

### Token secrets

Access token secret and refresh token secret are separate environment variables. Rotating either secret invalidates all tokens signed with the old secret — emergency kill switch for all sessions.

### Rate limiting

Login endpoint: 5 attempts per IP per minute via `slowapi`. After 5 failures the IP is blocked for 15 minutes. Applied at the FastAPI middleware layer.

### CORS

Strict CORS policy. Only the registered frontend origin is allowed. Credentials mode enabled for cookie transmission.

### HttpOnly cookie flags

Refresh token cookie: `HttpOnly=true`, `Secure=true`, `SameSite=Strict`, `Path=/auth`. Scoped to `/auth` so it is only sent to auth endpoints.

### Redis security

Redis must be configured with `requirepass` in production. Never expose Redis publicly. Access restricted to the application server only via network policy or firewall rules. Auth uses db=0 exclusively — if an emergency flush of auth sessions is needed, `FLUSHDB` on db=0 logs out all users without touching pub/sub, cache, or rate limiting on other databases.

---

## Libraries

```
python-jose[cryptography]     JWT encoding and decoding
passlib[bcrypt]               password hashing
slowapi                       rate limiting
redis.asyncio                 async Redis client
python-multipart              form parsing for login endpoint
```

---

## Environment Variables

```
JWT_ACCESS_SECRET             secret for signing access tokens
JWT_REFRESH_SECRET            secret for signing refresh tokens
JWT_ACCESS_EXPIRY_MINUTES     15
JWT_REFRESH_EXPIRY_DAYS       30
JWT_ALGORITHM                 HS256
BCRYPT_COST                   12
REDIS_URL                     redis://localhost:6379
REDIS_DB_AUTH                 0
```