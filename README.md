# Prepwise

Most job seekers fail before they even get to the interview. Not because they lack the
skills, but because their applications are generic, their preparation is scattered, and
they have no system for tracking what is working and what is not. Prepwise is built to
fix that.

Prepwise is a personal job search operating system. It sits at the intersection of four
problems that every serious job seeker faces simultaneously: finding the right roles,
packaging themselves accurately for each one, preparing deeply for interviews, and
keeping track of a search that can span dozens of applications over weeks or months.

It is not a job board. It is not a resume builder. It is not a flashcard app. It is a
single system that handles all of it, grounded entirely in who you actually are.

---

## What it does

**Job search with intelligent targeting**

Before you search for a single role, Prepwise reads your profile and tells you what you
should be looking for. It infers your discipline, your strongest lane, and the titles
that map to your real experience. You can take its suggestions or override them. When
you search, results come back scored against your profile so you know immediately which
roles are worth pursuing and which are a stretch.

**Tailored resume and cover letter generation**

Every role you apply for gets its own resume and cover letter. Not a template swap, but
a genuine rewrite where the most relevant parts of your experience are surfaced, the job
description's language is used naturally, and ATS keywords are placed without stuffing.
The output is plain structured content that renders into a polished document in your
chosen format.

**Roadmap-driven interview preparation**

Your profile generates a preparation roadmap scoped entirely to your actual skills and
experience. Not a generic curriculum, but a structured map of every subject and topic
you need to be able to speak to in an interview. You drill through it at your own pace,
one level at a time. Subjects break into topics, topics break into subtopics, subtopics
break into questions. Nothing is generated until you need it. When you practice, the
session is conversational and interconnected, the way a real interview is, not a
disconnected set of flashcards.

When you apply for a specific role, Prepwise generates a separate sprint prep path for
that exact job. It maps the JD against your profile, identifies where you are strong and
where you need to sharpen, generates predicted interview questions for that company and
domain, and links back to the relevant parts of your master roadmap.

**Application tracking with pattern analysis**

Every application you submit goes into a tracker. Status, notes, follow-up dates,
rejection reasons. Over time, Prepwise analyses your funnel and tells you where you are
losing. Getting applications ghosted consistently points to a packaging problem.
Getting interviews but no offers points to a preparation problem. The analysis is honest
and specific, not generic advice you could have found in a blog post.

---

## How it works

Everything in Prepwise flows from a single source of truth: your master profile. This is
a markdown file you write and maintain. It contains your skills with their real depth,
your projects with their real metrics, your experience with your real contributions.
Every resume, every cover letter, every interview question, every search suggestion is
grounded in what is actually in that file.

The backend is a FastAPI application with five independent engines, each handling one
domain end to end. Generation is handled by a LangGraph agent backed by Claude. Jina
Embeddings and a local Qdrant instance handle semantic retrieval so that document
generation pulls only the most relevant parts of your profile for any given role rather
than sending everything you have ever done. All generation streams to the client in real
time so you see output as it arrives rather than staring at a blank screen.

For a full technical breakdown of the architecture, the data model, the agent design,
the streaming pattern, and the engineering decisions behind the system, see
[docs/architecture.md](docs/architecture.md).

---

## Who it is for

Prepwise is designed for one user at a time. It is a personal tool, not a platform. You
run it for yourself. Your profile, your roadmap, your applications, your documents. The
architecture reflects this: there is no multi-tenancy, no social layer, no marketplace.
Just the cleanest possible system for getting one person hired.

The codebase is open source. If you want to run it for yourself, fork it, adapt the
profile structure to your background, and use it as your own operating system for the
search. If you want to extend it into something multi-user, the layer separation makes
that tractable.

---

## Stack

Python, FastAPI, LangGraph, LangChain, Anthropic Claude, Jina Embeddings, Qdrant,
PostgreSQL, Next.js, TailwindCSS.

Full stack and dependency details are in [docs/architecture.md](docs/architecture.md).

---

## Status

Active development. Backend complete. Frontend in progress.

---

## License

MIT