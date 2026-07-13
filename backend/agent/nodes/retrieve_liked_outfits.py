import os
from qdrant_client.models import Filter, FieldCondition, MatchValue
from services.qdrant import client, LIKED_OUTFITS
from services.mongo import liked_outfits
from services.embed import embed_text

# loose threshold for preference grounding (vs 0.95 for the cache)
GROUNDING_THRESHOLD = float(os.getenv("GROUNDING_THRESHOLD", "0.75"))

'''
Node: retrieve_liked_outfits
RAG grounding retrieval. Embeds the occasion's style_direction and
searches the user's liked outfits in Qdrant at a loose threshold (~0.75).
For each sufficiently similar hit, fetches the full record from MongoDB
(two-store pattern: Qdrant decides relevance, MongoDB serves the data).
Returns {"retrieved_history": [...]} — empty list when the user has no
relevant history, so reason_outfit degrades gracefully to cold-start mode.
'''
def run(state: dict) -> dict:
    user_id = state.get("user_id", os.getenv("DEFAULT_USER_ID", "local-user"))
    style_direction = state["analysis"]["style_direction"]

    # embed the aesthetic description as the search query —
    # same vocabulary space as the stored (occasion + style_name) vectors
    vector = embed_text(style_direction)

    # search only this user's liked outfits
    # (query_points replaces search in qdrant-client >= 1.9)
    hits = client.query_points(
        collection_name=LIKED_OUTFITS,
        query=vector,
        query_filter=Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        ),
        limit=3,
    ).points

    # keep only hits above the grounding threshold,
    # and fetch each one's full record from MongoDB by shared id
    history = []
    for hit in hits:
        if hit.score < GROUNDING_THRESHOLD:
            continue
        record = liked_outfits.find_one({"_id": hit.id})
        if record:
            history.append({
                "occasion": record["occasion"],
                "style": record["style"],   # style_name, description, key_pieces, reasoning
            })

    return {"retrieved_history": history}