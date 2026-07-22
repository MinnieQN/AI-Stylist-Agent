import sys
from eval.common import load_cases, report   # loads .env before agent imports
from agent.graph import graph

"""
Eval function for the tool routing logic in the agent graph.
This is a unit test for the agent's decision-making logic, not a full integration test.
"""
def run_tool_routing_eval():
    results = []
    # run each case through the agent and check the tool call trace
    for case in load_cases("tool_routing_cases.json"):
        try:
            out = graph.invoke({"occasion": case["occasion"],
                                "user_id": "eval-user",
                                "style_preference": "no preference"})
            trace = out.get("tool_call_trace", [])
            missing   = [t for t in case["expected_tools"] if t not in trace]
            violated  = [t for t in case["forbidden_tools"] if t in trace]
            clear_ok  = out.get("occasion_clear") == case["expect_clear"]
            passed = not missing and not violated and clear_ok
            results.append({"label": case["occasion"], "passed": passed,
                            "detail": {"trace": trace, "missing": missing,
                                    "violated": violated}})
        except Exception as e:
            results.append({"label": case["occasion"], "passed": False,
                            "detail": {"exception": str(e)}})
    return report("Tool Routing", results)


if __name__ == "__main__":
    summary = run_tool_routing_eval()
    sys.exit(0 if summary["failed"] == 0 else 1)