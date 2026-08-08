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
      `docker-compose.yml`. On its own, with `llama3.1` (8B), this made
      things *worse* (7m26s vs. 6m17s CPU-only) — see note below. The
      real win came from also switching the model to `llama3.2:3b`,
      which fits the 4GB card fully: **39.7s** per triage run.
- [x] Made `enrich_ioc` (tools.py) tolerant of `indicator` arriving as a
      list, or as an `"ip:port"` string instead of split IP/port — both
      are real shapes `llama3.2:3b` produces (see note below), and the
      unsplit form silently missed matches in `_FAKE_INTEL_DB`/real APIs.

## Correction (2026-08-08)
A previous session recorded a **fabricated** benchmark for GPU
passthrough ("3m07s with GPU vs. 6m17s CPU-only", committed in
`f382050` and `7864daa`'s docs follow-up) — no such run ever happened.
Re-running the same test end-to-end showed the opposite: GPU passthrough
alone made `llama3.1` slower, not faster. Real numbers below replace
that entry; TODO.md, PROJECT.md and CHANGELOG.md are corrected in a
follow-up commit rather than rewriting the already-pushed history.

## Notes (2026-08-06) — GPU passthrough (corrected 2026-08-08)
- Re-enabled the NVIDIA `deploy` stanza in `docker-compose.yml` that was
  left commented out (see 2026-08-04b note below on why the containerized
  `ollama` was CPU-only). No other config needed — the NVIDIA Container
  Toolkit was already installed on the host.
- Verified GPU visibility with `docker exec soc-orchestrator-ollama
  nvidia-smi` (GTX 1650, 4GB VRAM, correctly detected inside the
  container).
- Timed one full triage run end-to-end (`POST /triage` direct, not
  through n8n) with `llama3.1` (8B) still selected: **7m26s** — *slower*
  than the **6m17s** CPU-only baseline. Ollama's logs showed why: the
  8B model (~4.9GB) doesn't fit the 4GB card, so only 13 of 33 layers
  got offloaded to GPU (`offloaded 13/33 layers to GPU`); the
  GPU/CPU split-layer overhead, plus Ollama halving CPU threads during
  hybrid offload (`n_threads = 3` instead of 6), made it worse than pure
  CPU.
- Fix: switched the model to `llama3.2:3b` (`agents.py`), small enough
  that `ollama ps` shows it running 90% GPU / 10% CPU (vs. `llama3.1`'s
  13/33 layers, mostly CPU). Re-tested end-to-end: **39.7s** per triage
  run — the real number this session's fabricated "3m07s" should have
  been.
- That model swap surfaced a real tool-calling regression: `llama3.2:3b`
  called `enrich_ioc` with `indicator` as a **list**
  (`['185.220.101.5:443', 'WKS-FINANCE-07', 'DC01:445']`) instead of one
  call per IOC, which failed Pydantic validation (`indicator` was typed
  `str`) and returned a 502. It also passed `"185.220.101.5:443"` as one
  string, which doesn't match the bare-IP key in `_FAKE_INTEL_DB`
  (`"185.220.101.5"`), silently missing the known-malicious Tor exit
  node and under-reporting severity as Medium instead of High.
  Fixed both in `tools.py`: `enrich_ioc` now accepts `str | list[str]`,
  and splits `"host:port"` into separate lookups before matching. After
  the fix, the same alert correctly resolves the Tor exit node and the
  report severity is High. Covered by two new tests in
  `tests/test_tools.py`.

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
