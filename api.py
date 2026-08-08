"""
FastAPI wrapper around the LangGraph triage pipeline, so it can be
triggered by a real webhook (n8n, Elastic Watcher/Alerting, or any SIEM
that can fire an HTTP POST) instead of only running as a CLI script.

Run locally:
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

Interactive docs (Swagger UI): http://localhost:8000/docs
"""

import uuid
from typing import Literal

from dotenv import load_dotenv

load_dotenv()  # must run before importing agents, which reads OLLAMA_HOST at import time

from fastapi import FastAPI, HTTPException  # noqa: E402
from langgraph.types import Command  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from orchestrator import build_graph  # noqa: E402

app = FastAPI(
    title="agent-orchestrator-soc",
    description=(
        "Multi-agent SOC alert triage API. Supervisor-worker pipeline "
        "(LangGraph) that enriches indicators, searches a local MITRE "
        "ATT&CK / runbook knowledge base (RAG), and writes a triage "
        "report with severity and recommended action. High/Critical "
        "reports pause for human approval — see POST /triage/{thread_id}/approve."
    ),
    version="0.4.0",
)

# Built lazily (and cached) instead of at import time, so `uvicorn api:app`
# starts instantly and the first request pays the one-time graph/model
# setup cost, not the module import.
_graph = None

# thread_id -> alert_id, so /approve can echo back the caller's original
# correlation ID. In-memory only, same lifetime as the MemorySaver
# checkpointer (see build_graph()) — doesn't survive a process restart.
_alert_ids: dict[str, str | None] = {}


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


class AlertRequest(BaseModel):
    alert_raw: str = Field(
        ...,
        min_length=1,
        description=(
            "Raw alert text (EDR/SIEM log line, Elastic hit formatted as "
            "text, etc.) — exactly what the CLI demo (orchestrator.py) "
            "hardcodes as SAMPLE_ALERT."
        ),
        examples=[
            "[EDR ALERT] Host: WKS-FINANCE-07\n"
            "Process: powershell.exe -EncodedCommand JABzAD0ATgB...\n"
            "Parent process: winword.exe\n"
            "Outbound connection detected: 185.220.101.5:443\n"
            "Additional internal traffic: WKS-FINANCE-07 -> DC01:445"
        ],
    )
    alert_id: str | None = Field(
        default=None,
        description="Optional external alert ID (Elastic/Wazuh rule ID, etc.), echoed back for correlation.",
    )


class ApprovalRequest(BaseModel):
    decision: Literal["approved", "rejected"]


class TriageResponse(BaseModel):
    alert_id: str | None
    thread_id: str
    status: Literal["completed", "pending_approval"]
    enrichment: str
    research: str
    report: str
    severity: str | None = None


def _response_from_state(thread_id: str, alert_id: str | None, state: dict) -> TriageResponse:
    if "__interrupt__" in state:
        payload = state["__interrupt__"][0].value
        return TriageResponse(
            alert_id=alert_id,
            thread_id=thread_id,
            status="pending_approval",
            enrichment=state["enrichment"],
            research=state["research"],
            report=payload["report"],
            severity=state.get("severity"),
        )
    return TriageResponse(
        alert_id=alert_id,
        thread_id=thread_id,
        status="completed",
        enrichment=state["enrichment"],
        research=state["research"],
        report=state["report"],
        severity=state.get("severity"),
    )


@app.get("/health")
def health() -> dict:
    """Liveness check. Confirms the API process is up — does not verify
    that Ollama or the Chroma index are reachable."""
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResponse)
def triage(alert: AlertRequest) -> TriageResponse:
    """Runs the supervisor-worker pipeline (enrichment -> research ->
    report) on a raw alert. For a Low/Medium severity result, returns the
    finished report right away (status="completed"). For High/Critical,
    the pipeline pauses before finishing and returns status="pending_approval"
    — call POST /triage/{thread_id}/approve to resolve it before the alert
    is considered triaged.

    This is the endpoint an n8n workflow or a SIEM webhook action (Elastic
    Watcher, Wazuh active response, etc.) should call to trigger triage
    automatically instead of running the CLI demo by hand.
    """
    graph = _get_graph()
    thread_id = alert.alert_id or str(uuid.uuid4())
    _alert_ids[thread_id] = alert.alert_id
    try:
        final_state = graph.invoke(
            {
                "alert_raw": alert.alert_raw,
                "enrichment": "",
                "research": "",
                "report": "",
                "severity": "",
                "approval": "",
                "next_step": "",
            },
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:  # noqa: BLE001 - surface as a clean 502, don't leak internals
        raise HTTPException(status_code=502, detail=f"Triage pipeline failed: {exc}") from exc

    return _response_from_state(thread_id, alert.alert_id, final_state)


@app.post("/triage/{thread_id}/approve", response_model=TriageResponse)
def approve(thread_id: str, approval: ApprovalRequest) -> TriageResponse:
    """Resolves a pending human-approval gate (see POST /triage) and lets
    the pipeline finish. 404s if there's no run paused on this thread_id
    — either it was never High/Critical, it was already resolved, or the
    API process restarted (the checkpointer is in-memory, see
    build_graph())."""
    graph = _get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    if not graph.get_state(config).next:
        raise HTTPException(status_code=404, detail=f"No pending approval for thread_id '{thread_id}'")

    try:
        final_state = graph.invoke(Command(resume=approval.decision), config=config)
    except Exception as exc:  # noqa: BLE001 - surface as a clean 502, don't leak internals
        raise HTTPException(status_code=502, detail=f"Triage pipeline failed: {exc}") from exc

    return _response_from_state(thread_id, _alert_ids.get(thread_id), final_state)
