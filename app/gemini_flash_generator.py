"""
gemini_flash_generator.py
Uses Gemini Flash for a quick, lightweight nutrition/recovery tip.
"""

import os

from google import genai

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

MODEL_NAME = "gemini-2.5-flash"

PROMPT_TEMPLATE = """
Give one short, practical nutrition and recovery tip (2-3 sentences max) for a
client whose fitness goal is "{fitness_goal}" and whose workout intensity is
"{workout_intensity}". Plain text only, no headings, no markdown.
"""


def generate_nutrition_tip(fitness_goal: str, workout_intensity: str) -> str:
    prompt = PROMPT_TEMPLATE.format(fitness_goal=fitness_goal, workout_intensity=workout_intensity)

    if client is None:
        return _fallback_tip(fitness_goal)

    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return response.text.strip()
    except Exception:
        return _fallback_tip(fitness_goal)


def _fallback_tip(fitness_goal: str) -> str:
    tips = {
        "Weight Loss": "Keep protein high and maintain a modest calorie deficit. "
                        "Prioritize 7-8 hours of sleep so recovery doesn't stall your progress.",
        "Muscle Gain": "Eat in a slight calorie surplus with 1.6-2.2g of protein per kg "
                        "bodyweight, and hydrate well around training sessions.",
        "General Wellness": "Focus on balanced meals with vegetables, lean protein, and "
                             "whole grains, and take at least one full rest day this week.",
    }
    return tips.get(fitness_goal, "Stay hydrated, eat balanced meals, and prioritize sleep for recovery.")
