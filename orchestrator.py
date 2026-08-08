"""
Entry point: builds the LangGraph StateGraph and runs a sample security
alert triage.

Usage:
    python ingest_kb.py     # once, to build the RAG index
    python orchestrator.py  # runs the multi-agent pipeline
"""

from dotenv import load_dotenv

load_dotenv()  # loads .env if present (OLLAMA_HOST, future API keys, etc.)
# Must run BEFORE importing agents, which reads OLLAMA_HOST at import time.

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from langgraph.graph import END, StateGraph  # noqa: E402
from langgraph.types import Command  # noqa: E402

from agents import (  # noqa: E402
    TriageState,
    await_approval_node,
    enrichment_node,
    report_node,
    research_node,
    route_after_supervisor,
    supervisor_node,
)

SAMPLE_ALERT = """\
[EDR ALERT] Host: WKS-FINANCE-07
Process: powershell.exe -EncodedCommand JABzAD0ATgB...
Parent process: winword.exe
Outbound connection detected: 185.220.101.5:443
Additional internal traffic: WKS-FINANCE-07 -> DC01:445
"""


def build_graph():
    graph = StateGraph(TriageState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("enrichment", enrichment_node)
    graph.add_node("research", research_node)
    graph.add_node("report", report_node)
    graph.add_node("await_approval", await_approval_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "enrichment": "enrichment",
            "research": "research",
            "report": "report",
            "await_approval": "await_approval",
            "end": END,
        },
    )
    # Each worker goes back to the supervisor so it can decide the next step
    graph.add_edge("enrichment", "supervisor")
    graph.add_edge("research", "supervisor")
    graph.add_edge("report", "supervisor")
    graph.add_edge("await_approval", "supervisor")

    # A checkpointer is required for interrupt()/Command(resume=...) to
    # actually pause and later resume a run instead of raising. MemorySaver
    # is in-process only (checkpoints don't survive a restart) — fine for
    # the CLI demo and single-process API deployment this repo ships with;
    # swap for a persistent checkpointer (Postgres/Redis) for real 24/7 use.
    return graph.compile(checkpointer=MemorySaver())


def main():
    app = build_graph()
    config = {"configurable": {"thread_id": "cli-demo"}}

    result = app.invoke(
        {
            "alert_raw": SAMPLE_ALERT,
            "enrichment": "",
            "research": "",
            "report": "",
            "severity": "",
            "approval": "",
            "next_step": "",
        },
        config=config,
    )

    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print("\n" + "=" * 70)
        print("APPROVAL REQUIRED — " + payload["reason"])
        print("=" * 70)
        print(payload["report"])
        decision = input("\nApprove this triage? [y/N] ").strip().lower()
        result = app.invoke(
            Command(resume="approved" if decision == "y" else "rejected"),
            config=config,
        )

    print("\n" + "=" * 70)
    print("TRIAGE REPORT")
    print("=" * 70)
    print(result["report"])
    if result.get("approval"):
        print(f"\n[Human decision: {result['approval']}]")


if __name__ == "__main__":
    main()
