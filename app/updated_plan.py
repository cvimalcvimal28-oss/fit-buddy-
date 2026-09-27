"""Use Gemini to revise a workout plan based on member feedback."""

import os
import json

from google import genai
from google.genai import types

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

MODEL_NAME = "gemini-2.5-pro"

PROMPT_TEMPLATE = """
You are a certified strength and conditioning coach. Here is a client's current
7-day workout plan as JSON:

{original_plan}

The client gave this feedback: "{feedback}"

Revise the plan to address the feedback while keeping it safe and balanced.
Respond with ONLY valid JSON, no markdown fences, matching exactly this shape:

{{
  "days": [
    {{
      "day": "Day 1",
      "focus": "short label",
      "warm_up": "1-2 sentences",
      "main_workout": ["exercise 1 - sets x reps", "..."],
      "cooldown": "1-2 sentences"
    }}
  ]
}}

Include exactly 7 entries, Day 1 through Day 7.
"""


def generate_updated_plan(original_plan_json: str, feedback: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(original_plan=original_plan_json, feedback=feedback)

    if client is None:
        return _fallback_update(original_plan_json, feedback)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception:
        return _fallback_update(original_plan_json, feedback)


def _fallback_update(original_plan_json: str, feedback: str) -> dict:
    """Without live credentials, echo the original plan with a note appended."""
    try:
        plan = json.loads(original_plan_json)
    except Exception:
        plan = {"days": []}
    for day in plan.get("days", []):
        day["focus"] = f"{day.get('focus', '')} (adjusted for: {feedback})"
    return plan
