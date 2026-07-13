import os
from qdrant_client.models import Filter, FieldCondition, MatchValue
from services.qdrant import client, LIKED_OUTFITS
from services.mongo import liked_outfits
from services.embed import embed_texts

# configurable via .env — was hardcoded, which silently ignored the env var
CACHE_THRESHOLD = float(os.getenv("CACHE_THRESHOLD", "0.90"))

"""
Semantic cache lookup for a previously liked outfit.

Embeds the incoming occasion and searches the user's liked_outfits in Qdrant
for the single closest match. If that match's similarity score meets or exceeds
CACHE_THRESHOLD (0.95), the occasion is considered essentially identical to one
the user already liked, so the full stored record (including the try-on image)
is fetched from MongoDB and returned — letting the caller skip the agent and
image generation entirely. Returns None on a cache miss.

@param occasion: the user's occasion text for the new request
@param user_id: the user whose liked outfits to search (scopes the vector search)
@return: the full MongoDB liked-outfit record on a cache hit, or None on a miss
"""
def check_cache(occasion: str, user_id: str):
    # embed occasion
    vector = embed_texts([occasion])[0]

    # semantic search in Qdrant (query_points replaces search in qdrant-client >= 1.9)
    result = client.query_points(
        collection_name=LIKED_OUTFITS,
        query=vector,
        query_filter=Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        ),
        limit=1,
    )
    hits = result.points  # list of ScoredPoint, each has .id and .score

    # compare score with threshold
    if hits and hits[0].score >= CACHE_THRESHOLD:
        # cache hit and retrieve image from mongo by id
        mongo_id = hits[0].id
        record = liked_outfits.find_one({"_id": mongo_id})
        return record

    # cache miss
    return None


