"""Generate general, safety-conscious nutrition chat replies with Gemini."""

import logging
import os

from google import genai

logger = logging.getLogger(__name__)
MODEL_NAME = "gemini-2.5-flash"
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY")) if os.getenv("GOOGLE_API_KEY") else None

SYSTEM_GUIDANCE = """You are FitBuddy's general healthy-eating assistant.
Give practical, friendly, non-judgmental food ideas and simple meal plans.
This is general education, not medical advice. Keep each response under 180 words.
Do not diagnose conditions,
prescribe diets, recommend fasting, supplements, calorie targets, weight-loss
rates, or restrictive eating. Never encourage skipping meals or cutting out
whole food groups. For minors, pregnancy, eating-disorder concerns, allergies,
or medical conditions (including diabetes or kidney disease), recommend a
qualified clinician or registered dietitian and keep guidance broad. Ask about
allergies before suggesting specific foods if unknown. Mention that users
should adapt portions to appetite, culture, access, and personal needs.
Keep replies concise and offer a balanced sample meal/day only when requested.
Do not claim that the plan treats disease or guarantees results."""

FALLBACK_REPLY = (
    "I can't reach the AI planner right now, but I can still help with a general "
    "starting point: build meals around a food you enjoy, add a source of protein "
    "and fruit or vegetables when available, and drink to thirst. Tell me your "
    "food preferences or dietary pattern and I can suggest a simple balanced meal "
    "idea. For medical needs or allergies, check with a qualified clinician or "
    "registered dietitian."
)


def generate_diet_reply(history: list[tuple[str, str]]) -> tuple[str, bool]:
    """Return a chat response and whether Gemini supplied it."""
    if not client:
        return FALLBACK_REPLY, False

    conversation = "\n".join(
        f"{'Member' if role == 'user' else 'FitBuddy'}: {content}"
        for role, content in history[-12:]
    )
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=f"{SYSTEM_GUIDANCE}\n\nConversation:\n{conversation}\n\nFitBuddy:",
        )
        text = (response.text or "").strip()
        return (text, True) if text else (FALLBACK_REPLY, False)
    except Exception:
        logger.exception("Gemini diet chat reply failed")
        return FALLBACK_REPLY, False
