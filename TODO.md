# TODO

## Pending
- [ ] Replace `data/mitre_notes.md` with a real knowledge base
- [ ] Connect `enrich_ioc` to OTX AlienVault or a custom MCP server
- [ ] Wire an actual n8n workflow (Webhook node -> HTTP Request -> `POST /triage`)
      against a real Elastic/Wazuh alert, and publish the report to Slack/Obsidian
- [ ] Human-approval node before destructive actions
- [ ] Regression set (alert, report) to evaluate prompt/model changes
- [x] Initialize git + push to GitHub as a portfolio piece
- [ ] Add a GIF of the pipeline running to the README

## In progress
- [ ] Deploy the API (Docker image already runs `uvicorn api:app`) somewhere
      reachable so the n8n webhook item above has a real URL to call

## Done
- [x] Supervisor-worker graph with LangGraph (enrichment, research, report)
- [x] Local RAG over `data/*.md` with Ollama + ChromaDB
- [x] Mocked threat intel + host criticality (tools.py)
- [x] Docker + docker-compose (app + ollama)
- [x] CI: lint (ruff), tests (pytest), Docker build
- [x] Translate repo to English
- [x] Clean up `.git-broken` residue (ignored in .gitignore, safe to delete manually)
- [x] Connect `enrich_ioc` to real APIs (VirusTotal + AbuseIPDB), with `.env` keys,
      exponential backoff, timeout, and fallback to `_FAKE_INTEL_DB` when no key is set
- [x] FastAPI webhook wrapper (`api.py`): `POST /triage`, `GET /health`, Swagger UI
      at `/docs`; Dockerfile/docker-compose updated to run it by default (port 8000)

## Notes (2026-08-03)
- `.git-broken/` is a leftover from a failed git init, already gitignored — not blocking anything, can be deleted with `rm -rf .git-broken`.
- `enrich_ioc` (tools.py) now hits VirusTotal / AbuseIPDB when `VIRUSTOTAL_API_KEY` /
  `ABUSEIPDB_API_KEY` are set in `.env`; with no keys configured it behaves exactly as
  before (mocked `_FAKE_INTEL_DB`), so existing tests are unaffected.
- OTX AlienVault is still not wired up — left for a follow-up.
- `api.py` reuses `build_graph()` from orchestrator.py unchanged — the CLI demo still
  works exactly as before (`python orchestrator.py`). The graph itself doesn't know or
  care whether it was invoked from the CLI or from an HTTP request.
- Tests for the API (`tests/test_api.py`) mock the graph, so `pytest` still doesn't
  need Ollama running, same as the existing tool tests.
