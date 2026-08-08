"""Tests for the FastAPI webhook wrapper (api.py).

The LangGraph pipeline itself is mocked out (via `api._get_graph`), so
these tests don't require Ollama or a built Chroma index to run — same
philosophy as test_tools.py.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import api


def _client_with_mocked_graph(final_state: dict) -> TestClient:
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = final_state
    api._graph = mock_graph  # bypass build_graph(); avoids requiring Ollama
    return TestClient(api.app)


def test_health():
    client = TestClient(api.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_triage_happy_path():
    client = _client_with_mocked_graph(
        {
            "enrichment": "185.220.101.5 is a known Tor exit node.",
            "research": "Matches MITRE T1071 (Application Layer Protocol).",
            "report": "Severity: High. Recommended action: isolate WKS-FINANCE-07.",
        }
    )
    response = client.post(
        "/triage",
        json={"alert_raw": "[EDR ALERT] Host: WKS-FINANCE-07", "alert_id": "wazuh-100002"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["alert_id"] == "wazuh-100002"
    assert "Tor exit node" in body["enrichment"]
    assert "T1071" in body["research"]
    assert "isolate" in body["report"]


def test_triage_requires_alert_raw():
    client = TestClient(api.app)
    response = client.post("/triage", json={"alert_id": "no-alert-text"})
    assert response.status_code == 422  # Pydantic validation error


def test_triage_pipeline_failure_returns_502():
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = RuntimeError("Ollama unreachable")
    api._graph = mock_graph
    client = TestClient(api.app)
    response = client.post("/triage", json={"alert_raw": "some alert"})
    assert response.status_code == 502
    assert "Triage pipeline failed" in response.json()["detail"]


def test_triage_high_severity_pauses_for_approval():
    interrupt_payload = SimpleNamespace(
        value={
            "reason": "High severity alert requires human approval.",
            "report": "Severity: High. Recommended action: isolate WKS-FINANCE-07.",
        }
    )
    client = _client_with_mocked_graph(
        {
            "enrichment": "185.220.101.5 is a known Tor exit node.",
            "research": "Matches MITRE T1071.",
            "severity": "high",
            "__interrupt__": [interrupt_payload],
        }
    )
    response = client.post(
        "/triage",
        json={"alert_raw": "[EDR ALERT] Host: WKS-FINANCE-07", "alert_id": "wazuh-100003"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_approval"
    assert body["severity"] == "high"
    assert body["thread_id"] == "wazuh-100003"
    assert "isolate" in body["report"]


def test_approve_resolves_pending_run():
    mock_graph = MagicMock()
    mock_graph.get_state.return_value = SimpleNamespace(next=("await_approval",))
    mock_graph.invoke.return_value = {
        "enrichment": "185.220.101.5 is a known Tor exit node.",
        "research": "Matches MITRE T1071.",
        "report": "Severity: High. Recommended action: isolate WKS-FINANCE-07.",
        "severity": "high",
        "approval": "approved",
    }
    api._graph = mock_graph
    client = TestClient(api.app)
    response = client.post("/triage/wazuh-100003/approve", json={"decision": "approved"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert "isolate" in body["report"]


def test_approve_unknown_thread_returns_404():
    mock_graph = MagicMock()
    mock_graph.get_state.return_value = SimpleNamespace(next=())
    api._graph = mock_graph
    client = TestClient(api.app)
    response = client.post("/triage/does-not-exist/approve", json={"decision": "approved"})
    assert response.status_code == 404
