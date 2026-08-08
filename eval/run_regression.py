"""
Regression eval for the triage pipeline: runs a fixed set of alerts
(eval/cases.json) end-to-end against the real graph (real Ollama, real
ChromaDB) and checks a few hard, structural properties of the output —
not exact-text matching, since LLM output isn't stable across runs/model
changes. Meant to catch the kind of regression a unit test can't: a
model swap that quietly changes severity calibration or breaks the
approval gate (see PROJECT.md's GPU/model-swap postmortem for a real
example of a regression this would have caught).

Requires Ollama reachable (OLLAMA_HOST) and the Chroma index already
built (`python ingest_kb.py`). Not part of CI (no Ollama/GPU there) —
run manually after a prompt or model change:

    python -m eval.run_regression
    docker compose exec app python -m eval.run_regression   # or in the container
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from langgraph.types import Command  # noqa: E402

from orchestrator import build_graph  # noqa: E402

CASES_PATH = Path(__file__).parent / "cases.json"


def _run_case(graph, case: dict) -> dict:
    config = {"configurable": {"thread_id": f"regression-{case['id']}"}}
    state = graph.invoke(
        {
            "alert_raw": case["alert_raw"],
            "enrichment": "",
            "research": "",
            "report": "",
            "severity": "",
            "approval": "",
            "next_step": "",
        },
        config=config,
    )

    paused = "__interrupt__" in state
    if paused:
        state = graph.invoke(Command(resume="approved"), config=config)

    failures = []

    severity = state.get("severity", "")
    if severity not in case["expected_severity"]:
        failures.append(
            f"severity={severity!r}, expected one of {case['expected_severity']}"
        )

    if paused != case["expect_approval_gate"]:
        failures.append(
            f"approval gate {'triggered' if paused else 'did not trigger'}, "
            f"expected {'triggered' if case['expect_approval_gate'] else 'not triggered'}"
        )

    enrichment_lower = state.get("enrichment", "").lower()
    if case["enrichment_contains_any"] and not any(
        needle in enrichment_lower for needle in case["enrichment_contains_any"]
    ):
        failures.append(
            f"enrichment missing all of {case['enrichment_contains_any']}: {state.get('enrichment', '')!r}"
        )

    report_lower = state.get("report", "").lower()
    techniques_seen = [t for t in case["informational_techniques"] if t.lower() in report_lower]

    return {
        "id": case["id"],
        "passed": not failures,
        "failures": failures,
        "severity": severity,
        "approval_gate": paused,
        "techniques_seen": techniques_seen,
        "techniques_expected": case["informational_techniques"],
    }


def main() -> int:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    graph = build_graph()

    results = []
    for case in cases:
        print(f"Running: {case['id']} — {case['description']}")
        result = _run_case(graph, case)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"  [{status}] severity={result['severity']} approval_gate={result['approval_gate']}")
        if result["techniques_expected"]:
            print(f"  (informational) techniques cited: {result['techniques_seen']} / {result['techniques_expected']}")
        for failure in result["failures"]:
            print(f"  - {failure}")
        print()

    passed = sum(1 for r in results if r["passed"])
    print(f"{passed}/{len(results)} cases passed")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
