from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import analyze_occasion
from agent.nodes import retrieve_liked_outfits
from agent.nodes import reason_outfit
from agent.nodes import critique_recommendations

graph_builder = StateGraph(AgentState)

"""
Conditional edge 1 — after analyze_occasion (the clarification gate).
If the input is not a clear, dressable occasion, end the graph early;
the route returns needs_clarification + the question to the frontend.
"""
def route_after_analyze(state: AgentState) -> str:
    if state.get("occasion_clear", False):
        return "retrieve_liked_outfits"
    return "END"

"""
Conditional edge 2 — after critique_recommendations (generator-critic).
critique_retry_count counts how many times the critique has RUN:
after the first critique it is 1, after critiquing the retry it is 2.
Loop back only while count < 2 → exactly one regeneration max.
On the second failure we proceed with what we have rather than loop.
"""
def route_after_critique(state: AgentState) -> str:
    if state.get("critique_passed", False) or state.get("critique_retry_count", 0) >= 2:
        return "END"
    return "reason_outfit"

# add nodes
graph_builder.add_node("analyze_occasion", analyze_occasion.run)
graph_builder.add_node("retrieve_liked_outfits", retrieve_liked_outfits.run)
graph_builder.add_node("reason_outfit", reason_outfit.run)
graph_builder.add_node("critique_recommendations", critique_recommendations.run)

# add edges
# (analyze_occasion → retrieve_liked_outfits is the conditional edge below —
# a fixed edge here as well would bypass the clarification gate)
graph_builder.add_edge(START, "analyze_occasion")
graph_builder.add_edge("retrieve_liked_outfits", "reason_outfit")
graph_builder.add_edge("reason_outfit", "critique_recommendations")

# conditional edge 1: clarification gate
graph_builder.add_conditional_edges(
    "analyze_occasion",
    route_after_analyze,
    {
        "retrieve_liked_outfits": "retrieve_liked_outfits",
        "END": END,
    }
)

# conditional edge 2: critic loop
graph_builder.add_conditional_edges(
    "critique_recommendations",
    route_after_critique,
    {
        "reason_outfit": "reason_outfit",
        "END": END,
    }
)

graph = graph_builder.compile()