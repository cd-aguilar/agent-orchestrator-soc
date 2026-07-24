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

from langgraph.graph import END, StateGraph  # noqa: E402

from agents import (  # noqa: E402
    TriageState,
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

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "enrichment": "enrichment",
            "research": "research",
            "report": "report",
            "end": END,
        },
    )
    # Each worker goes back to the supervisor so it can decide the next step
    graph.add_edge("enrichment", "supervisor")
    graph.add_edge("research", "supervisor")
    graph.add_edge("report", "supervisor")

    return graph.compile()


def main():
    app = build_graph()

    final_state = app.invoke(
        {
            "alert_raw": SAMPLE_ALERT,
            "enrichment": "",
            "research": "",
            "report": "",
            "next_step": "",
        }
    )

    print("\n" + "=" * 70)
    print("TRIAGE REPORT")
    print("=" * 70)
    print(final_state["report"])


if __name__ == "__main__":
    main()
