"""
Defines the shared state and the nodes (agents) of the orchestration graph.

Pattern: Supervisor-Worker.
A "supervisor" agent doesn't do work itself: it decides which specialized
agent should act next, based on the accumulated state. Each worker does
ONE thing well and writes its result back to the shared state.
"""

import os
import re
from pathlib import Path
from typing import Literal, TypedDict

from langchain_chroma import Chroma
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langgraph.types import interrupt

from tools import enrich_ioc, get_host_criticality

# Severities that must not reach the caller unattended — a human has to
# approve before the pipeline is considered finished. Low/Medium triage
# still completes end-to-end without a human in the loop.
HIGH_SEVERITIES = {"high", "critical"}
_SEVERITY_RE = re.compile(r"severity\W*(low|medium|high|critical)", re.IGNORECASE)


def _extract_severity(report: str) -> str:
    """Pulls the severity word out of the report text (report_node's prompt
    asks for a 'Severity (Low/Medium/High/Critical)' line). Defaults to
    "high" on a miss — fail closed, route to human approval rather than
    silently skip it if the model didn't follow the format."""
    match = _SEVERITY_RE.search(report)
    return match.group(1).lower() if match else "high"

PERSIST_DIR = Path(__file__).parent / "chroma_db"

# Locally this defaults to http://localhost:11434. In docker-compose,
# OLLAMA_HOST is overridden to http://ollama:11434 (see docker-compose.yml).
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Local model via Ollama. Swap "llama3.2:3b" for whichever model you've pulled.
llm = ChatOllama(model="llama3.2:3b", temperature=0, base_url=OLLAMA_HOST)


# --- Shared state between agents ---------------------------------------------
class TriageState(TypedDict):
    alert_raw: str          # raw incoming alert (log, EDR, SIEM)
    enrichment: str         # result from the enrichment agent
    research: str           # result from the research agent (RAG)
    report: str             # final report
    severity: str           # extracted from the report (low/medium/high/critical)
    approval: str           # "" until a human resolves the approval gate, then "approved"/"rejected"
    next_step: str          # supervisor's routing decision


# --- Supervisor agent ---------------------------------------------------
def supervisor_node(state: TriageState) -> dict:
    """Decides the next step in the pipeline. Linear and deterministic
    (enrich -> research -> report), except for one branch: a High/Critical
    report doesn't reach "end" until a human has resolved the approval
    gate (await_approval), regardless of what that resolution is."""
    if not state.get("enrichment"):
        return {"next_step": "enrichment"}
    if not state.get("research"):
        return {"next_step": "research"}
    if not state.get("report"):
        return {"next_step": "report"}
    if state["severity"] in HIGH_SEVERITIES and not state.get("approval"):
        return {"next_step": "await_approval"}
    return {"next_step": "end"}


def route_after_supervisor(
    state: TriageState,
) -> Literal["enrichment", "research", "report", "await_approval", "end"]:
    return state["next_step"]  # type: ignore[return-value]


# --- Enrichment agent (tool calling) --------------------------------
def enrichment_node(state: TriageState) -> dict:
    llm_with_tools = llm.bind_tools([enrich_ioc, get_host_criticality])
    prompt = (
        "You are a tier-1 SOC analyst. Extract the relevant indicators "
        "(IPs, ports, hostnames) from the following alert and use the "
        "available tools to enrich them.\n\n"
        f"Alert:\n{state['alert_raw']}"
    )
    response = llm_with_tools.invoke(prompt)

    results = []
    for call in response.tool_calls:
        if call["name"] == "enrich_ioc":
            results.append(enrich_ioc.invoke(call["args"]))
        elif call["name"] == "get_host_criticality":
            results.append(get_host_criticality.invoke(call["args"]))

    return {"enrichment": "\n".join(results) if results else "No clear IOCs to enrich."}


# --- Research agent (RAG over your knowledge base) -------------
def research_node(state: TriageState) -> dict:
    embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_HOST)
    vectorstore = Chroma(persist_directory=str(PERSIST_DIR), embedding_function=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    relevant_docs = retriever.invoke(state["alert_raw"])
    context = "\n---\n".join(d.page_content for d in relevant_docs)

    prompt = (
        "You are a detection analyst. Based on the following context from "
        "your knowledge base (runbooks, MITRE ATT&CK notes), identify which "
        "ATT&CK technique(s) match the alert and what action the playbook "
        "recommends.\n\n"
        f"Context:\n{context}\n\n"
        f"Alert:\n{state['alert_raw']}"
    )
    response = llm.invoke(prompt)
    return {"research": response.content}


# --- Report agent --------------------------------------------------
def report_node(state: TriageState) -> dict:
    prompt = (
        "Write a concise, actionable security triage report with these "
        "sections: Summary, Severity (Low/Medium/High/Critical), Enriched "
        "Indicators, Identified MITRE ATT&CK Techniques, and Recommended "
        "Action.\n\n"
        f"Original alert:\n{state['alert_raw']}\n\n"
        f"Enrichment:\n{state['enrichment']}\n\n"
        f"Research:\n{state['research']}"
    )
    response = llm.invoke(prompt)
    report = response.content
    return {"report": report, "severity": _extract_severity(report)}


# --- Human approval gate (High/Critical severity only) ------------------
def await_approval_node(state: TriageState) -> dict:
    """Pauses the graph (via LangGraph's interrupt) so a human can review
    the report before a High/Critical alert is considered resolved. The
    graph must be compiled with a checkpointer for this to actually pause
    execution instead of raising — see build_graph() in orchestrator.py.
    Resuming with Command(resume="approved" | "rejected") sets `approval`
    and lets the supervisor route to "end"."""
    decision = interrupt(
        {
            "reason": f"{state['severity'].capitalize()} severity alert requires human approval.",
            "report": state["report"],
        }
    )
    return {"approval": decision}
