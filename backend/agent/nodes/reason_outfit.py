import os
import json
import re
from google import genai
from google.genai import types
from shared.retry import generate_with_retry

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

"""
Node: reason_outfit
Generates 3 distinct outfit recommendations from the occasion analysis,
personalized by the user's liked-outfit history as a SOFT signal
(occasion-appropriateness first, preference as tiebreaker, keep variety).
On a critique retry, the judge's feedback is injected so the regeneration
fixes what failed. Output JSON shape unchanged from Phase A.
"""
def run(state: dict) -> dict:
    # read inputs from state
    occasion = state["occasion"]
    analysis = state["analysis"]
    retrieved_history = state.get("retrieved_history", [])
    critique_feedback = state.get("critique_feedback")

    # ── history soft-signal block (replaces the old search-results block) ──
    # only included when relevant history exists; empty history = cold-start,
    # the prompt simply omits the block and Gemini works from analysis alone
    if retrieved_history:
        history_block = f"""
    The user has previously LIKED these outfits for similar occasions:
    {json.dumps(retrieved_history, indent=2)}

    Treat these as a soft preference signal, with this priority order:
    1. Occasion-appropriateness comes first — never sacrifice fit for
       the occasion's formality and context to match past preferences.
    2. Among appropriate options, lean toward the aesthetics, colors,
       and silhouettes the user has demonstrated they like.
    3. Keep variety — do not make all 3 styles clones of past likes;
       at least one style should offer something outside their history.
    """
    else:
        history_block = ""

    # ── critique feedback block (present only on the single retry) ──
    if critique_feedback:
        feedback_block = f"""
    Previous attempt feedback: {critique_feedback}
    Your previous set of recommendations failed review for the reason(s)
    above. Generate a corrected set of 3 styles that addresses this
    feedback while still following all other instructions.
    """
    else:
        feedback_block = ""

    prompt = f"""
    The user is attending: "{occasion}"

    Occasion analysis:
    {json.dumps(analysis, indent=2)}
    {history_block}{feedback_block}
    Using the analysis above{" and the user's preference history" if retrieved_history else ""},
    generate exactly 3 distinct outfit styles suitable for this occasion.
    Each style should be distinct in character (e.g. classic, modern,
    smart casual) while staying consistent with the formality level and
    style direction from the analysis.

    Respond with only a JSON array of 3 objects in the following format:
    [
        {{
            "style_name": "Business Casual",
            "description": "A relaxed yet polished aesthetic with clean lines and neutral tones — structured-but-soft layers, minimal accessories, and footwear that bridges casual and professional.",
            "key_pieces": ["navy blazer", "white dress shirt", "grey trousers", "oxford shoes"],
            "reasoning": "This style conveys authority and professionalism."
        }},
        {{
            "style_name": "...",
            "description": "...",
            "key_pieces": ["..."],
            "reasoning": "..."
        }},
        {{
            "style_name": "...",
            "description": "...",
            "key_pieces": ["..."],
            "reasoning": "..."
        }}
    ]

    - "style_name" should be a short label for the style (e.g. "Business
      Casual", "Modern Minimalist", "Smart Casual").
    - "description" should be a 2-3 sentence description of the aesthetic.
    - "key_pieces" should be a list of specific garment items that
      together cover all categories in "needed_items" from the analysis.
    - "reasoning" should be one concise sentence explaining why this
      style suits the occasion.
    """

    response = generate_with_retry(
        client,
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    text = response.text.strip()
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in reason_outfit response: {text[:200]}")
    recommendations = json.loads(match.group())

    return {"recommendations": recommendations}