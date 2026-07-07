JOB_SCORING_PROMPT = """
You are scoring a job listing against a candidate's profile to determine fit.

Candidate profile summary:
{profile_summary}

Job listing:
Title: {title}
Company: {company}
Description: {snippet}

Score this job from 0 to 100 based on how well the candidate's skills and experience
match what this role appears to need. Consider the role title, visible tech stack,
and seniority signals in the description.

Return ONLY a JSON object in this exact format with no other text:
{{
  "fit_score": <integer 0-100>,
  "fit_reason": "<one sentence explaining the score>"
}}
"""


JD_ANALYSIS_PROMPT = """
Analyze this job description and extract the following in plain structured text.
Use these exact labels on separate lines:

required_skills: <comma separated list>
nice_to_have_skills: <comma separated list>
seniority_level: <junior | mid | senior | staff>
role_type: <what kind of engineer they are looking for>
domain: <industry or product domain>
ats_keywords: <comma separated keywords to include in resume>
cultural_signals: <one sentence on tone and culture from the JD>

Job description:
{jd_text}
"""