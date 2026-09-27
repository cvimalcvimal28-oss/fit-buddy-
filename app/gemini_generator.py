"""Generate a structured 7-day workout plan with Gemini."""

import os
import json

from google import genai
from google.genai import types

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

MODEL_NAME = "gemini-2.5-pro"

PROMPT_TEMPLATE = """
You are a certified strength and conditioning coach. Build a personalized 7-day
workout plan for the client below. Respond with ONLY valid JSON, no markdown
fences, no commentary, matching exactly this shape:

{{
  "days": [
    {{
      "day": "Day 1",
      "focus": "short label, e.g. Full Body / Rest / Cardio",
      "warm_up": "1-2 sentences",
      "main_workout": ["exercise 1 - sets x reps", "exercise 2 - sets x reps", "..."],
      "cooldown": "1-2 sentences"
    }}
  ]
}}

Include exactly 7 entries in "days", covering Day 1 through Day 7, with at
least one lighter recovery day if the intensity is Low or Medium.

Client profile:
- Name: {name}
- Age: {age}
- Weight: {weight} kg
- Fitness Goal: {fitness_goal}
- Workout Intensity: {workout_intensity}
"""


def generate_workout_plan(name: str, age: int, weight: int, fitness_goal: str, workout_intensity: str) -> dict:
    """
    Calls Gemini and returns a parsed dict: {"days": [...]}.
    Falls back to a safe default plan if the API key is missing or the call fails,
    so the app remains demonstrable without live credentials.
    """
    prompt = PROMPT_TEMPLATE.format(
        name=name, age=age, weight=weight,
        fitness_goal=fitness_goal, workout_intensity=workout_intensity,
    )

    if client is None:
        return _fallback_plan(fitness_goal)

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
        return _fallback_plan(fitness_goal)


def _fallback_plan(fitness_goal: str) -> dict:
    """A minimal offline plan used when Gemini is unavailable."""
    days = []
    focuses = ["Full Body", "Cardio", "Upper Body", "Rest & Mobility",
               "Lower Body", "Core & Conditioning", "Active Recovery"]
    for i, focus in enumerate(focuses, start=1):
        days.append({
            "day": f"Day {i}",
            "focus": focus,
            "warm_up": "5-10 minutes light cardio and dynamic stretching.",
            "main_workout": [
                f"Session aligned to goal: {fitness_goal}",
                "Bodyweight squats - 3 x 15",
                "Push-ups - 3 x 12",
                "Plank - 3 x 30 sec",
            ] if focus not in ("Rest & Mobility", "Active Recovery") else [
                "Light walk - 20-30 minutes",
                "Full-body stretching routine",
            ],
            "cooldown": "5 minutes static stretching and deep breathing.",
        })
    return {"days": days}
