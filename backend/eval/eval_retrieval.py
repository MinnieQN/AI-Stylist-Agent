"""
Eval: retrieval — validates the two liked_outfits read paths against seeded data.

What it tests:
1. Semantic cache (services/cache.check_cache, CACHE_THRESHOLD ~0.90):
   does a near-identical occasion hit, and an unrelated one miss?
2. Preference grounding (agent/tools._fetch_liked_history, GROUNDING_THRESHOLD 0.75):
   do related occasions retrieve history, and unrelated ones come back empty?

Design notes:
- Seeds MIRROR the production write path exactly (uuid shared id, embed text
  = f"{occasion} {style_name}", payload {user_id}) — otherwise we'd be
  evaluating a different system than the one that runs.
- Uses an isolated EVAL_USER so real local-user data is never touched, and
  cleans up BOTH stores in a finally block so failed runs can't leak points
  into the real cache.
- Prints the raw top similarity score per query: on boundary cases the
  number (e.g. 0.91 vs threshold 0.90) is the tuning finding, not the boolean.
- No LLM calls — embeddings only. The cheapest eval in the suite.

Run from backend/:  python -m eval.eval_retrieval
"""

from eval.common import load_cases, report
import os
import sys
import uuid
from datetime import datetime

from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from services.embed import embed_text
from services.qdrant import client as qdrant_client, LIKED_OUTFITS
from services.mongo import liked_outfits
from services.cache import check_cache
from agent.tools import _fetch_liked_history

EVAL_USER = "eval-user"

"""
Seed the eval outfits into both stores, mirroring the /tryon/like write path.
@param seeds: seed_outfits list from retrieval_cases.json
@return: dict of seed_id -> shared uuid (to verify WHICH record was retrieved)
"""
def seed_outfits(seeds: list[dict]) -> dict:
    seed_ids = {}
    for seed in seeds:
        shared_id = str(uuid.uuid4())
        seed_ids[seed["seed_id"]] = shared_id

        # Mongo: full record (empty image — retrieval never reads it here)
        liked_outfits.insert_one({
            "_id": shared_id,
            "user_id": EVAL_USER,
            "occasion": seed["occasion"],
            "style": seed["style"],
            "tryon_image": "",
            "created_at": datetime.utcnow(),
        })

        # Qdrant: occasion-ONLY vector — MUST match the like-write formula
        # (symmetric with the cache query; style_name suffix cost ~0.17
        # similarity and made the 0.90 cache threshold unreachable)
        vector = embed_text(seed["occasion"])
        qdrant_client.upsert(
            collection_name=LIKED_OUTFITS,
            points=[PointStruct(id=shared_id, vector=vector, payload={"user_id": EVAL_USER})],
        )
    return seed_ids


"""
Raw top similarity score for a query against the eval user's points,
with no threshold applied — for diagnostic printing on every case.
@return: (score, point_id) of the single closest point, or (None, None)
"""
def raw_top_score(query_occasion: str):
    vector = embed_text(query_occasion)
    hits = qdrant_client.query_points(
        collection_name=LIKED_OUTFITS,
        query=vector,
        query_filter=Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=EVAL_USER))]
        ),
        limit=1,
    ).points
    if not hits:
        return None, None
    return hits[0].score, hits[0].id


"""
Delete everything the eval seeded, from both stores.
Runs in finally — must never assume the run got far enough to seed.
"""
def cleanup():
    qdrant_client.delete(
        collection_name=LIKED_OUTFITS,
        points_selector=Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=EVAL_USER))]
        ),
    )
    liked_outfits.delete_many({"user_id": EVAL_USER})


def main():
    data = load_cases("retrieval_cases.json")
    results = []

    try:
        seed_ids = seed_outfits(data["seed_outfits"])
        id_to_seed = {v: k for k, v in seed_ids.items()}

        for q in data["queries"]:
            occasion = q["query_occasion"]

            # diagnostic: the raw number is the finding on boundary cases
            score, top_id = raw_top_score(occasion)
            closest = id_to_seed.get(top_id, "none")

            # 1. cache path — the exact function the route calls
            cached = check_cache(occasion, EVAL_USER)
            cache_hit = cached is not None
            cache_ok = cache_hit == q["expect_cache_hit"]

            # 2. grounding path — the exact tool implementation the agent calls
            grounding = _fetch_liked_history(occasion, {"user_id": EVAL_USER})
            grounding_hit = len(grounding["outfits"]) > 0
            grounding_ok = grounding_hit == q["expect_grounding_hit"]

            passed = cache_ok and grounding_ok
            results.append({
                "label": f"'{occasion}'",
                "passed": passed,
                "detail": {
                    "raw_top_score": f"{score:.4f} (closest: {closest})" if score is not None else "no hits",
                    "cache": f"hit={cache_hit} expected={q['expect_cache_hit']}",
                    "grounding": f"hit={grounding_hit} ({len(grounding['outfits'])} outfits) expected={q['expect_grounding_hit']}",
                    "note": q.get("note", ""),
                },
            })

    finally:
        cleanup()

    # print detail for EVERY case here (not just failures) — the raw scores
    # are the point of this eval, and passing boundary cases still inform tuning
    ok = report("Retrieval eval (cache + grounding thresholds)", results)
    print(f"\nThresholds under test: CACHE={os.getenv('CACHE_THRESHOLD', '0.90')} "
          f"GROUNDING={os.getenv('GROUNDING_THRESHOLD', '0.75')}")
    for r in results:
        if r["passed"]:
            print(f"  score detail [{r['label']}]: {r['detail']['raw_top_score']}")

    # ok is the summary dict — a truthiness check would always exit 0
    sys.exit(0 if ok["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
