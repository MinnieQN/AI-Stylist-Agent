import os
from google import genai
from google.genai import types
from shared.retry import generate_with_retry
from agent.tools import TOOL_DECLARATIONS, validate_recommendations

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# agent model — set GEMINI_MODEL in .env; the alias default tracks the latest
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

# after this many stylist_agent runs, tool choice is FORCED to finalize
MAX_LOOP_ITERATIONS = 4
# absolute ceiling — raise instead of looping forever if even forced
# finalize keeps failing validation (route → 500, never a hang)
HARD_STOP_ITERATIONS = 6

SYSTEM_PROMPT = """
You are a personal stylist agent. Given a user's occasion and style
preference, your job is to produce exactly 3 distinct outfit style
recommendations — or, if the input is not something you can style for,
to ask ONE clarifying question.

You must ALWAYS respond by calling one of your tools. Never reply with
plain text.

## Judging the occasion
Call ask_clarification (and nothing else) if the input is:
- gibberish or random characters
- not an occasion at all (a general question, a greeting)
- too vague to determine formality (e.g. "something nice", "an event")
Otherwise it is a dressable occasion — proceed.

## Gathering context (external tools)
- fetch_liked_history: call once for any normal styling request, with a
  short query describing the occasion's aesthetic. An empty result means
  no relevant history — proceed without it.
- get_weather: call ONLY if the occasion is plausibly outdoors or
  weather-dependent AND a location is mentioned or clearly inferable
  (e.g. "rooftop party in Austin" → yes; "beach wedding in Miami" → yes;
  "job interview at a bank" → no; "picnic with friends" → no location, no).
- Do not call any tool twice with the same arguments.

## Building recommendations
- The 3 styles must be genuinely distinct in character
  (e.g. classic vs modern vs relaxed).
- Match the occasion's formality first.
- If fetch_liked_history returned outfits: make exactly ONE of the 3
  styles closely reflect a liked outfit's aesthetic (its reasoning
  should say it builds on a look the user liked before), and keep the
  other TWO clearly different from the history — never three clones.
  If history is empty, ignore this rule.
- If you fetched weather, let it shape fabrics and layering.
- Respect the style preference. If it is "no preference" or absent,
  do not assume gendered clothing norms.
- key_pieces_categorized uses EXACTLY the keys top, bottom, shoes.
  Outerwear and accessories belong under top. An empty category is
  valid (e.g. a dress look has an empty bottom).

When you have enough context, call finalize_recommendations with your
occasion analysis and the 3 styles. That ends the session.
"""

"""
Node: stylist_agent
One Gemini function-calling turn. Appends the model's response to the
running conversation and classifies what happened into agent_outcome:
  "tools"    → external calls pending, route to execute_tools
  "clarify"  → ask_clarification called, route to END
  "finalize" → valid recommendations stored, route to critique
  "continue" → nudge/invalid finalize, route back here
Re-entry after a failed critique appends the critic's feedback so the
model regenerates through the same code path.
"""
def run(state: dict) -> dict:
    iterations = state.get("loop_iterations", 0)
    if iterations >= HARD_STOP_ITERATIONS:
        raise RuntimeError("stylist agent could not produce valid recommendations")

    # first entry: seed the conversation with the user's request
    messages = list(state.get("messages") or [])
    if not messages:
        messages.append(types.Content(role="user", parts=[types.Part.from_text(text=(
            f'Occasion: "{state["occasion"]}"\n'
            f'Style preference: {state.get("style_preference") or "no preference"}'
        ))]))

    # re-entry from a failed critique: inject the feedback once
    if state.get("agent_outcome") == "finalize" and state.get("critique_feedback"):
        messages.append(types.Content(role="user", parts=[types.Part.from_text(text=(
            "A reviewer critiqued your recommendations before they could be "
            f"shown to the user: {state['critique_feedback']}\n"
            "Call finalize_recommendations again with improved recommendations."
        ))]))

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=TOOL_DECLARATIONS)],
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    # iteration cap reached — stop exploring, force the terminator
    if iterations >= MAX_LOOP_ITERATIONS:
        config.tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="ANY", allowed_function_names=["finalize_recommendations"],
            )
        )

    response = generate_with_retry(
        client, model=GEMINI_MODEL, contents=messages, config=config,
    )
    messages.append(response.candidates[0].content)

    updates = {"messages": messages, "loop_iterations": iterations + 1}
    trace = list(state.get("tool_call_trace") or [])
    function_calls = response.function_calls or []

    # terminators take precedence over anything else in the same response
    for fc in function_calls:
        if fc.name == "ask_clarification":
            trace.append(fc.name)
            return {
                **updates,
                "tool_call_trace": trace,
                "agent_outcome": "clarify",
                "occasion_clear": False,
                "clarification_question": (fc.args or {}).get(
                    "question", "Could you tell me more about your occasion?"
                ),
                "pending_tool_calls": [],
            }
        if fc.name == "finalize_recommendations":
            trace.append(fc.name)
            args = fc.args or {}
            try:
                recommendations = validate_recommendations(args.get("recommendations"))
            except ValueError as error:
                # invalid payload — report it as the function response and loop
                messages.append(types.Content(role="tool", parts=[
                    types.Part.from_function_response(
                        name=fc.name, response={"error": str(error)},
                    )
                ]))
                return {
                    **updates,
                    "messages": messages,
                    "tool_call_trace": trace,
                    "agent_outcome": "continue",
                    "pending_tool_calls": [],
                }
            return {
                **updates,
                "tool_call_trace": trace,
                "agent_outcome": "finalize",
                "occasion_clear": True,
                "recommendations": recommendations,
                # critique reads analysis — the agent submits it at finalize
                "analysis": args.get("analysis") or {},
                "pending_tool_calls": [],
            }

    # external tool calls — hand off to execute_tools
    if function_calls:
        return {
            **updates,
            "agent_outcome": "tools",
            "pending_tool_calls": [
                {"name": fc.name, "args": dict(fc.args or {})} for fc in function_calls
            ],
        }

    # plain text response — remind the model of the contract and loop
    messages.append(types.Content(role="user", parts=[types.Part.from_text(text=(
        "You must respond by calling one of your tools — either gather "
        "context, ask_clarification, or finalize_recommendations."
    ))]))
    return {
        **updates,
        "messages": messages,
        "agent_outcome": "continue",
        "pending_tool_calls": [],
    }
