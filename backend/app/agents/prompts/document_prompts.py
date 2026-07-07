JD_ANALYSIS_PROMPT = """
Analyze the job description below and extract the following.
Use these exact labels on separate lines. Do not add any other text.

required_skills: <comma separated list>
nice_to_have_skills: <comma separated list>
seniority_level: <junior | mid | senior | staff>
role_type: <concise description of the type of engineer they want>
domain: <industry or product domain>
ats_keywords: <comma separated keywords critical for ATS matching>
cultural_signals: <one sentence describing tone and culture from the JD>

Job description:
{jd_text}
"""


RESUME_GENERATION_PROMPT = """
You are generating a targeted resume for the candidate based on the job description
analysis and the most relevant sections of their profile retrieved below.

Job description analysis:
{jd_analysis}

Relevant profile sections:
{retrieved_chunks}

Generate the resume content as plain structured text using ONLY these exact labels.
Each label must appear on its own line followed by a colon and the content.
Do not use markdown, bullet symbols, bold, or any formatting characters.

profile_summary: <3-4 sentence summary tailored to this role using JD language>

experience_1_title: <job title>
experience_1_company: <company name>
experience_1_period: <period>
experience_1_bullet_1: <strong achievement bullet, metrics where possible>
experience_1_bullet_2: <strong achievement bullet>
experience_1_bullet_3: <strong achievement bullet>

Repeat experience blocks for each role, incrementing the number.

project_1_name: <project name>
project_1_description: <2-3 sentence description grounded in real metrics, tailored to JD>
project_1_stack: <tech stack comma separated>

Repeat project blocks for the most relevant projects only. Max 4 projects.
Prioritise projects whose stack overlaps most with the JD required skills.

skills: <grouped skills as plain text, most relevant to JD first>

education: <education entries as plain text>

certifications: <certifications as plain text, most relevant first>

Ground every bullet and description in the candidate's actual work.
Do not invent metrics, scale numbers, or technologies not present in the profile.
Use the exact ATS keywords from the JD analysis naturally within the content.
"""


COVER_LETTER_GENERATION_PROMPT = """
You are generating a cover letter for the candidate tailored to this specific role.

Job description analysis:
{jd_analysis}

Relevant profile sections:
{retrieved_chunks}

Generate the cover letter as plain structured text using ONLY these exact labels.
Each label must appear on its own line followed by a colon and the content.
Do not use markdown, bullet symbols, bold, or any formatting characters.
Write in a confident, direct, human tone. Not corporate. Not sycophantic.

opening_paragraph: <hook that names the role, immediately references the candidate's
strongest relevant project or achievement, and states why this role is the right fit>

body_paragraph_1: <deepest relevant technical proof point. Reference a specific project,
real metrics, and the specific technical decisions made. Connect directly to what the
JD is asking for>

body_paragraph_2: <second proof point covering a different angle, such as infrastructure,
scale, cross-functional impact, or a skill the JD emphasises that the first paragraph
did not cover. Keep it grounded in real work>

closing_paragraph: <confident close. No begging. State availability, express genuine
interest in what the company is building, and invite next steps>
"""