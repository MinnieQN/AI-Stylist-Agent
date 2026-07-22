# AI Stylist Agent — Project Context for Claude

This file lives in the project root. Paste its contents at the start of any new Claude conversation.

---

## What this project is

A full-stack web app: a personal AI wardrobe consultant. User inputs an occasion → a LangGraph **tool-calling agent** generates 3 personalized outfit recommendations (deciding per-request whether to fetch weather, consult liked-outfit history, or ask for clarification) → user picks a style → shoppable garments are fetched from Google Shopping (virtual closet as a second source, later) → user picks garments → uploads a body photo → try-on: IDM-VTON (image-conditioned; chained top+bottom) when garment images exist, instruct-pix2pix (text-driven) as fallback → user likes (stored) or dislikes (re-pick).

**Current status:** Tool-calling agent live (stylist_agent ⇄ execute_tools loop + critic; smoke-tested on all 3 canonical routings). IDM-VTON wired into /tryon including chained top+bottom via the patched Space. Semantic cache + style-preference selector + garment picker with store links live. **Next: implement the eval suite (eval/*.py are empty placeholders — tool_routing eval is the flagship), then the virtual closet.**

---

## Architecture principles (READ FIRST — these encode deliberate decisions)

1. **No web search for styling knowledge.** The LLM knows styling; the web's value is sourcing real garments AFTER style selection. The agent's tools fetch FACTS the LLM cannot know (live weather, the user's private history) — that's the line. Do not add a style-inspiration search tool.
2. **RAG = private user data only.** No generic style-knowledge corpus. Two stores: liked_outfits (built), closet_items (later).
3. **liked_outfits: ONE store, TWO thresholds.** CACHE_THRESHOLD (env, 0.90) = semantic cache, route-level, returns stored try-on as an inline suggestion the user confirms. GROUNDING_THRESHOLD (env, 0.65 — measured: related occasions score ~0.70-0.80 on occasion-only vectors, unrelated ~0.59) = preference grounding via the fetch_liked_history tool. Dislikes NOT stored — dislike navigates back to StylePickerPage with the same recommendations.
4. **Agentic value at the boundaries:** clarification gate (ask_clarification terminator tool) + output generator-critic loop (max 1 regeneration, rerun through the same agent loop with feedback). Critique double-fail = silent degrade (DELIBERATE: ship the 2nd attempt, no UI hint).
5. **Two-store pattern:** shared uuid4 string is Mongo _id AND Qdrant point id (Mongo ObjectId is invalid as a Qdrant id). Qdrant payload minimal: {user_id} only; fetch Mongo via hit.id.
6. **Cache vector is occasion-ONLY, symmetric with the cache query.** Measured via eval_retrieval: appending style_name cost ~0.17 similarity — an EXACT occasion repeat scored 0.825, making the 0.90 cache threshold unreachable (and the earlier occasion+style+description formula was worse still). Occasion-only scores 1.0 on exact repeats, ~0.84 on loose paraphrases (deliberately below the 0.90 bar). The cache is a user-confirmed SUGGESTION, so imperfect matching is fine.
7. **key_pieces_categorized is the source of truth** for garment categories: `{"top": [...], "bottom": [...], "shoes": [...]}` — exactly these keys; outerwear/accessories under top. Enforced by the finalize_recommendations schema + validate_recommendations() (folds extra keys under top, derives flat `key_pieces` in code for StyleCard/gemini.py/critique). categorize_key_pieces() keyword rules remain ONLY as endpoint fallback.
8. **Try-on honesty + routing:** pix2pix is instruction-driven (cannot take garment images). IDM-VTON = image-conditioned, via duplicated + PATCHED HF ZeroGPU Space (LittleMinnie/IDM-VTON) + gradio_client. The patch exposes a `category` API arg (upper_body/lower_body/dresses) — the stock Space hardcodes upper_body, and gradio_client SILENTLY DROPS unknown extra args (pants got painted on the torso before the guard existed). Routing in /tryon: top+bottom images → chained_tryon (top first, bottom on the result; step-2 failure returns step-1); top only → upper_body; bottom only → lower_body; none or VTON raises → pix2pix (failure reason is logged — silent fallbacks cost a debugging session). SHOES ARE NOT A VTON CATEGORY (display-only).
9. **Shopping is an enhancement layer:** categories with no pieces are OMITTED from the response (a dress look has no bottom section); a category whose search fails returns [] (quiet "no products" note); per-category try/except; picker gates Continue on non-empty TRY-ON categories only (top/bottom — shoes are display-only, no Select button); error path still offers "continue without products."

---

## The agent (current — 3 nodes, 2 conditional edges, the loop IS the topology)

```
START → stylist_agent (Flash + 4 tool declarations; ONE Gemini turn per run;
   │        classifies its response into agent_outcome)
   ├─ route_after_agent on agent_outcome:
   │    "tools"    → execute_tools — runs the requested external tools,
   │                 appends function responses to messages, records
   │                 tool_call_trace, mirrors history → retrieved_history
   │                 — then fixed edge back to stylist_agent
   │    "clarify"  → END (needs_clarification path)
   │    "continue" → stylist_agent (plain-text nudge / invalid finalize retry)
   │    "finalize" → critique_recommendations
   ↓
critique_recommendations (UNCHANGED Flash judge: distinctness, constraint
   │     fit vs analysis formality/needed_items — analysis is submitted BY
   │     the model inside the finalize call; history-balance — passes if no
   │     history; COUNTS CRITIQUE RUNS: 1 after first, 2 after retry's)
   ├─ route_after_critique: passed OR critique_retry_count ≥ 2 → END
   └─ else → stylist_agent (critique_feedback appended as a user message;
             regeneration reuses the same loop code path)
```

The four tools (agent/tools.py — native google-genai FunctionDeclarations, NOT LangChain):

| Tool | Kind | Backing | The LLM-owned decision |
|---|---|---|---|
| get_weather(city) | external | services/weather.py — Open-Meteo, no key, sync, WMO code → words | IF occasion is outdoor/weather-dependent AND located |
| fetch_liked_history(query) | external | Qdrant query_points @ GROUNDING_THRESHOLD + Mongo fetch, user_id-scoped | WHETHER history helps and WHAT query text to use |
| ask_clarification(question) | terminator | intercepted by stylist_agent → occasion_clear=False | WHEN input is unstylable (gibberish / not an occasion / too vague) |
| finalize_recommendations(analysis, recommendations) | terminator | validate_recommendations() enforces the contract; invalid → error returned as function response, model retries | the structured-output terminator |

**Loop safety:** MAX_LOOP_ITERATIONS=4 → tool_config forces finalize (mode="ANY"); HARD_STOP_ITERATIONS=6 → raise (route 500s; never hang); LangGraph recursion_limit=25 is the outer backstop.

AgentState additions for the loop: messages (google-genai Content list — the loop's memory), pending_tool_calls, tool_call_trace (evals/debugging), loop_iterations, agent_outcome. Plus the original: occasion, style_preference, user_id, analysis, occasion_clear, clarification_question, retrieved_history, recommendations, critique_passed, critique_feedback, critique_retry_count.

Invoke with INPUTS ONLY: `{occasion, style_preference, user_id}` — no counter seeding (nodes use .get defaults).

Watch: Flash critique may over-fail; if >half of first attempts fail, soften "strictly" → "fairly" in the judge prompt.

---

## /api/styles — three response shapes (UNCHANGED by the agent refactor)

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
| POST | /api/tryon | { style, occasion, filepath, garments? } | routing per principle 8 (chained / upper / lower / pix2pix); deletes temp file in finally; returns {image} base64 |
| POST | /api/tryon/warmup | (empty) | fire-and-forget Space wake-up (background thread, ~10ms response); UploadPage fires it on mount so the multi-minute ZeroGPU cold start overlaps with photo picking (latency hiding); waking costs no GPU quota |
| POST | /api/tryon/like | { occasion, style, tryon_image } | two-store write: Mongo insert → embed(occasion ONLY — symmetric with cache query) → Qdrant upsert (shared uuid) |
| POST | /api/styles/garments | { occasion, style, style_preference? } | prefers key_pieces_categorized, keyword fallback; query = gender term ("women's"/"men's" from style_preference) + cleaned piece (parentheticals stripped, LAST "or"-alternative kept — first can be a bare adjective); style_name NOT in query (returned men's items in a womenswear flow); empty-piece categories omitted; per-category try/except → [] |

SerpAPI free tier = 100 searches/month. Product fields: title, image_url (thumbnail ~225px — the VTON quality ceiling), product_link — NO price (deliberate).

---

## Frontend flow & pages

```
OccasionPage (input + style-preference pills [womenswear/menswear/no preference],
   localStorage-persisted, soft tag-palette styling; handles 3 response
   shapes: clarification banner, cache card w/ thumbnail + Generate new/
   View liked look, or navigate)
→ StylePickerPage (3 cards, fade-on-select, navigates to /garments with
   {selectedStyle, occasion, recommendations})
→ GarmentPickerPage (fetch on mount, sends style_preference from localStorage;
   Object.entries render — handles any categories; product image links out
   to store (new tab), selection via Select button under each card
   (bottom-aligned via flex column); top/bottom sections tagged "shown in
   your try-on", others "display only" with NO Select button; Continue
   gated on non-empty TRYON_CATEGORIES=[top,bottom] only; empty category
   from failed search = quiet note; error path offers continue-without)
→ UploadPage (fires /tryon/warmup on mount — cold start overlaps photo
   picking; relays selectedGarments; shows garment thumbnails preview;
   guard checks selectedStyle only — garments optional)
→ TryOnPage (fromCache branch: setImage + skip generation; normal branch:
   sends garments in /tryon POST; loading copy varies: chained "top, then
   bottom — a few minutes" / single garment / plain; StrictMode useRef
   guard — effects fired generation TWICE before (2x GPU quota + concurrent
   pix2pix crash); Dislike → /styles with same recommendations; Like →
   disabled after success (was writing duplicates) + Back-to-home appears)
```

State relay chain: recommendations + selectedGarments thread through every navigate.

---

## Tech stack & environment

Python 3.11, FastAPI :8001, React 18/Vite :5173 (axios baseURL 127.0.0.1:8001/api), Tailwind v4 (no config), Qdrant Docker :6333 (3072-dim cosine, gemini-embedding-001), MongoDB Docker :27017 (PyMongo, db ai_stylist), google-genai SDK (`from google import genai`), LangGraph, SerpAPI (google-search-results pkg), gradio_client 2.x (kwarg is `token`, NOT hf_token) + duplicated+patched IDM-VTON ZeroGPU Space, timbrooks/instruct-pix2pix (local MPS fallback; threading.Lock — concurrent runs corrupt the scheduler), Open-Meteo via requests (weather tool).

**Model strings are env-driven** (gemini-2.5-flash was retired and hard-broke the agent): GEMINI_MODEL in .env (currently gemini-3-flash-preview; default alias gemini-flash-latest). Embeddings: gemini-embedding-001.

.env (project root): GEMINI_API_KEY, GEMINI_MODEL, EMBEDDING_MODEL=gemini-embedding-001, QDRANT_URL, MONGODB_URI, CACHE_THRESHOLD=0.90, GROUNDING_THRESHOLD=0.75, DEFAULT_USER_ID=local-user, SERPAPI_KEY, HF_TOKEN (READ-only — cannot push to the Space), HF_SPACE=LittleMinnie/IDM-VTON.

docker-compose.yml (root): qdrant (qdrant_data volume) + mongodb (mongo:7, mongo_data volume). Stray-container lesson: if a port won't bind, check `docker ps -a`.

Services: cache.py (check_cache → record|None; threshold from env), embed.py (embed_text, embed_texts), qdrant.py (ensure_collections on startup; use query_points — .search() removed in qdrant-client ≥1.12), mongo.py (verify_connection on startup), shopping.py (search_garment(key_piece, style_preference) + _clean_piece; [] is valid), weather.py (get_weather(city) — current conditions, date param accepted but unused), pix2pix.py (generate_tryon_image + lock), tryon_vton.py (idm_vton_tryon(person, garment_url, desc, category) + chained_tryon; lazy cached Client — import-time connect would crash boot when Space is down; 300s read timeout — cold starts exceeded the default and silently degraded to pix2pix; _space_supports_category guard; warmup_space() fire-and-forget background connect, client creation is lock-guarded against the warmup/tryon race).

**ZeroGPU reality:** free quota is small and resets on a multi-hour window; each VTON step requests ~90s. Space sleeps after idle — first call cold-starts for minutes (now survives via the long timeout). After editing the Space, RESTART the backend — the gradio client caches the API signature at connect time.

---

## Build queue (in order)

1. **IDM-VTON wiring** (DONE) — routing + fallbacks live and tested end-to-end.
2. **Chained full-body VTON** (DONE) — top then bottom via patched Space category arg; ~47s warm; step-2 failure returns step-1.
3. **Tool-calling agent** (DONE) — stylist_agent ⇄ execute_tools loop, 4 tools, critic unchanged.
4. **Evals** — eval/*.py are EMPTY placeholders (only data/*.json exist). Flagship: eval_tool_routing.py asserting tool_call_trace per occasion ("bank interview" → history not weather; "outdoor wedding in Maine" → weather; "asdf" → clarification only). Adapt clarification/critique/retrieval evals to invoke the graph.
5. **Virtual closet** — per-garment upload → SegFormer (mattmdjaga/segformer_b2_clothes) isolate → Gemini Vision tag → embed rich description → Mongo + Qdrant closet_items. retrieve_closet = post-selection per-category semantic search (NOT an agent tool), feeds GarmentPickerPage alongside shopping. CAUTION: SegFormer is trained on worn clothing — may fail on flat product photos.
6. Later: S3 (only tryon_image field changes), auth (Phase E), multi-garment compositing beyond top+bottom, Gemini-image try-on comparison path (nano-banana: person+top+bottom in ONE call — candidate replacement for pix2pix fallback and/or chained VTON).

---

## Design system

Page #F7F0E8, sections #D8C3A5, cards #FFFAF3, primary text #3B2F2F, secondary #7A5E5E, tag bg #F0E6D8, tag text #5A3E2B, button #B8875B, hover #8A5A3B, button text #FFFAF3. Flat, no shadows, rounded-2xl.

---

## Interview story (keep consistent)

"The stylist is a tool-using agent: a LangGraph loop where the LLM node decides per-request which tools to call — live weather for outdoor occasions, vector search over the user's liked-outfit history for personalization — and conditional edges route tool execution, clarification requests, and the final structured recommendations. Two terminator tools end the loop: ask_clarification when input isn't stylable, and a schema-enforced finalize whose payload an independent critic reviews before anything ships (one regeneration max, then degrade gracefully). Personalization is RAG over private data only — one vector store read at two thresholds: strict for a semantic cache that skips generation entirely, loose for preference grounding. After the user picks a style, garments are sourced live from Google Shopping, and tried on with IDM-VTON — image-conditioned and chained top-then-bottom on a Space I patched to expose the mask category — falling back to instruction-driven pix2pix. I kept the agent's autonomy deliberately narrow: tools fetch facts the model can't know (weather, my history); styling knowledge stays in the model, and web search earns its place only sourcing real garments."
