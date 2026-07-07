SEARCH_CONTEXT_PROMPT = """
Based on this candidate's profile, generate intelligent job search suggestions.

Return ONLY a JSON object in this exact format with no other text:
{{
  "suggested_titles": [
    {{
      "title": "<job title>",
      "reason": "<one sentence why this fits the candidate>",
      "seniority": "<junior | mid | senior>",
      "priority": <1-5 where 1 is highest priority>
    }}
  ],
  "recommended_keywords": ["<keyword1>", "<keyword2>"],
  "avoid_titles": ["<title that would be a mismatch>"],
  "strongest_lane": "<one sentence describing the candidate's primary strength lane>"
}}

Generate 5 to 7 suggested titles. Order by fit strength.
Base everything strictly on what is in the profile — do not invent skills or experience.
"""