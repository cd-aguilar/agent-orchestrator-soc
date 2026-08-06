# TODO

## Pending
- [ ] Replace `data/mitre_notes.md` with a real knowledge base
- [ ] Connect `enrich_ioc` to OTX AlienVault or a custom MCP server
- [ ] Test the n8n workflow against a real Elastic/Wazuh alert (so far
      only tested with the sample EDR alert)
- [ ] Publish the triage report to Slack/Obsidian from the n8n workflow
- [ ] Human-approval node before destructive actions
- [ ] Regression set (alert, report) to evaluate prompt/model changes
- [x] Initialize git + push to GitHub as a portfolio piece
- [ ] Add a GIF of the pipeline running to the README

## In progress
- [ ]

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
- [x] Deployed the API behind a Cloudflare Tunnel at
      `https://soc-api.aigis-cloud.com` (named tunnel `SOC_agent`, runs as a
      Windows service on the host, zero cost — no VPS)
- [x] Wired a dedicated n8n instance (`docker-compose.yml`, port 5679) with
      an importable workflow (`n8n/workflow-triage.json`): Webhook
      (`POST /webhook/soc-alert`) -> HTTP Request (`POST /triage` over the
      internal Docker network) -> Respond to Webhook. Tested end-to-end
      with the sample alert, HTTP 200 with the full report.
- [x] GPU passthrough for the containerized `ollama` service (NVIDIA
      Container Toolkit already present on the host) — uncommented the
      `deploy.resources.reservations.devices` stanza in
      `docker-compose.yml`. Confirmed with `nvidia-smi` inside the
      container (GTX 1650 visible) and measured ~2x speedup on a full
      triage run: 3m07s with GPU vs. 6m17s CPU-only.

## Notes (2026-08-06) — GPU passthrough
- Re-enabled the NVIDIA `deploy` stanza in `docker-compose.yml` that was
  left commented out (see 2026-08-04b note below on why the containerized
  `ollama` was CPU-only). No other config needed — the NVIDIA Container
  Toolkit was already installed on the host.
- Verified GPU visibility with `docker exec soc-orchestrator-ollama
  nvidia-smi` (GTX 1650, 4GB VRAM, correctly detected inside the
  container).
- Timed one full triage run end-to-end (`POST /triage` direct, not
  through n8n): **3m07s**, vs. **6m17s** measured CPU-only two days
  earlier with the same sample alert. Still well within the n8n workflow
  node's 900s timeout margin.

## Notes (2026-08-04b) — n8n workflow
- Tried pointing the workflow at the public
  `https://soc-api.aigis-cloud.com/triage` first (matches the original
  ask), but Cloudflare's tunnel proxy aborts the connection if the origin
  is silent for ~100-120s ("Proxy Read Timeout"). A full triage run is 3
  sequential local LLM calls with no streaming, so it never got a chance
  to respond in time.
- Measured a direct call to the dockerized API: **6m17s** for one triage
  run. That's much slower than running Ollama natively on the host —
  the containerized `ollama` service has no GPU access (the NVIDIA
  stanza in `docker-compose.yml` is commented out), so it's CPU-only.
  This host does have a GPU (GTX 1650, 4GB VRAM) currently idle.
- Fix applied: the workflow's HTTP Request node calls `http://app:8000/triage`
  (internal Docker network, since n8n and the API run in the same
  compose stack) instead of the public URL, with a 900s node timeout as
  margin. No Cloudflare hop, no 100s ceiling.
- n8n workflow activation quirk (this n8n version, 2.32.5): `import:workflow`
  always deactivates on import; activating requires `n8n publish:workflow
  --id=<id>` followed by a container restart (`docker compose restart n8n`)
  — a REST `PATCH .../active=true` call did not take effect. Also needed
  an owner account (`POST /rest/owner/setup` + `/rest/login`) since
  `N8N_BASIC_AUTH_ACTIVE` is not honored by this version — that env var is
  effectively a no-op now, left in for parity with the other project's
  n8n but not actually gating access.
- Did not reuse the existing `aigis-n8n` container (different project,
  already has live Slack/Telegram/TheHive credentials) — this project has
  its own n8n service and volume instead. See PROJECT.md Key decisions.

## Notes (2026-08-04)
- Live demo confirmed working end-to-end from the public internet:
  `GET /health` -> `{"status":"ok"}`, `GET /docs` serves Swagger UI. Only
  reachable while the host's Docker Compose stack + `Cloudflared` Windows
  service are both running.
- DNS for `soc-api.aigis-cloud.com` (CNAME -> `<tunnel-id>.cfargotunnel.com`)
  was created automatically by Cloudflare when the tunnel's public hostname
  route was added — `aigis-cloud.com`'s nameservers already point to
  Cloudflare, so no manual DNS edit was needed at the registrar (Hostinger).

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
