"""
FastAPI wrapper around the LangGraph triage pipeline, so it can be
triggered by a real webhook (n8n, Elastic Watcher/Alerting, or any SIEM
that can fire an HTTP POST) instead of only running as a CLI script.

Run locally:
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

Interactive docs (Swagger UI): http://localhost:8000/docs
"""

from dotenv import load_dotenv

load_dotenv()  # must run before importing agents, which reads OLLAMA_HOST at import time

from fastapi import FastAPI, HTTPException  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from orchestrator import build_graph  # noqa: E402

app = FastAPI(
    title="agent-orchestrator-soc",
    description=(
        "Multi-agent SOC alert triage API. Supervisor-worker pipeline "
        "(LangGraph) that enriches indicators, searches a local MITRE "
        "ATT&CK / runbook knowledge base (RAG), and writes a triage "
        "report with severity and recommended action."
    ),
    version="0.3.0",
)

# Built lazily (and cached) instead of at import time, so `uvicorn api:app`
# starts instantly and the first request pays the one-time graph/model
# setup cost, not the module import.
_graph = None


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


class TriageResponse(BaseModel):
    alert_id: str | None
    enrichment: str
    research: str
    report: str


@app.get("/health")
def health() -> dict:
    """Liveness check. Confirms the API process is up — does not verify
    that Ollama or the Chroma index are reachable."""
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResponse)
def triage(alert: AlertRequest) -> TriageResponse:
    """Runs the full supervisor-worker pipeline (enrichment -> research ->
    report) on a raw alert and returns the triage report.

    This is the endpoint an n8n workflow or a SIEM webhook action (Elastic
    Watcher, Wazuh active response, etc.) should call to trigger triage
    automatically instead of running the CLI demo by hand.
    """
    graph = _get_graph()
    try:
        final_state = graph.invoke(
            {
                "alert_raw": alert.alert_raw,
                "enrichment": "",
                "research": "",
                "report": "",
                "next_step": "",
            }
        )
    except Exception as exc:  # noqa: BLE001 - surface as a clean 502, don't leak internals
        raise HTTPException(status_code=502, detail=f"Triage pipeline failed: {exc}") from exc

    return TriageResponse(
        alert_id=alert.alert_id,
        enrichment=final_state["enrichment"],
        research=final_state["research"],
        report=final_state["report"],
    )
