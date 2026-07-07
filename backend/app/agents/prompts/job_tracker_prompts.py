PATTERN_ANALYSIS_PROMPT = """
You are analyzing a candidate's job application history to identify patterns,
diagnose where in the hiring funnel they are losing, and provide specific
actionable recommendations.

Application data:
{application_data}

Return ONLY valid JSON with no other text, no markdown, no code fences.

Format:
{{
  "summary": "2-3 sentence honest assessment of the overall job search performance
  based strictly on the data provided",
  "funnel_stages": [
    {{
      "stage": "application_to_response",
      "drop_off_rate": 0.85,
      "observation": "one precise sentence on what the data shows at this stage"
    }},
    {{
      "stage": "response_to_interview",
      "drop_off_rate": 0.60,
      "observation": "one precise sentence on what the data shows at this stage"
    }},
    {{
      "stage": "interview_to_offer",
      "drop_off_rate": 0.90,
      "observation": "one precise sentence on what the data shows at this stage"
    }}
  ],
  "strongest_signal": "The single clearest positive signal in the data",
  "weakest_point": "The single most critical failure point to address",
  "recommendations": [
    "Specific, actionable recommendation grounded in the data -- not generic advice"
  ],
  "data_confidence": "low | medium | high -- based on how many applications are in
  the dataset. Low for under 10, medium for 10-30, high for 30+"
}}

Rules:
- Be honest and direct -- do not sugarcoat weak data
- Recommendations must be specific to what the data shows, not generic job search advice
- Drop off rates are decimals between 0 and 1 representing the proportion that did not
  advance to the next stage
- If data is insufficient for meaningful analysis, say so clearly in the summary
- Generate 3 to 5 recommendations
- Funnel stages must always include all three stages even if data is sparse
"""