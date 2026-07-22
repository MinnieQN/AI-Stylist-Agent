from dotenv import load_dotenv
load_dotenv()          # run before eval scripts import agent/services

import json, sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# read cases from a JSON file in the data directory
def load_cases(filename: str):
    return json.loads((DATA_DIR / filename).read_text())

# report results to stdout, return the summary dict —
# callers check summary["failed"] == 0, NOT truthiness (a dict is always truthy)
def report(title: str, results: list[dict]) -> dict:
    correct = sum(r["passed"] for r in results)
    print(f"\n{'='*60}\n{title}: {correct}/{len(results)}")
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['label']}")
        if not r["passed"]:
            for k, v in r.get("detail", {}).items():
                print(f"         {k}: {v}")
    # return eval summary
    return {
        "accuracy": correct / len(results),
        "total": len(results),
        "passed": correct,
        "failed": len(results) - correct,
    }