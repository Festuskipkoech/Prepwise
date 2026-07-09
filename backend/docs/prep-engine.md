# Interview Preparation Engine

## Overview

The prep engine is a conversational interview coach. It builds a structured preparation roadmap tailored to the user's background and target role, then works through it in a natural multi-turn session — explaining concepts, asking questions, quizzing the user, giving honest feedback, and adjusting depth based on demonstrated knowledge. The roadmap lives in the agent's awareness at all times but the user experiences it as a flowing conversation, not a rigid curriculum.

---

## Conversation Design

### Agent personality

A senior mentor who has seen hundreds of interviews. Patient but direct. Knows when to explain deeply and when to push. Gives honest, specific feedback — not generic praise. Runs the session like a real interview mixed with a tutoring session. Moves at the user's pace, not a fixed pace.

### Conversation flow

**Turn 1 — vague intent ("I want to prep for an ML interview"):**

The agent does not immediately generate a roadmap. It checks the session state for recent job searches. If recent searches exist, it surfaces them:

"Are you prepping for one of these roles, or something different?"
- Senior ML Engineer at Safaricom
- Data Scientist at Equity Bank
- ML Research Engineer at Google

If no recent searches exist, it asks one focused question:

"What role and company are you targeting? The more specific you are, the better I can tailor this."

**Turn 1 — specific intent ("I want to prep for a Google ML Engineer interview"):**

The agent calls `get_profile_context` silently to understand the user's existing strengths and gaps relative to ML engineering. It calls `get_job_description` if a saved JD exists for this role. It then generates the roadmap and presents the opening of the first subject — not the full roadmap document, just a natural introduction to where they are starting:

"For a Google ML Engineer role, we are going to cover five areas: ML Fundamentals, Systems Design, Coding and Algorithms, Behavioural, and a Google-specific section on scale and reliability. Let's start with ML Fundamentals — specifically, how solid are you on the bias-variance tradeoff? Walk me through it."

The roadmap is stored in `state["roadmap"]` and the agent tracks position internally. The user never sees it as a rigid document. They experience it as a conversation that has direction.

**Mid-session — explanation, quiz, feedback loop:**

The agent introduces a concept, asks the user to explain or demonstrate it, gives specific feedback, and moves forward or goes deeper based on the response quality. This cycle continues through each topic.

If the user asks a question off-script: the agent answers it fully, then naturally returns — "good question. That actually connects to what we are about to cover. Let's get into it."

**Mid-session — user requests a break from the roadmap:**

The user might say "explain gradient descent again more slowly." The agent does this and then resumes — "got it. So to recap where we are: backpropagation covered, gradient descent covered. Next is regularisation."

The agent always knows where it is. It surfaces position naturally, not mechanically.

**End of roadmap or user signals readiness:**

The agent gives an honest readiness assessment — specific, not generic — then offers the natural next step:

"You are strong on the fundamentals and systems design. Coding under pressure is where I would spend another day. When you are ready to apply, I can open a document chat to tailor your resume for this role."

---

## LangGraph Graph

### State

```python
class PrepState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    chat_id: str
    target_role: str
    target_company: str
    job_id: str                         # if linked to a saved job
    profile_context: str
    jd_text: str
    roadmap: dict                       # full roadmap structure
    roadmap_id: str                     # UUID of prep_roadmaps row
    current_subject_index: int
    current_topic_index: int
    calibration_depth: str              # surface | standard | deep
    topic_mastery: dict                 # {topic_name: assessed_level}
    session_mode: str                   # explaining | quizzing | discussing
    last_question_asked: str
    waiting_for_answer: bool
    user_constraints: dict
```

### Nodes

```
assess_context
    Checks if target_role and target_company are known
    If not: checks for recent job searches, returns them or asks one question
    If yes: proceeds to roadmap generation or roadmap resume

load_profile_and_jd
    Calls get_profile_context with role-specific query
    Calls get_job_description if job_id is known
    Populates state["profile_context"] and state["jd_text"]

generate_roadmap
    Large LLM call: builds structured roadmap from profile gaps and JD
    Roadmap format:
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
    Saves roadmap to prep_roadmaps table
    Populates state["roadmap"], state["roadmap_id"]

resume_roadmap
    Loads existing roadmap from prep_roadmaps table
    Restores state["current_subject_index"] and state["current_topic_index"]

introduce_topic
    Generates a natural introduction to the current topic
    Ends with an opening question to gauge the user's existing knowledge
    Sets state["session_mode"] = "discussing"
    Sets state["last_question_asked"]

process_user_response
    Evaluates the user's answer to the last question
    Updates state["topic_mastery"][current_topic]
    Updates state["calibration_depth"] based on response quality:
      - Strong answer: advance topic, reduce depth
      - Weak answer: go deeper before advancing
    Decides next action: explain, quiz, or advance

explain_concept
    Large LLM call: explains the current subtopic clearly
    Calibrates depth to state["calibration_depth"]
    Sets state["session_mode"] = "explaining"
    Ends with a check-in question

quiz_user
    Generates a targeted quiz question for the current topic
    Sets state["session_mode"] = "quizzing"
    Sets state["waiting_for_answer"] = True

give_feedback
    Evaluates quiz answer specifically and honestly
    References what was right, what was missing, what interviewers push on
    Sets state["waiting_for_answer"] = False

advance_topic
    Increments current_topic_index or current_subject_index
    Updates prep_roadmaps table with new position
    Transitions to introduce_topic for the next topic

generate_readiness_assessment
    Large LLM call: honest assessment based on state["topic_mastery"]
    Identifies strong areas and areas needing review
    Offers handoff to document engine

handle_offscript
    Handles questions or diversions that are not on the current topic
    Answers fully, then returns to roadmap position
```

### Edges

```
START -> assess_context

assess_context -> load_profile_and_jd          (role and company known)
assess_context -> ask_clarification             (need more context)
assess_context -> resume_roadmap                (returning to existing session)

load_profile_and_jd -> generate_roadmap         (no roadmap exists)
load_profile_and_jd -> resume_roadmap           (roadmap exists)

generate_roadmap -> introduce_topic
resume_roadmap -> introduce_topic

introduce_topic -> END                          (streams introduction, waits for user)

process_user_response -> explain_concept        (user is weak on topic)
process_user_response -> quiz_user              (user has explained adequately)
process_user_response -> advance_topic          (user has demonstrated mastery)
process_user_response -> handle_offscript       (user asked an off-topic question)

explain_concept -> END
quiz_user -> END
give_feedback -> advance_topic
give_feedback -> explain_concept                (answer was significantly wrong)
advance_topic -> introduce_topic
advance_topic -> generate_readiness_assessment  (all topics covered)
generate_readiness_assessment -> END
handle_offscript -> introduce_topic             (return to roadmap)
```

---

## Tools

```python
@tool
def get_profile_context(query: str) -> str:
    """Retrieve relevant sections of the user's profile.
    Use this to understand their existing knowledge depth before building the roadmap."""

@tool
def get_recent_job_searches(limit: int = 5) -> list:
    """Retrieve the user's recently saved jobs.
    Use this when the user has not specified a target role, to offer them options."""

@tool
def get_job_description(job_id: str) -> str:
    """Retrieve the full job description for a saved job.
    Use this to tailor the roadmap to the specific role's requirements."""

@tool
def save_roadmap(roadmap: dict, role: str, company: str, job_id: str = None) -> str:
    """Save the generated roadmap to the database. Returns the roadmap_id."""

@tool
def update_roadmap_progress(roadmap_id: str, subject_index: int, topic_index: int) -> None:
    """Update the user's current position in the roadmap."""

@tool
def get_long_term_memories() -> str:
    """Retrieve facts remembered about this user from previous sessions."""
```

---

## System Prompt

```
You are a senior interview coach with deep knowledge across technical and professional domains.
You are helping this user prepare for a specific interview role.

Your operating rules:
- Always know where you are in the roadmap. Track it in your state. Reference it naturally in transitions.
- Introduce each topic conversationally, not as a menu item. Connect it to why it matters for this specific role and company.
- Gauge the user's existing knowledge before explaining. Ask first, then calibrate your explanation depth to what they showed you.
- Ask one question at a time. Always. Wait for the answer before continuing.
- Give specific, honest feedback. "That is right but you missed X which is what interviewers push on" is better than "great answer."
- Adjust pace to demonstrated mastery. Move faster through areas they know well. Go deeper where they are shaky.
- When the user goes off-script, answer the question fully and naturally return to where you were.
- Reference what was covered earlier in the session naturally. "You mentioned earlier that..." shows you were listening.
- At the end, give an honest readiness assessment. Be specific about strengths and gaps. Not generic.
- If the user asks about resume or cover letter, acknowledge and suggest opening a document chat with this role's context loaded.

Session mode awareness:
- explaining: you are teaching a concept, end with a check-in
- quizzing: you asked a question, wait for the answer, do not continue until they respond
- discussing: open conversation about a topic, guide toward the roadmap

Never break character. You are a mentor who knows this user's background and cares about their outcome.
```

---

## Database Schema

```
prep_roadmaps
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid()
  user_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
  chat_session_id       UUID REFERENCES chat_sessions(id) ON DELETE SET NULL
  job_id                UUID REFERENCES jobs(id) ON DELETE SET NULL
  target_role           TEXT NOT NULL
  target_company        TEXT
  raw_roadmap           JSONB NOT NULL
  current_subject_index INTEGER NOT NULL DEFAULT 0
  current_topic_index   INTEGER NOT NULL DEFAULT 0
  topic_mastery         JSONB DEFAULT '{}'
  status                TEXT NOT NULL DEFAULT 'active'   -- active | completed
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
```

Indexes:
- `prep_roadmaps(user_id)` for listing all user roadmaps
- `prep_roadmaps(user_id, status)` for active roadmaps
- `prep_roadmaps(chat_session_id)` for linking back to chat

Multiple active roadmaps per user are supported. Each has its own `chat_session_id` and its own `thread_id` in the LangGraph checkpointer, so they are fully independent.

---

## Prep Chunks in Qdrant

As subtopics are covered in sessions, they are embedded and stored in `prep_chunks_{user_id}` for future retrieval. This allows the system to surface relevant past prep content across sessions.

Chunk unit: each covered subtopic
Metadata: `subject`, `topic`, `subtopic`, `skill_tags`, `mastery_level`, `session_date`

---

## Streaming Pattern

All conversational responses stream token by token via `stream_mode=["custom", "messages"]`. Status events — "Building your roadmap...", "Evaluating your answer..." — are emitted via `get_stream_writer()` between LLM calls where the model is silent.

The roadmap generation step is the heaviest single call. A status event is emitted before it begins so the user sees activity immediately rather than a blank screen.

---

## Seamless Conversation Checklist

- `state["roadmap"]` always present after generation — agent never loses track of position
- `state["calibration_depth"]` adjusts explanation depth dynamically per topic
- `state["topic_mastery"]` maintains an honest running record across the session
- `state["session_mode"]` prevents the agent from asking a new question while waiting for an answer to the last one
- `state["last_question_asked"]` ensures follow-up evaluation is contextually precise
- Off-script handling always returns naturally to roadmap position
- Long-term memories loaded at session start for cross-session continuity
- `prep_roadmaps` table ensures roadmap survives WebSocket disconnection and can be resumed