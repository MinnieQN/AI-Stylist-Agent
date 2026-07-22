import sys
from eval.common import load_cases, report   # loads .env before agent imports
from agent.graph import graph

def run_clarification_eval():
    # loop cases, compare to expected
    results = []
    for case in load_cases("clarification_cases.json"):
        try:
            out = graph.invoke({"occasion": case["occasion"],
                                "user_id": "eval-user",
                                "style_preference": "no preference"})

            # check clearance
            clear_ok = out.get("occasion_clear") == case["expected_clear"]
            results.append({"label": case["occasion"], "passed": clear_ok,
                            "detail": {"occasion_clear": out.get("occasion_clear"),
                                       "expected_clear": case["expected_clear"]}})
        except Exception as e:
            results.append({"label": case["occasion"], "passed": False,
                            "detail": {"exception": str(e)}})

    return report("Clarification", results)


if __name__ == "__main__":
    summary = run_clarification_eval()
    sys.exit(0 if summary["failed"] == 0 else 1)
