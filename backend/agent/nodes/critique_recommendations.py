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

"""
Node: critique_recommendations
Generator-critic judge. Reviews the 3 recommendations the stylist agent
just finalized against three criteria:
1. Distinctness — are the 3 styles genuinely different in character?
2. Constraint fit — do they match the analysis formality, and do their
   key_pieces cover all needed_items categories?
3. History balance — if the user has liked history, do the styles
   reflect it WITHOUT all being clones of it?
Returns critique_passed, critique_feedback (what to fix, for the retry),
and increments critique_retry_count (counts how many times the critique
has run — the graph's routing caps regeneration at one retry).
"""
def run(state: dict) -> dict:
    recommendations = state["recommendations"]
    analysis = state["analysis"]
    retrieved_history = state.get("retrieved_history", [])
    retry_count = state.get("critique_retry_count", 0)

    # history criterion only applies when history exists
    if retrieved_history:
        history_section = f"""
    The user's liked history that was provided to the generator:
    {json.dumps(retrieved_history, indent=2)}

    3. History balance: the styles should lean toward the aesthetics the
       user has liked, but NOT all three should be near-copies of past
       likes — at least one should offer appropriate variety.
    """
    else:
        history_section = """
    3. History balance: the user has no liked history — skip this
       criterion and judge it as passing.
    """

    prompt = f"""
    You are reviewing outfit recommendations before they are shown to a
    user. Judge them strictly against the criteria below.

    Occasion analysis the recommendations must fit:
    {json.dumps(analysis, indent=2)}

    The 3 recommendations to review:
    {json.dumps(recommendations, indent=2)}

    Criteria:
    1. Distinctness: are the 3 styles genuinely different in character
       (e.g. classic vs modern vs relaxed)? Fail if two or more are
       near-identical in aesthetic, key pieces, or description.
    2. Constraint fit: does each style match the analysis "formality",
       and do each style's key_pieces_categorized cover ALL categories
       listed in "needed_items"? Fail if any needed category has no
       pieces or a style is clearly the wrong formality.
    {history_section}

    Respond with only a JSON object:
    {{
        "critique_passed": true,
        "critique_feedback": null
    }}

    - "critique_passed" must be a JSON boolean (true or false).
    - If any criterion fails, set "critique_passed" to false and set
      "critique_feedback" to 1-2 concise sentences naming exactly what
      failed and how to fix it (e.g. "Styles 1 and 2 are nearly
      identical smart-casual looks — replace one with a clearly more
      formal or more relaxed direction. Style 3 is missing shoes from
      key_pieces.").
    - If all criteria pass, "critique_feedback" must be null.
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
        raise ValueError(f"No JSON object found in critique response: {text[:200]}")
    result = json.loads(match.group())

    return {
        "critique_passed": result["critique_passed"],
        "critique_feedback": result.get("critique_feedback"),
        "critique_retry_count": retry_count + 1,
    }