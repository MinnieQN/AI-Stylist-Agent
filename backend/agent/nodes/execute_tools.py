from google.genai import types
from agent.tools import execute_tool

"""
Node: execute_tools
Runs the external tool calls the stylist_agent requested, appends each
result to the conversation as a function response, and records the
trace. Tool errors are NOT raised — they go back to the model as the
function response so it can adapt (e.g. unknown city → skip weather).
Also mirrors fetch_liked_history results into retrieved_history, which
the critique node reads for its history-balance criterion.
"""
def run(state: dict) -> dict:
    messages = list(state["messages"])
    trace = list(state.get("tool_call_trace") or [])
    updates = {}

    parts = []
    for call in state.get("pending_tool_calls") or []:
        name, args = call["name"], call["args"]
        trace.append(name)
        try:
            result = execute_tool(name, args, state)
        except Exception as error:
            result = {"error": str(error)}

        # critique's history-balance criterion reads state, not messages
        # also save the liked outfit history into state["retrieved_history"].
        if name == "fetch_liked_history" and "outfits" in result:
            updates["retrieved_history"] = result["outfits"]

        parts.append(types.Part.from_function_response(name=name, response=result))

    messages.append(types.Content(role="tool", parts=parts))

    return {
        **updates,
        "messages": messages,
        "tool_call_trace": trace,
        "pending_tool_calls": [],
    }
