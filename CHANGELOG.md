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
- `enrich_ioc` also now accepts `indicator` as a dict of named fields
  (`{"hostname": ..., "ip": ..., "port": 443}`) — a third tool-calling
  shape, surfaced by feeding a full nested Wazuh/Sysmon alert JSON
  through the pipeline unflattened (previous real-alert testing had
  flattened fields to a log-line string first, which avoided this
  shape). Without the fix this returned a 502 on a real High-severity
  alert. Covered by a new test; see TODO.md's 2026-08-09 note.
- Human-approval gate: a new `await_approval` node (`agents.py`) uses
  LangGraph's `interrupt()` to pause the pipeline whenever the report's
  extracted severity is High/Critical. `build_graph()` now compiles with
  a `MemorySaver` checkpointer so pause/resume works. `POST /triage`
  returns `status: "pending_approval"` + `thread_id` for those alerts
  instead of the finished report; a new `POST
  /triage/{thread_id}/approve` endpoint resumes the run. Low/Medium
  severity is unchanged (`status: "completed"` synchronously). 3 new
  tests in `tests/test_api.py`.
- `n8n/workflow-approve.json`: a second n8n workflow (Webhook
  `POST /webhook/soc-approve` -> HTTP Request `POST
  /triage/{thread_id}/approve` -> Respond to Webhook), mirroring the
  existing triage workflow, so the approval gate above is reachable from
  a SIEM/webhook flow and not only `/docs`/`curl`. Tested end-to-end.
- `eval/cases.json` + `eval/run_regression.py`: a regression eval — 5
  fixed alerts run against the real graph (real Ollama, real ChromaDB),
  checked for severity/approval-gate/enrichment properties rather than
  exact text. Run manually (`python -m eval.run_regression`), not part
  of CI. Current baseline: 4/5, later 5/5 — see PROJECT.md Key decisions
  for what the first real run caught and how the prompts were tightened.
- Report publishing to a `reports/` folder in this repo (gitignored),
  from both n8n workflows: Code node (build markdown) -> `convertToFile`
  (`toText`) -> `readWriteFile` (`write`), writing
  `/reports/<thread_id>.md`. Chosen over Slack (no credentials) or
  Obsidian (would contradict ADR-001 — see PROJECT.md Key decisions).
  Needed `N8N_RESTRICT_FILE_ACCESS_TO=/reports` on the `n8n` service —
  n8n's file nodes reject writes outside an explicit allowlist by
  default.
- `docs/demo.gif` for the README: `scripts/make_demo_gif.py` renders a
  real captured transcript (`docs/cli_demo_transcript.txt`, from
  `python orchestrator.py`) as a typewriter-effect terminal GIF using
  Pillow's GIF encoder — no screen recording, no ffmpeg.
### Validated
- Tested the n8n webhook against a real Wazuh/Elasticsearch alert (not
  just the sample EDR text): triggered two genuine detections on a
  sibling project's live Wazuh stack, pulled the real alert documents
  from Elasticsearch, transformed their native JSON into `alert_raw`,
  and POSTed through `POST /webhook/soc-alert`. Confirmed real-schema
  handling end-to-end; found that `enrich_ioc`'s IP matching needs
  dotted notation, so a real "Format alert" transform must preserve IOC
  formatting. See TODO.md's 2026-08-08c note.
- `data/mitre_notes.md`: replaced the 3-technique placeholder with 16
  original entries across Initial Access through Impact — written for
  this project, not copied from any vendor or course material.
- `enrich_ioc` now also queries OTX AlienVault (`_query_otx`, same
  pattern as VirusTotal/AbuseIPDB) when `OTX_API_KEY` is set in `.env`.
### Changed (prompts)
- `enrichment_node`'s prompt now explicitly states which tool is for
  what (`enrich_ioc` for IPs/hashes/domains, `get_host_criticality` for
  hostnames), after the regression eval caught it calling `enrich_ioc`
  on a bare hostname.
- `report_node`'s prompt now has an explicit severity rule contrasting a
  POSITIVE enrichment finding (malicious/Tor/abuse score → severity at
  least High) against NO DATA (e.g. "No matches in feeds" → not evidence
  of malice, don't escalate on it alone) — the regression eval caught a
  confirmed-malicious IOC not reliably escalating severity.
- `research_node`'s prompt now explicitly warns that the retrieved KB
  context describes a technique's *typical* behavior, not necessarily
  this alert — after expanding the KB to 16 techniques made retrieval
  genuinely selective (previously it always returned all 3 docs), it
  started citing unstated details (e.g. "regular interval") as if
  observed. Regression eval went 4/5 → 3/5 → 5/5 (two consecutive runs)
  across this KB expansion and fix — see PROJECT.md Key decisions.
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
