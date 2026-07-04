from typing import TypedDict, Optional


class AgentState(TypedDict, total=False):
    """
    Shared state flowing through the 5-node agent graph.
    total=False: fields are filled in progressively as nodes run.
    Each node returns ONLY the keys it changes.
    """

    # ── Inputs (set at invocation) ─────────────────────────────
    occasion: str                       # required at entry
    style_preference: Optional[str]     # e.g. "feminine", "masculine", "no preference"
    user_id: str                        # DEFAULT_USER_ID until Phase E auth

    # ── Set by analyze_occasion ────────────────────────────────
    analysis: dict                      # {"formality", "style_direction", "needed_items"}
    occasion_clear: bool                # is the input a clear, dressable occasion?
    clarification_question: Optional[str]  # set when occasion_clear is False —
                                           # the question to show the user

    # ── Set by retrieve_liked_outfits ──────────────────────────
    retrieved_history: list[dict]       # top-k past liked outfits (~0.75 threshold);
                                        # empty list when user has no relevant history

    # ── Set by reason_outfit ───────────────────────────────────
    recommendations: list[dict]         # 3 styles: style_name, description,
                                        # key_pieces, reasoning

    # ── Set by critique_recommendations ────────────────────────
    critique_passed: bool               # judge verdict on the 3 recommendations
    critique_feedback: Optional[str]    # what to fix, passed back to reason_outfit
                                        # on the single allowed retry
    critique_retry_count: int           # starts at 0; max 1 regeneration