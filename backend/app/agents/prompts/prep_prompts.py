ROADMAP_GENERATION_PROMPT = """
You are generating a comprehensive interview preparation roadmap based entirely on the
master profile provided in your system context.

Infer everything about the candidate from the profile alone. Do not assume their
discipline, seniority, or domain. Let the profile define the roadmap structure entirely.

Generate a structured roadmap as a JSON array of subjects. Each subject must have topics.
Return ONLY valid JSON with no other text, no markdown, no code fences.

Format:
[
  {{
    "name": "Subject name",
    "description": "One sentence describing what this subject covers",
    "order_index": 0,
    "topics": [
      {{
        "name": "Topic name",
        "description": "One sentence describing what this topic covers",
        "order_index": 0
      }}
    ]
  }}
]

Rules:
- Group related technologies and concepts into coherent subjects
- Each subject should have 3 to 7 topics
- Order topics from fundamentals to advanced
- Base subjects strictly on what is in the profile
- Do not invent skills, technologies, or domains not present in the profile
- Generate between 8 and 14 subjects total
"""


SUBTOPIC_GENERATION_PROMPT = """
You are generating subtopics for an interview preparation topic.

Subject: {subject_name}
Topic: {topic_name}

The candidate's relevant profile context:
{profile_text}

Generate subtopics for this topic as a JSON array.
Return ONLY valid JSON with no other text, no markdown, no code fences.

Format:
[
  {{
    "name": "Subtopic name",
    "concept": "Clear explanation of this concept in 3-5 sentences. Be technically precise.",
    "project_evidence": "Specific evidence from the candidate's profile showing how they
    have used or applied this concept in real projects. Reference actual project names,
    metrics, and decisions. If no direct evidence exists, state that clearly.",
    "order_index": 0
  }}
]

Rules:
- Generate 3 to 6 subtopics per topic
- Concept explanations must be technically accurate and interview-ready
- Project evidence must be grounded in what is actually in the profile
- Never fabricate project evidence
- Order from foundational to advanced
"""


QUESTION_GENERATION_PROMPT = """
You are generating interview questions for a specific subtopic.

Subtopic: {subtopic_name}

Concept:
{concept}

Candidate's project evidence for this subtopic:
{project_evidence}

Generate interview questions as a JSON array.
Return ONLY valid JSON with no other text, no markdown, no code fences.

Format:
[
  {{
    "type": "theoretical",
    "question": "The interview question",
    "answer": "A strong, complete answer the candidate would give based on their
    experience. Be specific, use correct terminology, explain the why not just
    the what.",
    "order_index": 0
  }}
]

Rules:
- Generate 3 theoretical questions and 2 practical questions
- Theoretical questions test understanding of concepts, tradeoffs, and design decisions
- Practical questions are scenario-based and reference the candidate's actual project
  evidence where possible
- Answers must be strong enough to impress a senior interviewer
- Practical question answers must reference the candidate's real work
- Do not generate generic textbook questions -- make them sharp and interview-realistic
"""


INTERVIEW_SESSION_SYSTEM = """
You are conducting a technical interview session. Your role is to ask follow-up questions
that probe deeper into the candidate's understanding based on their previous answers.

Subtopic being tested: {subtopic_name}

Concept context:
{concept}

Rules:
- Ask exactly one follow-up question per turn
- Build on what the candidate just said -- probe their reasoning, challenge their
  decisions, or explore an edge case they did not mention
- If their answer was strong, push into more advanced territory
- If their answer was weak, redirect to a more fundamental aspect
- Never repeat a question already asked in this session
- Keep questions sharp and realistic -- mirror how a senior interviewer would probe
- Do not give feedback or evaluate the answer -- only ask the next question
"""


PREP_PATH_ANALYSIS_PROMPT = """
Analyze this job description against the candidate's profile in your system context
and produce a structured prep path.

Job description:
{jd_text}

Return ONLY valid JSON with no other text, no markdown, no code fences.

Format:
{{
  "strong_matches": {{
    "skills": ["skill1", "skill2"],
    "talking_points": ["one sentence on how to articulate this match in an interview"]
  }},
  "needs_sharpening": {{
    "skills": ["skill1"],
    "reason": "one sentence per skill on why it needs sharpening for this specific role"
  }},
  "gaps": {{
    "skills": ["skill1"],
    "mitigation": "one sentence on how to handle this gap honestly in an interview"
  }},
  "likely_angles": [
    "Predicted interview question area based on JD language and role type"
  ],
  "job_subject": {{
    "name": "Subject name specific to this role and company domain",
    "description": "One sentence on why this subject is critical for this specific role",
    "topics": [
      {{
        "name": "Topic name",
        "description": "One sentence on what to prepare for this interview",
        "order_index": 0
      }}
    ]
  }}
}}

Rules:
- strong_matches must only include skills clearly evidenced in the profile
- needs_sharpening is for skills the candidate has but needs to go deeper for this role
- gaps must be honest -- do not pretend skills exist that do not
- likely_angles should read as actual interview questions a hiring manager would ask
- job_subject must be specific to this company and role -- not generic
- job_subject topics should be 3 to 6 items that would directly prepare for this interview
"""