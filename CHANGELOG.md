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
### Changed
- Translated the entire repo (docs, comments, docstrings, sample data) to English.
- Dockerfile now runs `uvicorn api:app` by default (port 8000 exposed); the
  original CLI demo is still available via `docker compose exec app python
  orchestrator.py`.
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
