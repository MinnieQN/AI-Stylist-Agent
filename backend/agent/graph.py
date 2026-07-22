from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import stylist_agent
from agent.nodes import execute_tools
from agent.nodes import critique_recommendations

graph_builder = StateGraph(AgentState)

"""
Conditional edge 1 — after each stylist_agent turn.
Routes on agent_outcome, which the node sets from the model's response:
  "tools"    → run the requested external tools, then loop back
  "clarify"  → clarification gate fired; END (needs_clarification path)
  "finalize" → valid recommendations produced; judge them
  "continue" → nudge or invalid finalize; take another turn
"""
def route_after_agent(state: AgentState) -> str:
    outcome = state.get("agent_outcome")
    if outcome == "tools":
        return "execute_tools"
    if outcome == "clarify":
        return "END"
    if outcome == "finalize":
        return "critique_recommendations"
    return "stylist_agent"

"""
Conditional edge 2 — after critique_recommendations (generator-critic).
critique_retry_count counts how many times the critique has RUN:
after the first critique it is 1, after critiquing the retry it is 2.
Loop back only while count < 2 → exactly one regeneration max.
On the second failure we proceed with what we have rather than loop.
Regeneration reruns the agent loop with the feedback appended.
"""
def route_after_critique(state: AgentState) -> str:
    if state.get("critique_passed", False) or state.get("critique_retry_count", 0) >= 2:
        return "END"
    return "stylist_agent"

# add nodes
graph_builder.add_node("stylist_agent", stylist_agent.run)
graph_builder.add_node("execute_tools", execute_tools.run)
graph_builder.add_node("critique_recommendations", critique_recommendations.run)

# add edges — the agent -> tools cycle is the agentic loop
graph_builder.add_edge(START, "stylist_agent")
graph_builder.add_edge("execute_tools", "stylist_agent")

# conditional edge 1: tool routing / clarification gate / finalize
graph_builder.add_conditional_edges(
    "stylist_agent",
    route_after_agent,
    {
        "execute_tools": "execute_tools",
        "critique_recommendations": "critique_recommendations",
        "stylist_agent": "stylist_agent",
        "END": END,
    }
)

# conditional edge 2: critic loop
graph_builder.add_conditional_edges(
    "critique_recommendations",
    route_after_critique,
    {
        "stylist_agent": "stylist_agent",
        "END": END,
    }
)

graph = graph_builder.compile()
