# AI Stylist Agent — Project Context for Claude

This file lives in the project root. Paste its contents at the start of any new Claude conversation.

---

## What this project is

A full-stack web app: a personal AI wardrobe consultant. User inputs an occasion → a LangGraph agent generates 3 personalized outfit recommendations → user picks one → garments are sourced from the user's virtual closet OR fetched from Google Shopping → user uploads a body photo → an image-conditioned try-on model generates the try-on → user likes (stored) or dislikes (re-pick).

**Current status:** Phases A/B complete and reworked. Semantic cache built (route-level). Liked-outfit two-store ingestion built. instruct-pix2pix try-on working. **Next: rebuild the agent to the 5-node design, then garment sourcing (shopping fetch + closet), then IDM-VTON try-on.**

---

## Architecture principles (READ FIRST — these encode deliberate decisions)

1. **No web search in the recommendation agent.** `search_styles`, `evaluate_results`, and the search retry loop were REMOVED deliberately. The LLM already knows styling; the web's unique value is *current products*, used later for garment sourcing. Do not reintroduce search into the recommendation path.
2. **RAG = private user data only.** No generic style-knowledge corpus (the model knows generic styling). Two RAG uses: (a) `liked_outfits` store, (b) virtual closet garments.
3. **`liked_outfits` is ONE store with TWO read thresholds:** ≥0.95 = semantic cache (reuse stored try-on); ~0.75 = preference grounding inside the agent (`retrieve_liked_outfits`). No separate "user history" store. Dislikes are NOT stored (dropped deliberately — dislike just routes the user back to re-pick).
4. **The closet sources garments AFTER outfit selection.** `retrieve_closet` is NOT an agent node — it's a post-selection retrieval: per-key-piece semantic search (by category) against the user's closet, offered alongside "search online."
5. **Try-on honesty:** instruct-pix2pix is instruction-driven — it CANNOT take a garment image as input; it imagines from text. Image-conditioned try-on (person + specific garment image) requires IDM-VTON (or CatVTON/OOTDiffusion) via a duplicated HuggingFace ZeroGPU Space called with `gradio_client` — the standard HF Inference API does NOT serve these models. pix2pix stays as fallback. Never claim image-conditioned fidelity for the pix2pix path.
6. **Agentic value lives at the boundaries:** the agent validates its input (clarification gate) and critiques its own output (generator-critic loop, max 1 retry). These two conditional edges ARE the agentic story.

---

## The agent (target design — 5 nodes, 2 conditional edges)

```
START → analyze_occasion
   ├─ (conditional: clear, dressable occasion?)
   │     no → END, respond with needs_clarification + question
   │     yes ↓
   retrieve_liked_outfits        (Qdrant liked_outfits @ ~0.75, top-k, [] if none)
        ↓
   reason_outfit                 (Gemini; history as SOFT signal: occasion-appropriate
        ↓                         first, preference tiebreaker, keep variety)
   critique_recommendations      (Flash judge: 3 styles distinct? respect formality/
   │                              needed_items? respect-but-not-clone history?)
   ├─ (conditional: pass OR already retried once?)
   │     fail & retry<1 → reason_outfit (critique text passed as feedback)
   │     else → END
```

AgentState (TypedDict, total=False): occasion, style_preference, analysis{formality, style_direction, needed_items}, occasion_clear (bool), clarification_question (str|None), retrieved_history (list[dict]), recommendations, critique_passed (bool), critique_feedback (str|None), critique_retry_count (int), user_id.

Node convention: each node module exposes `run(state) -> dict`, returning ONLY changed keys.

REMOVED from the old graph: search_styles, evaluate_results, refinement_query, retry_count (search retries). Do not resurrect.

---

## Full system flow

```
User inputs occasion
  → semantic cache check (route-level, NOT in graph; skip if skip_cache=true)
      hit (≥0.95): return {cached:true, outfit} → OccasionPage shows inline
        suggestion (Option A card) → View liked look | Generate new (skip_cache)
      miss: run agent → one of:
        {needs_clarification:true, question} → OccasionPage asks user to refine
        {cached:false, recommendations} → StylePickerPage
  → user picks a style
  → GarmentPickerPage: retrieve_closet (per-category semantic search)
      closet matches → show them, offer "use closet" or "search online"
      no matches / user chooses online → Google Shopping fetch (SerpAPI,
        3 queries: top/bottom/shoes, first/best match per category, NO price field)
  → user confirms garments → UploadPage (body photo)
  → try-on: IDM-VTON (person + garment image) when available; pix2pix fallback
  → TryOnPage: Like → two-store write (MongoDB + Qdrant liked_outfits)
              Dislike → navigate back to StylePickerPage with same recommendations
  (cached view: no Like/Dislike; "Generate new recommendations" + "Back to home")
```

---

## Tech stack

| Layer | Tool | Status |
|---|---|---|
| Frontend | React 18, Vite, Router v6, Axios, Tailwind v4 | built |
| Backend | Python 3.11, FastAPI | built |
| Agent | LangGraph (5-node target), google-genai (Gemini Flash) | rebuild |
| Vector DB | Qdrant (Docker), gemini-embedding-001, 3072-dim cosine | built |
| Document DB | MongoDB (Docker), PyMongo | built |
| Cache | services/cache.py check_cache(occasion, user_id) route-level | built |
| Shopping | SerpAPI Google Shopping (free 100/mo; fetch AFTER style pick = 3 queries/flow) | next |
| Try-on v1 | timbrooks/instruct-pix2pix (instruction-driven) | working |
| Try-on v2 | IDM-VTON via duplicated ZeroGPU Space + gradio_client | planned |
| Closet | SegFormer garment isolation + Gemini Vision tagging + dual-store | planned |
| Image storage | MongoDB base64 now; AWS S3 later (only image field changes) | — |

---

## Project structure (deltas from built state)

```
backend/
├── api/routes.py            /styles (cache + agent, 3 response shapes),
│                            /upload, /tryon, /tryon/like,
│                            + /styles/garments (shopping fetch — next)
│                            + /closet/... (later)
├── services/
│   ├── cache.py             built
│   ├── shopping.py          NEXT: search_garment(query, limit) — no price field
│   ├── embed.py, qdrant.py, mongo.py, gemini.py   built
│   └── tryon.py             pix2pix now; idm_vton via gradio_client later
├── agent/
│   ├── state.py             UPDATE to new AgentState fields
│   ├── graph.py             REBUILD: 5 nodes, 2 conditional edges
│   └── nodes/
│       ├── analyze_occasion.py        UPDATE (adds occasion_clear judgment)
│       ├── retrieve_liked_outfits.py  NEW (~0.75, top-k=3, [] if empty)
│       ├── reason_outfit.py           UPDATE (history soft-signal block +
│       │                               optional critique_feedback block)
│       └── critique_recommendations.py NEW (Flash judge, max 1 retry)
frontend/
├── pages/GarmentPickerPage.jsx   NEW (closet/online garment selection)
└── (OccasionPage handles 3rd response shape: needs_clarification)
```

---

## /api/styles — three response shapes (frontend branches on these)

```json
{ "cached": true,  "occasion": "...", "outfit": { "style": {...}, "tryon_image": "..." } }
{ "cached": false, "needs_clarification": true, "question": "..." }
{ "cached": false, "recommendations": [ {style_name, description, key_pieces, reasoning} x3 ] }
```
Request: `{ occasion, style_preference?, skip_cache? (default false) }`

---

## Environment variables

```
GEMINI_API_KEY=...
EMBEDDING_MODEL=gemini-embedding-001
QDRANT_URL=http://localhost:6333
MONGODB_URI=mongodb://localhost:27017/
CACHE_THRESHOLD=0.95
GROUNDING_THRESHOLD=0.75
DEFAULT_USER_ID=local-user
SERPAPI_KEY=...            # next
HF_TOKEN=...               # for IDM-VTON Space, later
```

---

## Design system

Page `#F7F0E8`, sections `#D8C3A5`, cards `#FFFAF3`, primary `#3B2F2F`, secondary `#7A5E5E`, tag bg `#F0E6D8`, tag text `#5A3E2B`, button `#B8875B`, hover `#8A5A3B`, button text `#FFFAF3`. Flat, no shadows, rounded-2xl. Tailwind v4, no config file.

---

## Build order (current queue)

1. **Agent rebuild** — state.py fields; analyze_occasion clarity judgment; retrieve_liked_outfits; reason_outfit soft-signal + feedback blocks; critique_recommendations; graph.py 5-node wiring; route handles needs_clarification; OccasionPage handles the new shape.
2. **Shopping fetch** — services/shopping.py (SerpAPI, no price), POST /styles/garments (3 category queries, graceful [] on failure), GarmentPickerPage, thread selectedGarments through Upload→TryOn.
3. **IDM-VTON standalone proof** — duplicate Space, gradio_client script with 2 hardcoded images; only then wire into /tryon (top-garment-only is acceptable demo scope).
4. **Virtual closet** — ingestion (SegFormer isolate + Vision tag + dual-store) and retrieve_closet per-category search feeding GarmentPickerPage.
5. Later: S3, auth (Phase E), multi-garment try-on compositing.

---

## Interview story (keep consistent)

"A LangGraph agent that validates its input (clarification gate) and critiques its own output (generator-critic with one retry). Recommendations are personalized by RAG over the user's liked-outfit history — one vector store read at two thresholds: strict for a semantic cache that skips regeneration entirely, loose for preference grounding. Garments are sourced from the user's closet via semantic search or fetched live from Google Shopping, and tried on with an image-conditioned model. I deliberately removed web search from recommendation generation — the LLM already knows styling; the web earns its place sourcing real, current garments."
