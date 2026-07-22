# Prepwise

Most job seekers fail before they even get to the interview. Not because they lack the skills, but because their applications are generic, their preparation is scattered, and they have no system for tracking what is working and what is not. Prepwise is built to fix that.

Prepwise is a personal job search operating system. It brings together everything a serious job seeker needs into one place: finding the right roles, packaging yourself accurately for each one, preparing deeply for interviews, and keeping track of a search that can span dozens of applications over weeks or months.

It is not a job board. It is not a resume builder. It is not a flashcard app. It is a single intelligent system that handles all of it, grounded entirely in who you actually are.

---

## How it works

When you sign up, you upload your resume, CV, or any document that describes your professional background. Prepwise reads it, understands it, and builds a profile of you — your skills, your projects, your experience, and your strengths. Everything the system does from that point forward is grounded in that profile.

You interact with Prepwise through a single chat interface, the same way you would talk to a knowledgeable advisor. You tell it what you need. It understands your intent, asks you what it needs to know, and gets to work.

---

## What it does

### Find the right jobs

Before you search for a single role, Prepwise tells you what you should be looking for. It reads your background and surfaces the titles, disciplines, and seniority levels that match your actual experience. When you search, results come back scored against your profile so you immediately know which roles are worth your time and which are a stretch. You can refine, filter, and save roles you want to pursue.

### Tailor your resume and cover letter

Every role you apply for gets its own resume and cover letter. Not a template swap — a genuine rewrite where the most relevant parts of your experience are surfaced, the job description's language is used naturally, and the content is optimised for the way employers and their systems read applications. You see it appear in real time, can request any changes through the chat, and download a polished document when you are happy.

### Prepare for interviews

Your profile generates a preparation roadmap built entirely around your actual skills and experience. Not a generic curriculum — a structured map of everything you need to be able to speak to in an interview for the kind of roles you are targeting.

You work through it at your own pace in a conversational session with the system. It explains concepts, asks you questions, quizzes you, gives you honest feedback, and adjusts its depth based on how well you know each area. It runs like a real interview mixed with a tutoring session.

When you apply for a specific role, Prepwise also generates a focused sprint prep path for that exact job — mapping the role's requirements against your profile, identifying where you are strong and where you need to sharpen, and predicting the kinds of questions that employer is likely to ask.

### Track your applications

Every application you submit goes into your tracker. You log the status, your notes, follow-up dates, and any feedback you receive. Over time, Prepwise analyses your search and tells you where you are losing. Consistent ghosting suggests a packaging problem. Getting first rounds but no second rounds suggests a preparation problem. The analysis is honest and specific.

---

## The chat interface

Prepwise works through a single conversational interface. You do not navigate to separate tools for job search, document generation, or interview prep. You simply say what you need:

- "Help me find ML engineering roles in Nairobi"
- "Write me a resume for this job at Safaricom"
- "I want to prepare for a data science interview at a fintech"
- "Why am I not getting past first rounds?"

The system understands your intent, routes your request to the right capability, and responds the way a knowledgeable career advisor would — asking one focused question when it needs more context, acting decisively when it has enough, and remembering everything you have told it within a session.

---

## Who it is for

Prepwise is built for anyone running a serious job search. Whether you are a recent graduate applying for your first roles, an experienced professional making a career move, or a specialist targeting a specific industry, the system adapts to your background and your goals.

It is designed to scale from a single user running it locally to a commercial platform serving thousands of users simultaneously. Every feature works the same way regardless of scale.

---

## The technology

Prepwise is built on a modern, production-grade stack. The backend is a Python API powered by FastAPI, with intelligent agents built on LangGraph. Conversations stream in real time over WebSocket connections. All data is stored in PostgreSQL. Semantic search uses Jina embeddings and a Qdrant vector database. The frontend is built on Next.js.

---

## Technical Documentation

Full technical documentation lives in the `/docs` directory. Each document covers one concern end to end — architecture, agent design, graph structure, state, tools, system prompts, database interactions, and streaming pattern.

| Document | What it covers |
|---|---|
| [Authentication](backend/docs/auth.md) | Session management, dual-token strategy, Redis caching, WebSocket auth, multi-user security |
| [Shared Infrastructure](backend/docs/shared-infrastructure.md) | WebSocket layer, Redis pub/sub, classification, LangGraph checkpointing, profile ingestion, vector store, model routing |
| [Job Search Engine](backend/docs/job-engine.md) | Job search agent, tool definitions, conversation flow, result scoring, graph structure |
| [Prep Engine](backend/docs/prep-engine.md) | Interview prep agent, roadmap generation, conversational drilling, quiz and feedback loop, graph structure |
| [Document Engine](backend/docs/document-engine.md) | Resume and cover letter generation, iterative editing, version history, graph structure |
| [Tracker Engine](backend/docs/tracker-engine.md) | Application tracking panel, conversational analysis agent, funnel analysis, graph structure |
| [Database Design](backend/docs/database.md) | Full schema, indexes, Redis database allocation, Qdrant collections, query patterns per engine |

---

## Status

Active development.

## License

MIT