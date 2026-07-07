PROFILE_ANALYSIS_PROMPT = """
You are analyzing the user's master profile to confirm it is well-structured
and contains enough detail for resume generation, interview prep, and job matching.

Profile content:
{profile_text}

Identify:
1. Any sections that are thin or missing key details
2. Projects that lack metrics or scale numbers
3. Skills listed without context of how they were used
4. Any gaps that would weaken resume or interview performance

Return your analysis as plain text with clear section labels.
Do not use markdown formatting or bullet symbols.
"""


PROFILE_SUMMARY_PROMPT = """
Based on the user's master profile, write a concise professional summary
in 3-4 sentences. Focus on their strongest lane, most impressive projects,
and what kind of role they are best positioned for.

Return plain text only. No labels, no formatting.
"""