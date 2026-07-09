# Application Tracking Engine

## Overview

The tracker engine has two distinct surfaces: a structured data entry panel for logging applications, and a conversational chat interface where the agent analyses the user's search, surfaces patterns, and gives honest, data-grounded advice. The panel does not involve AI. The chat does not involve manual data entry. They complement each other cleanly.

---

## Two Surfaces

### The Panel (non-chat)

A dedicated UI panel where the user logs and manages applications. Standard HTTP endpoints. No WebSocket. No LLM involvement.

The user inputs:
- Job title and company
- Link to the job posting
- Application status
- Date applied
- Follow-up date
- Notes
- Rejection reason (when applicable)

The panel also displays:
- Full application list with filtering by status
- Follow-up alerts: due today, overdue, upcoming
- A visual pipeline showing application counts at each stage

All of this is computed directly from the `jobs` table. No AI needed.

### The Chat Interface

The conversational surface where the user discusses their search, asks questions, and gets honest analysis. This is where the agent lives. It reads the user's tracker data, identifies patterns, and gives specific actionable advice.

---

## Conversation Design

### Agent personality

An honest, data-aware advisor. Like a coach reviewing game tape. Does not sugarcoat. Reads what the data actually says, not what the user wants to hear. Proactive — surfaces things the user has not asked about if they are worth knowing.

### Conversation flow

**Turn 1 — opening a tracker chat:**

The agent does not wait for a question. It opens with a data snapshot drawn from the user's current tracker state:

"You have 14 active applications. 3 are at interview stage. 2 follow-ups are overdue — Equity Bank from 12 days ago and Twiga Foods from 8 days ago. Your application-to-first-response rate over the last 30 days is 21%. Want to dig into any of this?"

This is not generic. Every number comes from the database. The agent earned the right to speak by doing the work first.

**Turn 2+ — user asks a specific question:**

"Why am I not getting past first rounds?"

The agent queries the tracker data, looks at the pattern, and gives a specific answer:

"You have had 4 first-round interviews in the last 6 weeks. None went to a second round. Three of the four rejections came from companies where you applied with an unmodified resume — same document for different roles. The one where you did tailor it, you got a second round. That is a document problem, not a preparation problem. Want me to open a document chat to fix that?"

The observation is grounded in specific data, leads to a specific diagnosis, and offers a concrete next step.

**Proactive surfacing:**

The agent notices things the user did not ask about. If the data shows a pattern worth surfacing, it does:

"You mentioned follow-up dates but I also noticed your application rate dropped by 60% in the last two weeks. Is the search slowing down by choice or are you stuck somewhere?"

**Cross-engine handoffs:**

The tracker agent regularly identifies problems that other engines solve. It handles these by acknowledging the problem clearly, naming the right engine, and offering to open it:

- Document problem → "Want to open a document chat to fix the tailoring?"
- Prep problem → "Want to open a prep chat to work on first-round interviews?"
- Search problem → "Want to open a job search chat to find more roles in this category?"

---

## LangGraph Graph

### State

```python
class TrackerState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    chat_id: str
    dashboard_snapshot: dict            # loaded at session start
    follow_ups: dict                    # due today, overdue, upcoming
    active_filters: dict                # date range, company, status filters
    analysis_cache: dict                # computed patterns cached for session
    last_query_type: str                # what the agent last analysed
    surfaced_insights: list[str]        # insights already shown this session
```

### Nodes

```
load_dashboard
    Runs at the start of every new session
    Calls get_application_stats tool
    Calls get_followups_due tool
    Populates state["dashboard_snapshot"] and state["follow_ups"]
    Generates the opening snapshot message

classify_query
    Determines what the user is asking:
    - funnel_analysis: why am I not getting X
    - follow_up_check: who do I need to follow up with
    - pattern_analysis: what is working and what is not
    - status_update: update a specific application
    - general_discussion: open-ended conversation about the search

run_funnel_analysis
    Queries jobs table for conversion rates at each stage
    Identifies where the user is losing applications
    Small LLM call: interprets the pattern and generates insight

run_pattern_analysis
    Broader analysis: company sizes, role types, application timing, document usage
    Identifies correlations in what is working vs not working
    Small LLM call: interprets and generates recommendations

run_followup_check
    Retrieves overdue and upcoming follow-ups from jobs table
    Formats them clearly with company, days elapsed, suggested action

generate_response
    Large LLM call: composes the final response
    References specific data points
    Identifies cross-engine handoffs where relevant
    Streams token by token

handle_status_redirect
    Tracker status updates happen in the panel, not the chat
    Agent politely redirects: "To update an application status, use the tracker panel.
    I can help you analyse patterns or discuss your strategy here."
```

### Edges

```
START -> load_dashboard                     (new session)
START -> classify_query                     (continuing session, dashboard already loaded)

load_dashboard -> generate_response         (opening snapshot)

classify_query -> run_funnel_analysis
classify_query -> run_pattern_analysis
classify_query -> run_followup_check
classify_query -> generate_response         (general discussion)
classify_query -> handle_status_redirect    (user trying to update status in chat)

run_funnel_analysis -> generate_response
run_pattern_analysis -> generate_response
run_followup_check -> generate_response
handle_status_redirect -> END
generate_response -> END
```

---

## Tools

```python
@tool
def get_application_stats(user_id: str, days: int = 30) -> dict:
    """Get aggregated application statistics for the user.
    Returns: total applications, status breakdown, conversion rates per stage,
    application rate per week, response rate."""

@tool
def get_followups_due(user_id: str) -> dict:
    """Get applications requiring follow-up.
    Returns: overdue (list with days elapsed), due_today (list), upcoming (list)."""

@tool
def get_application_history(
    user_id: str,
    status: str = None,
    company: str = None,
    date_from: str = None,
    date_to: str = None,
    cursor_id: str = None,
    page_size: int = 20
) -> dict:
    """Get paginated application history with optional filters.
    Uses cursor pagination on (created_at DESC, id DESC)."""

@tool
def get_stage_conversion_rates(user_id: str) -> dict:
    """Get conversion rates between each application stage.
    Returns: applied_to_screening, screening_to_interview,
    interview_to_offer, offer_to_acceptance rates."""

@tool
def get_pattern_data(user_id: str) -> dict:
    """Get data for pattern analysis: company sizes, role types,
    document usage per application, application timing, rejection reasons."""

@tool
def get_long_term_memories() -> str:
    """Retrieve facts remembered about this user from previous sessions."""
```

---

## System Prompt

```
You are an honest, data-aware career advisor analysing a job seeker's application pipeline.
You have access to their full application history and can run analysis on it.

Your operating rules:
- Always open a new session with a data snapshot. Do not wait to be asked. Pull the numbers
  and present them immediately. Be specific — use actual counts and rates from the data.
- Be honest about what the data says. If the pattern is bad news, say so clearly and specifically.
  "Your application-to-response rate is 12%, which is low" is better than vague encouragement.
- Ground every insight in specific data. Do not make claims the data does not support.
- Proactively surface patterns the user has not asked about if they are worth knowing.
  Do not dump everything at once — surface the most important thing, then let the conversation develop.
- When the data points to a problem that another engine solves, name it and offer the handoff.
  Be specific about why: "This looks like a document tailoring problem — want me to open a
  document chat?" is better than "you should improve your resume."
- Do not let users update application statuses through chat. Redirect them to the panel.
- Remember what was surfaced earlier in this session. Do not repeat the same insight twice.
- Application tracking data can be sensitive — the user may be anxious about their search.
  Be honest but not harsh. The goal is clarity and forward motion, not discouragement.

When referencing data, be precise:
- Use actual numbers, not approximations unless the data is genuinely uncertain
- Reference time periods explicitly: "in the last 30 days", "over the past 6 weeks"
- Name specific companies and roles when relevant and helpful
- Note when a pattern is based on a small sample and may not be conclusive
```

---

## Panel Endpoints (HTTP, no WebSocket)

```
POST   /tracker/jobs                        create new application manually
GET    /tracker/jobs                        list with filters and cursor pagination
PATCH  /tracker/jobs/{id}                   update status, notes, dates
DELETE /tracker/jobs/{id}                   remove application
GET    /tracker/dashboard                   aggregated stats, follow-up alerts
GET    /tracker/follow-ups                  due today, overdue, upcoming
GET    /tracker/history                     cursor-paginated application history
```

These are thin HTTP routes that call tracker repository methods directly. No LangGraph involvement. No streaming.

---

## Database Schema (tracker relevant)

The tracker engine works entirely from the `jobs` table. No additional tables needed for the tracker engine specifically.

```
jobs
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
  title             TEXT NOT NULL
  company           TEXT
  source_url        TEXT
  jd_text           TEXT
  source            TEXT NOT NULL DEFAULT 'manual'   -- search | manual
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
- `jobs(user_id)` baseline filter for all queries
- `jobs(user_id, status)` for status-based analysis
- `jobs(user_id, applied_date)` for time-series analysis
- `jobs(user_id, follow_up_date)` for follow-up queries
- `jobs(user_id, created_at DESC, id DESC)` for cursor pagination

### Cursor pagination pattern

Application history uses cursor pagination on `(created_at DESC, id DESC)`. The client passes the `id` of the last received record as `cursor_id`. The server returns records strictly before that position. Stable under concurrent writes, performant at scale, no duplicates or skipped records.

```sql
SELECT * FROM jobs
WHERE user_id = :user_id
  AND (created_at, id) < (
      SELECT created_at, id FROM jobs WHERE id = :cursor_id
  )
ORDER BY created_at DESC, id DESC
LIMIT :page_size
```

---

## Streaming Pattern

The tracker chat uses `stream_mode=["custom", "messages"]` like all other engines. Status events for analysis operations: "Analysing your funnel...", "Looking at conversion rates...". Token streaming for the final response. The analysis computations happen in graph nodes before the response is generated, so the user sees the status events while the system is working and then the response streams in.

---

## Seamless Conversation Checklist

- Dashboard snapshot loaded at session start — agent opens with real data, not a greeting
- `state["analysis_cache"]` prevents re-running the same analysis multiple times in a session
- `state["surfaced_insights"]` prevents the agent from repeating the same observation twice
- Proactive pattern surfacing gives the agent the feel of a real advisor, not a query interface
- Clear cross-engine handoff language with specific reasoning
- Status update redirection handled gracefully, not coldly
- Long-term memories at session start for context about the user's overall search history
- Honest tone enforced in system prompt — data-grounded, not encouraging noise