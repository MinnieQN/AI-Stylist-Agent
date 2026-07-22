import sys
from eval.common import load_cases, report   # MUST come first: loads .env before
from agent.nodes import critique_recommendations  # this import builds the genai client

def run_critique_eval():
    results = []
    for case in load_cases("critique_cases.json"):
        try:
            out = critique_recommendations.run({
                "recommendations": case["recommendations"],
                "analysis": case["analysis"],
                "retrieved_history": case["retrieved_history"],
            })
            passed = out["critique_passed"] == case["expected_pass"]
            results.append({"label": case["case_name"], "passed": passed,
                            "detail": {"critique_passed": out["critique_passed"],
                                       "expected_pass": case["expected_pass"],
                                       "feedback": out.get("critique_feedback")}})
        except Exception as e:
            results.append({"label": case["case_name"], "passed": False,
                            "detail": {"exception": str(e)}})
    return report("Critique", results)


if __name__ == "__main__":
    summary = run_critique_eval()
    sys.exit(0 if summary["failed"] == 0 else 1)
