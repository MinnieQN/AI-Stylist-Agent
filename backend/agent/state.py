from typing import TypedDict, Optional


class AgentState(TypedDict, total=False):
    """
    Shared state flowing through the 4-node agent graph.
    total=False: fields are filled in progressively as nodes run.
    Each node returns ONLY the keys it changes.
    """

    # ── Inputs (set at invocation) ─────────────────────────────
    occasion: str                       # required at entry
    style_preference: Optional[str]     # e.g. "feminine", "masculine", "no preference"
    user_id: str                        # DEFAULT_USER_ID until Phase E auth

    # ── Agent loop (stylist_agent -> execute_tools cycle) ───────
    messages: list                      # running google-genai Content list — the loop's memory
    pending_tool_calls: list[dict]      # external calls awaiting execution [{name, args}]
    tool_call_trace: list[str]          # every tool the model called, in order (evals/debugging)
    loop_iterations: int                # stylist_agent runs; cap forces finalize
    agent_outcome: Optional[str]        # last run's result: "tools" | "clarify" | "finalize" | "continue"

    # ── Set by stylist_agent on terminator calls ───────────────
    analysis: dict                      # {"formality", "style_direction", "needed_items"}
                                        # — submitted by the model with finalize; critique reads it
    occasion_clear: bool                # is the input a clear, dressable occasion?
    clarification_question: Optional[str]  # set when occasion_clear is False —
                                           # the question to show the user
    recommendations: list[dict]         # 3 validated styles: style_name, description,
                                        # key_pieces_categorized, key_pieces (derived), reasoning

    # ── Set by execute_tools ───────────────────────────────────
    retrieved_history: list[dict]       # fetch_liked_history results (~0.75 threshold);
                                        # mirrored into state for the critique node

    # ── Set by critique_recommendations ────────────────────────
    critique_passed: bool               # judge verdict on the 3 recommendations
    critique_feedback: Optional[str]    # what to fix, injected into the agent loop
                                        # on the single allowed regeneration
    critique_retry_count: int           # starts at 0; max 1 regeneration