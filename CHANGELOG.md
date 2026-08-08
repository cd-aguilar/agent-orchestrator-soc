# Changelog

## [Unreleased]
### Added
- `enrich_ioc` now queries VirusTotal and AbuseIPDB over `requests` when
  `VIRUSTOTAL_API_KEY` / `ABUSEIPDB_API_KEY` are set in `.env`, with timeouts
  and exponential backoff on rate-limit (429) and 5xx responses.
- `api.py`: FastAPI wrapper exposing `POST /triage` and `GET /health`, with
  interactive Swagger docs at `/docs`. Lets a real webhook (n8n, Elastic
  Watcher, Wazuh active response) trigger the same LangGraph pipeline the
  CLI demo uses, instead of only running `orchestrator.py` by hand.
- `tests/test_api.py`: API tests with the graph mocked out, no Ollama required.
- Deployed the API behind a named Cloudflare Tunnel at
  `https://soc-api.aigis-cloud.com`, running as a Windows service on the
  host — no VPS, $0/month.
- Dedicated `n8n` service in `docker-compose.yml` (port 5679) with an
  importable workflow (`n8n/workflow-triage.json`): Webhook -> HTTP
  Request (`POST /triage` over the internal Docker network) -> Respond
  to Webhook. Tested end-to-end with the sample alert.
- GPU passthrough for the containerized `ollama` service (NVIDIA
  Container Toolkit), combined with switching the model to
  `llama3.2:3b` (small enough to fit the 4GB card) — 39.7s vs. 6m17s
  per triage run. GPU passthrough alone, with the previous `llama3.1`
  (8B, doesn't fit the card), was actually *slower* than CPU-only
  (7m26s) — see PROJECT.md Key decisions and the correction below.
- `enrich_ioc` (tools.py) now accepts `indicator` as a list, and splits
  `"host:port"` strings before matching — both are shapes `llama3.2:3b`
  produces that the previous model didn't. Covered by new tests in
  `tests/test_tools.py`.
- Human-approval gate: a new `await_approval` node (`agents.py`) uses
  LangGraph's `interrupt()` to pause the pipeline whenever the report's
  extracted severity is High/Critical. `build_graph()` now compiles with
  a `MemorySaver` checkpointer so pause/resume works. `POST /triage`
  returns `status: "pending_approval"` + `thread_id` for those alerts
  instead of the finished report; a new `POST
  /triage/{thread_id}/approve` endpoint resumes the run. Low/Medium
  severity is unchanged (`status: "completed"` synchronously). 3 new
  tests in `tests/test_api.py`.
### Changed
- Translated the entire repo (docs, comments, docstrings, sample data) to English.
- Dockerfile now runs `uvicorn api:app` by default (port 8000 exposed); the
  original CLI demo is still available via `docker compose exec app python
  orchestrator.py`.
### Corrected
- A prior entry in this changelog (and matching notes in `TODO.md`/
  `PROJECT.md`) claimed GPU passthrough alone gave "~2x faster triage
  runs (3m07s vs. 6m17s CPU-only)". That run never happened — re-testing
  found GPU passthrough alone was actually *slower* (7m26s) with the
  8B model then in use, because it doesn't fit the 4GB card. The real
  speedup came from also switching to `llama3.2:3b` (39.7s). See the
  "Added" entry above and `TODO.md`'s 2026-08-08 note for the full
  timeline.

### Fixed
- Confirmed `.git-broken/` residue is inert (gitignored, no effect on `main`), safe to delete.
- `docker-compose.yml`: remapped the containerized `ollama` service's host
  port from `11434` to `11436` — it failed to bind whenever a native
  Ollama install was already listening on `11434`. The `app` container
  still reaches it via the internal Docker network
  (`OLLAMA_HOST=http://ollama:11434`), so only the host-side mapping
  changed.

## [0.2.0]
### Added
- PROJECT.md, TODO.md, CLAUDE.md, SECURITY.md, .gitignore, .env.example — AI context layer.
- Docker + docker-compose (app + ollama).
- CI: lint (ruff), tests (pytest), Docker image build.

## [0.1.0] - baseline
### Added
- Multi-agent supervisor-worker graph (LangGraph) for alert triage: enrichment,
  research (local RAG), report (functionality that existed before this changelog).
