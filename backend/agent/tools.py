import os
from google.genai import types
from qdrant_client.models import Filter, FieldCondition, MatchValue
from services.weather import get_weather
from services.embed import embed_text
from services.qdrant import client as qdrant_client, LIKED_OUTFITS
from services.mongo import liked_outfits

"""
Tool layer for the stylist agent loop.

Two kinds of tools:
- EXTERNAL tools (get_weather, fetch_liked_history): executed here via
  execute_tool(); their result goes back to the model as a function response.
- TERMINATOR tools (ask_clarification, finalize_recommendations): never
  executed here — the loop node intercepts them and turns their arguments
  into state updates that end the loop.
"""

# loose threshold for preference grounding (vs CACHE_THRESHOLD for the cache)
GROUNDING_THRESHOLD = float(os.getenv("GROUNDING_THRESHOLD", "0.75"))

# exact category contract for key_pieces_categorized
# anything else the model emits (outerwear, accessories...) folds under "top"
CATEGORY_KEYS = ["top", "bottom", "shoes"]


# tool declarations

GET_WEATHER = types.FunctionDeclaration(
    name="get_weather",
    description=(
        "Get the current weather for a city. Call this ONLY when the occasion "
        "is plausibly outdoors or weather-dependent AND a location is mentioned "
        "or clearly inferable from the occasion (e.g. 'rooftop party in Austin', "
        "'beach wedding in Miami'). Do NOT call it for indoor occasions "
        "('job interview at a bank', 'dinner at a restaurant') or when no "
        "location is given."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "city": types.Schema(
                type=types.Type.STRING,
                description="City name to fetch weather for, e.g. 'Chicago'",
            ),
        },
        required=["city"],
    ),
)

FETCH_LIKED_HISTORY = types.FunctionDeclaration(
    name="fetch_liked_history",
    description=(
        "Search the user's previously liked outfits for looks relevant to this "
        "occasion. Call this for normal styling requests to personalize "
        "recommendations. The query should be a short description of the "
        "occasion's aesthetic (e.g. 'relaxed daytime picnic casual'). "
        "Returns up to 3 past liked outfits; an empty list means no relevant "
        "history — proceed without it. Do not call more than once."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "query": types.Schema(
                type=types.Type.STRING,
                description="Short aesthetic description of the occasion to search with",
            ),
        },
        required=["query"],
    ),
)

ASK_CLARIFICATION = types.FunctionDeclaration(
    name="ask_clarification",
    description=(
        "End the conversation by asking the user ONE short, friendly question "
        "about their occasion. Call this ONLY when the input is not a clear, "
        "dressable occasion: gibberish, not an occasion at all, or too vague "
        "to determine formality. Calling this means NO recommendations are "
        "produced this turn."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "question": types.Schema(
                type=types.Type.STRING,
                description="One short question that would help the user specify their occasion",
            ),
        },
        required=["question"],
    ),
)

# nested schema for one recommendation, matching the existing style contract
_RECOMMENDATION_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "style_name": types.Schema(type=types.Type.STRING),
        "description": types.Schema(
            type=types.Type.STRING,
            description="2-3 sentence description of the overall look",
        ),
        "key_pieces_categorized": types.Schema(
            type=types.Type.OBJECT,
            description=(
                "Garments by category. Use EXACTLY the keys top, bottom, shoes. "
                "Outerwear and accessories go under top. A category may be an "
                "empty list (e.g. bottom for a dress look)."
            ),
            properties={
                "top": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "bottom": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "shoes": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
            },
            required=["top", "bottom", "shoes"],
        ),
        "reasoning": types.Schema(
            type=types.Type.STRING,
            description="One sentence on why this style fits the occasion",
        ),
    },
    required=["style_name", "description", "key_pieces_categorized", "reasoning"],
)

FINALIZE_RECOMMENDATIONS = types.FunctionDeclaration(
    name="finalize_recommendations",
    description=(
        "Submit the final 3 outfit recommendations and end the styling session. "
        "Call this exactly once, when you have enough context. The 3 styles "
        "must be clearly distinct from each other."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "analysis": types.Schema(
                type=types.Type.OBJECT,
                description="Your read of the occasion these recommendations were built for",
                properties={
                    "formality": types.Schema(
                        type=types.Type.STRING,
                        description="Short phrase, e.g. 'business casual', 'formal', 'very casual'",
                    ),
                    "style_direction": types.Schema(
                        type=types.Type.STRING,
                        description="2-3 sentence description of the overall aesthetic that fits this occasion",
                    ),
                    "needed_items": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description="Garment categories needed for this occasion, e.g. ['top', 'bottom', 'shoes']",
                    ),
                },
                required=["formality", "style_direction", "needed_items"],
            ),
            "recommendations": types.Schema(
                type=types.Type.ARRAY,
                description="Exactly 3 distinct outfit recommendations",
                items=_RECOMMENDATION_SCHEMA,
            ),
        },
        required=["analysis", "recommendations"],
    ),
)

TOOL_DECLARATIONS = [GET_WEATHER, FETCH_LIKED_HISTORY, ASK_CLARIFICATION, FINALIZE_RECOMMENDATIONS]

# the loop intercepts these instead of dispatching them
TERMINATOR_TOOLS = {"ask_clarification", "finalize_recommendations"}


# external tool implementations

"""
Search the user's liked outfits (two-store pattern: Qdrant decides
relevance at GROUNDING_THRESHOLD, MongoDB serves the data).
@param query: aesthetic description chosen by the model
@param state: agent state (for user_id scoping)
@return: {"outfits": [{occasion, style}], trimmed — no tryon_image}
"""
def _fetch_liked_history(query: str, state: dict) -> dict:
    user_id = state.get("user_id", os.getenv("DEFAULT_USER_ID", "local-user"))
    vector = embed_text(query)

    hits = qdrant_client.query_points(
        collection_name=LIKED_OUTFITS,
        query=vector,
        query_filter=Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        ),
        limit=3,
    ).points

    outfits = []
    for hit in hits:
        if hit.score < GROUNDING_THRESHOLD:
            continue
        record = liked_outfits.find_one({"_id": hit.id})
        if record:
            outfits.append({
                "occasion": record["occasion"],
                "style": record["style"],
            })
    return {"outfits": outfits}


"""
Execute an external (non-terminator) tool and return its result dict,
ready to wrap in types.Part.from_function_response. Raises on unknown
names and terminator names — the loop must intercept terminators first.
@param name: function call name from the model
@param args: function call args from the model
@param state: agent state (user scoping etc.)
@return: JSON-serializable result dict
"""
def execute_tool(name: str, args: dict, state: dict) -> dict:
    if name == "get_weather":
        return get_weather(args["city"])
    if name == "fetch_liked_history":
        return _fetch_liked_history(args["query"], state)
    raise ValueError(f"Unknown or non-dispatchable tool: {name}")


# finalize validation

"""
Validate and normalize the finalize_recommendations payload against the
existing style contract, and derive flat key_pieces in code (existing
convention — StyleCard, pix2pix.py and critique all read it).
Raises ValueError with a model-readable message so the loop can feed the
problem back as a function response and let the model retry.
@param recommendations: raw list from the finalize function call
@return: normalized list of exactly 3 recommendation dicts
"""
def validate_recommendations(recommendations) -> list[dict]:
    if not isinstance(recommendations, list) or len(recommendations) != 3:
        raise ValueError("recommendations must be a list of exactly 3 styles")

    normalized = []
    for rec in recommendations:
        for field in ("style_name", "description", "key_pieces_categorized", "reasoning"):
            if not rec.get(field):
                raise ValueError(f"recommendation missing required field: {field}")

        raw = rec["key_pieces_categorized"]
        categorized = {key: list(raw.get(key) or []) for key in CATEGORY_KEYS}
        # contract: exactly top/bottom/shoes — fold any extra category under top
        for key, pieces in raw.items():
            if key not in CATEGORY_KEYS and pieces:
                categorized["top"].extend(pieces)

        if not any(categorized.values()):
            raise ValueError(f"'{rec['style_name']}' has no key pieces in any category")

        normalized.append({
            "style_name": rec["style_name"],
            "description": rec["description"],
            "key_pieces_categorized": categorized,
            # flat key_pieces DERIVED here, preserving the existing contract
            "key_pieces": [p for key in CATEGORY_KEYS for p in categorized[key]],
            "reasoning": rec["reasoning"],
        })
    return normalized
