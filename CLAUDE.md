# AI Stylist Agent — Project Context for Claude

This file lives in the project root. Paste its contents at the start of any new Claude conversation.

---

## What this project is

A full-stack web app: a personal AI wardrobe consultant. User inputs an occasion → a LangGraph agent generates 3 personalized outfit recommendations → user picks a style → shoppable garments are fetched from Google Shopping (virtual closet as a second source, later) → user picks garments → uploads a body photo → try-on: IDM-VTON (image-conditioned) when a top garment image exists, instruct-pix2pix (text-driven) as fallback → user likes (stored) or dislikes (re-pick).

**Current status:** Agent rebuilt (4 nodes, 2 conditional edges). Semantic cache + clarification gate + style-preference selector live. Shopping fetch + GarmentPickerPage built. IDM-VTON standalone proof PASSED. **Next: wire IDM-VTON into /tryon (services/tryon_vton.py + routing), then chained top+bottom VTON, then the virtual closet.**

---

## Architecture principles (READ FIRST — these encode deliberate decisions)

1. **No web search in the recommendation agent.** search_styles / evaluate_results / search retry loop were REMOVED deliberately. The LLM knows styling; the web's value is sourcing real garments AFTER style selection. Do not reintroduce.
2. **RAG = private user data only.** No generic style-knowledge corpus. Two stores: liked_outfits (built), closet_items (later).
3. **liked_outfits: ONE store, TWO thresholds.** ≥0.95 (CACHE_THRESHOLD) = semantic cache, route-level, returns stored try-on as an inline suggestion the user confirms. ~0.75 (GROUNDING_THRESHOLD) = preference grounding via retrieve_liked_outfits node. Dislikes NOT stored — dislike navigates back to StylePickerPage with the same recommendations.
4. **Agentic value at the boundaries:** input clarification gate + output generator-critic loop (max 1 regeneration). Critique double-fail = silent degrade (DELIBERATE: ship the 2nd attempt, no UI hint — soft quality issues beat erroring after two good generations).
5. **Two-store pattern:** shared uuid4 string is Mongo _id AND Qdrant point id (Mongo ObjectId is invalid as a Qdrant id). Qdrant payload minimal: {user_id} only; fetch Mongo via hit.id.
6. **Cache vector is occasion-dominant** (embed occasion + style_name at write; embed occasion-only at cache query). The cache is a user-confirmed SUGGESTION, so imperfect matching is fine.
7. **key_pieces_categorized is the source of truth** for garment categories: reason_outfit emits `{"top": [...], "bottom": [...], "shoes": [...]}` (exactly these keys; outerwear/accessories under top). Flat `key_pieces` is DERIVED in code after parsing to preserve the existing contract (StyleCard, gemini.py, critique). categorize_key_pieces() keyword rules remain ONLY as endpoint fallback.
8. **Try-on honesty + routing:** pix2pix is instruction-driven (cannot take garment images). IDM-VTON = image-conditioned, via duplicated HF ZeroGPU Space + gradio_client (standard HF Inference API does NOT serve it). Routing: garments.top.image_url present → IDM-VTON; absent OR IDM-VTON raises → pix2pix. IDM-VTON supports upper_body/lower_body/dresses — SHOES ARE NOT A CATEGORY (display-only). Full-body = sequential chained calls (top, then bottom on the result); if chain step 2 fails, return step 1's result.
9. **Shopping is an enhancement layer:** empty categories are VALID (never raise), per-category try/except, all-empty still returns the structure, picker gates Continue on non-empty categories only, error path still offers "continue without products."

---

## The agent (current — 4 nodes, 2 conditional edges, 1 loop)

```
START → analyze_occasion (Flash; ONE call does clarity judgment + analysis;
   │     nested JSON {occasion_clear, clarification_question, analysis})
   ├─ route_after_analyze: occasion_clear? no → END
   ↓
retrieve_liked_outfits (embed style_direction → Qdrant liked_outfits,
   │     user_id filter, limit=3, keep ≥ GROUNDING_THRESHOLD, fetch Mongo
   │     per hit.id, return [{occasion, style}] — trimmed, no tryon_image)
   ↓
reason_outfit (Flash; history soft-signal block: occasion-appropriateness
   │     first, preference tiebreaker, keep variety; conditional
   │     critique_feedback block on retry; emits key_pieces_categorized,
   │     derives flat key_pieces in code)
   ↓
critique_recommendations (Flash judge: distinctness, constraint fit vs
   │     formality/needed_items, history-balance — passes if no history;
   │     returns critique_passed, critique_feedback, critique_retry_count+1;
   │     COUNTS CRITIQUE RUNS: 1 after first, 2 after retry's critique)
   ├─ route_after_critique: passed OR critique_retry_count ≥ 2 → END
   └─ else → reason_outfit (feedback injected)
```

AgentState (total=False): occasion, style_preference, user_id, analysis{formality, style_direction, needed_items}, occasion_clear, clarification_question, retrieved_history, recommendations, critique_passed, critique_feedback, critique_retry_count.

Invoke with INPUTS ONLY: `{occasion, style_preference, user_id}` — no counter seeding (nodes use .get defaults).

Watch: Flash critique may over-fail; if >half of first attempts fail, soften "strictly" → "fairly" in the judge prompt.

---

## /api/styles — three response shapes

```json
{ "occasion": "...", "cached": true,  "outfit": { "style": {...}, "tryon_image": "..." } }
{ "cached": false, "needs_clarification": true, "question": "..." }
{ "occasion": "...", "cached": false, "recommendations": [ {style_name, description, key_pieces, key_pieces_categorized, reasoning} x3 ] }
```
Request: `{ occasion, style_preference?, skip_cache? }`. Branch order in frontend: needs_clarification FIRST, then cached, then recommendations.

---

## Other endpoints

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | /api/upload | multipart file | uuid-named file to uploads/, returns {filename, filepath} |
| POST | /api/tryon | { style, occasion, filepath, garments? } | NEXT: route on garments.top → IDM-VTON else pix2pix; deletes temp file in finally; returns {image} base64 |
| POST | /api/tryon/like | { occasion, style, tryon_image } | two-store write: Mongo insert → embed(occasion + style_name + description) → Qdrant upsert (shared uuid) |
| POST | /api/styles/garments | { occasion, style } | prefers key_pieces_categorized, keyword fallback; query = f"{pieces[0]} {occasion}"; 3 SerpAPI calls/flow; per-category try/except → [] |

SerpAPI free tier = 100 searches/month ≈ 33 flows. Product fields: title, image_url (thumbnail), product_link — NO price (deliberate).

---

## Frontend flow & pages

```
OccasionPage (input + style-preference pills [womenswear/menswear/no preference],
   localStorage-persisted; handles 3 response shapes: clarification banner
   #F0E6D8/#B8875B left-border, cache Option A card w/ 64px thumbnail +
   Generate new/View liked look, or navigate)
→ StylePickerPage (3 cards, fade-on-select, navigates to /garments with
   {selectedStyle, occasion, recommendations})
→ GarmentPickerPage (fetch on mount, Object.entries render — handles any
   categories, select 1/category by title identity, click-again deselects,
   empty category = quiet note, Continue gated on non-empty categories,
   error path offers continue-without-products)
→ UploadPage (relays selectedGarments; shows garment thumbnails preview;
   guard checks selectedStyle only — garments optional)
→ TryOnPage (fromCache branch: setImage + skip generation, buttons =
   Generate new recommendations + Back to home; normal branch: Dislike →
   /styles with {occasion, recommendations}, Like → liked ✓ state + POST
   /tryon/like; NEXT: send garments in /tryon POST, honest loading copy
   "can take a minute or two" for VTON)
```

State relay chain: recommendations + selectedGarments thread through every navigate.

---

## Tech stack & environment

Python 3.11, FastAPI :8001, React 18/Vite :5173, Tailwind v4 (no config), Qdrant Docker :6333 (3072-dim cosine, gemini-embedding-001), MongoDB Docker :27017 (PyMongo, db ai_stylist), google-genai SDK (`from google import genai`), LangGraph, SerpAPI (google-search-results pkg), gradio_client + duplicated IDM-VTON ZeroGPU Space, timbrooks/instruct-pix2pix (working try-on v1; gemini.py model string "gemini-3.1-flash-image" — user-confirmed working).

.env (project root): GEMINI_API_KEY, EMBEDDING_MODEL=gemini-embedding-001, QDRANT_URL, MONGODB_URI, CACHE_THRESHOLD=0.95, GROUNDING_THRESHOLD=0.75, DEFAULT_USER_ID=local-user, SERPAPI_KEY, HF_TOKEN.

docker-compose.yml (root): qdrant (qdrant_data volume) + mongodb (mongo:7, mongo_data volume). Stray-container lesson: if a port won't bind, check `docker ps -a` for an old container holding it.

Services: cache.py (check_cache → record|None), embed.py (embed_text, embed_texts), qdrant.py (ensure_collections on startup), mongo.py (verify_connection on startup), shopping.py (search_garment — [] is valid, categorize_key_pieces fallback), gemini.py (generate_tryon_image only), tryon_vton.py (NEXT: idm_vton_tryon(person_filepath, garment_image_url) → base64; module-level Client; download garment image if Space rejects URLs; raise on failure for route fallback).

---

## Build queue (in order)

1. **IDM-VTON wiring** （Done） — services/tryon_vton.py; TryOnRequest.garments: dict|None; route: top.image_url → VTON, except/else → pix2pix; TryOnPage sends garments + loading copy. Test 3 paths: VTON success, no-top → pix2pix, Space paused → graceful fallback.
2. **Chained full-body VTON**（Done）— extend standalone script first (feed step-1 output + bottom image); expect compounding artifacts ~20-30%, 2-4 min total; if chain step 2 fails return step 1 result; progressive UI ("top fitted — now fitting bottom…") optional.
3. **Virtual closet** — per-garment upload → SegFormer (mattmdjaga/segformer_b2_clothes) isolate → Gemini Vision tag (type/color/formality/season) → embed rich description → Mongo + Qdrant closet_items. retrieve_closet = post-selection per-category semantic search (NOT an agent node), feeds GarmentPickerPage alongside shopping. CAUTION: SegFormer is trained on worn clothing — may fail on flat product-style photos; may need background removal instead, or nothing.
4. Later: S3 (only tryon_image field changes), auth (Phase E), multi-garment compositing beyond top+bottom.

---

## Design system

Page #F7F0E8, sections #D8C3A5, cards #FFFAF3, primary text #3B2F2F, secondary #7A5E5E, tag bg #F0E6D8, tag text #5A3E2B, button #B8875B, hover #8A5A3B, button text #FFFAF3. Flat, no shadows, rounded-2xl.

---

## Interview story (keep consistent)

"A LangGraph agent that validates its input (clarification gate) and critiques its own output (generator-critic, one retry). Recommendations are personalized by RAG over the user's liked-outfit history — one vector store read at two thresholds: strict for a semantic cache that skips regeneration entirely (served as a user-confirmed suggestion), loose for preference grounding. After the user picks a style, garments are sourced live from Google Shopping (closet as second source coming), and tried on with IDM-VTON — image-conditioned, so the actual product transfers — falling back to instruction-driven pix2pix when no garment image exists. I deliberately removed web search from recommendation generation: the LLM already knows styling; the web earns its place sourcing real, current garments."