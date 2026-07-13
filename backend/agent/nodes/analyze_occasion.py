import os
import json
import re
from google import genai
from google.genai import types
from shared.retry import generate_with_retry

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# agent model — set GEMINI_MODEL in .env; the alias default tracks the latest
# stable Flash so a model retirement never hard-breaks the agent again
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

'''
Node: analyze_occasion
Reads state["occasion"] and makes two judgments in one Gemini call:
1. Is this a clear, dressable occasion at all? (occasion_clear)
   - If not, provides a clarification_question to show the user,
     and the graph routes to END without recommending.
2. If clear: break it down into structured attributes
   (formality, style_direction, needed_items) for later nodes.
Returns: {"analysis", "occasion_clear", "clarification_question"}
'''
def run(state: dict) -> dict:
    occasion = state["occasion"]

    prompt = f"""
    A user typed the following as an occasion they want outfit
    recommendations for: "{occasion}"
    Style preference: {state.get("style_preference", "no preference")}

    First, judge whether this is a clear, dressable occasion — a real
    event or situation a person could dress for (e.g. "job interview",
    "beach wedding", "casual dinner"). It is NOT clear if it is:
    - gibberish or random characters
    - not an occasion at all (e.g. a general question, a greeting)
    - too vague to determine formality (e.g. "something nice", "an event")

    Respond with only a JSON object in the following format:
    {{
        "occasion_clear": true,
        "clarification_question": null,
        "analysis": {{
            "formality": "business casual",
            "style_direction": "A relaxed yet polished aesthetic with clean lines and neutral tones — think structured-but-soft layers, minimal accessories, and footwear that bridges casual and professional. Avoid anything overly formal or athletic.",
            "needed_items": ["top", "bottom", "shoes"]
        }}
    }}

    - "occasion_clear" must be a JSON boolean (true or false).
    - If occasion_clear is false: set "clarification_question" to ONE
      short, friendly question that would help the user specify their
      occasion (e.g. "Could you tell me more about the event — what is
      it and how formal will it be?"), and set "analysis" to null.
    - If occasion_clear is true: set "clarification_question" to null
      and fill in "analysis" as follows:
      - "formality" should be a short phrase (e.g. "formal", "business
        casual", "smart casual", "athletic", "very casual").
      - "style_direction" should be a 2-3 sentence description of the
        overall aesthetic that fits this occasion — describe colors,
        silhouettes, and mood in language that could plausibly describe
        garments themselves.
      - "needed_items" should be a list of garment categories needed to
        complete an outfit for this occasion (e.g. ["top", "bottom",
        "shoes"], or include "outerwear" / "accessories" if relevant).
        Reflect the style preference above when deciding categories —
        if "no preference", suggest categories without assuming
        gendered clothing norms.
    """

    response = generate_with_retry(
        client,
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    text = response.text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in analyze_occasion response: {text[:200]}")
    result = json.loads(match.group())

    return {
        "occasion_clear": result["occasion_clear"],
        "clarification_question": result.get("clarification_question"),
        "analysis": result.get("analysis") or {},
    }