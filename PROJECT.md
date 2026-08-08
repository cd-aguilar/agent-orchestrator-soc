# PROJECT.md — Context for AI

> Read this file first, in full, before exploring the repo or proposing changes.
> If `AI/GlobalContext.md` exists in the user's workspace, read that too.

## Goal
Multi-agent system (supervisor-worker pattern with LangGraph) for automated
security alert triage: enriches IOCs, searches a local knowledge base (RAG
over MITRE/runbook/HTB notes), and writes a triage report with severity and
recommended action. Portfolio piece for AI Engineer / Detection Engineer /
Security Automation Engineer roles.

## Scope
Includes: supervisor graph → enrichment (tool calling) → research (RAG) →
report, 100% local (Ollama + ChromaDB), with sample data
(`data/mitre_notes.md`) and threat intel enrichment (`tools.py`) — real
VirusTotal/AbuseIPDB lookups when API keys are configured, mocked
(`_FAKE_INTEL_DB`) otherwise.
Includes a real trigger via a dedicated n8n instance (Webhook -> `POST
/triage` -> Respond to Webhook, see `n8n/workflow-triage.json`).
Includes a human-approval gate: a High/Critical report pauses the graph
(`POST /triage` returns `status="pending_approval"`) until `POST
/triage/{thread_id}/approve` resolves it.
Not yet included: OTX AlienVault, publishing the report to
Slack/Obsidian, evaluation with a regression set, an n8n/Slack step for
the approval gate itself (currently only reachable via `/docs` or
`curl`). See Roadmap.

## Architecture
The supervisor decides the next step based on accumulated state; each
worker does exactly one thing (enrichment, research, report) and returns
to the supervisor. Full diagram in README.md.

## Key decisions
- **LangGraph over a manual loop**: explicit typed state, conditional
  branching, a pattern used in production by AI Engineering teams.
- **Ollama (local model), not an external API**: zero cost, and security
  alerts (sensitive data) never leave the machine — reusable across the
  "second brain" stack.
- **Embedded ChromaDB**: zero infrastructure for local RAG.
- **Native tool calling, no manual prompt parsing**: more reliable, the
  same pattern used with MCP.
- **FastAPI wrapper (`api.py`) around `build_graph()`, not a rewrite**:
  `orchestrator.py`'s CLI entry point is untouched, so the pipeline has
  two entry points (CLI, HTTP) sharing one graph. FastAPI was picked over
  a bare Flask/webhook receiver because it gets request validation
  (Pydantic) and Swagger UI (`/docs`) for free — no extra work, and it
  matches the pattern used in `rag-api-cloud`.
- **Real threat intel with a mock fallback, not an all-or-nothing swap**:
  `enrich_ioc` calls VirusTotal/AbuseIPDB (via `requests`, with timeout and
  exponential backoff on 429/5xx) only when `VIRUSTOTAL_API_KEY` /
  `ABUSEIPDB_API_KEY` are set in `.env`; with no keys, or if a call errors
  or returns no data, it falls back to `_FAKE_INTEL_DB`. This keeps the
  demo runnable offline/without keys while still being production-capable.
- **Cloudflare Tunnel over a VPS to expose the API**: the pipeline needs
  Ollama (real CPU/RAM), which doesn't fit a serverless free tier, and a
  VPS running 24/7 costs money. A named Cloudflare Tunnel keeps the app
  100% local (Docker Compose on the host) while giving it a stable public
  hostname (`soc-api.aigis-cloud.com`) — zero additional infrastructure
  cost, consistent with this project's "$0/month, fully reproducible"
  positioning. Tradeoff: it's only reachable while the host machine and
  the `Cloudflared` Windows service are both running, not true 24/7 uptime.
- **n8n calls the API over the internal Docker network, not the public
  tunnel URL**: the `n8n` service (added to `docker-compose.yml`) points
  its HTTP Request node at `http://app:8000/triage`, not
  `https://soc-api.aigis-cloud.com/triage`. Reason: Cloudflare's tunnel
  proxy kills a request if the origin sends nothing back for ~100-120s,
  and a full triage run (3 sequential local LLM calls) took 6+ minutes in
  testing — well past that ceiling — so the public URL is only usable for
  short-lived/external calls (a SIEM outside this host, manual `curl`,
  `/docs`), not for the orchestrator that lives on the same machine.
- **Dedicated n8n instance for this project, not the existing `aigis-n8n`
  container**: this machine already runs an n8n (`aigis-n8n`, port 5678)
  for a different project, with its own Slack/Telegram/TheHive
  credentials. Reusing it would mix an unrelated project's secrets into
  this portfolio piece's docker-compose, so this project gets its own
  `n8n` service (port 5679, own volume) instead.
- **GPU passthrough alone was not enough — the model had to fit the
  card**: uncommenting the `deploy.resources` stanza in
  `docker-compose.yml` (NVIDIA Container Toolkit already present on the
  host) made `llama3.1` (8B) *slower* (7m26s vs. 6m17s CPU-only): the
  4GB GTX 1650 only fit 13 of 33 layers, and the GPU/CPU split-layer
  overhead plus Ollama halving CPU threads during hybrid offload made it
  worse than pure CPU. Switching the model to `llama3.2:3b` (small
  enough to run mostly on-GPU) is what delivered the real speedup:
  **39.7s** per triage run. See TODO.md's 2026-08-06 note and its
  2026-08-08 correction for the full story, including a fabricated
  "3m07s" benchmark from an earlier session that never actually ran and
  has since been corrected here.
- **`enrich_ioc` accepts `str | list[str]`, and splits `"host:port"`
  before matching**: switching to `llama3.2:3b` surfaced two real
  tool-calling quirks — it sometimes batches multiple IOCs into one
  call as a list instead of one call per IOC, and passes `"ip:port"` as
  a single string, which doesn't match the bare-IP/bare-port keys used
  by `_FAKE_INTEL_DB` and the real APIs. Both are now handled in
  `tools.py` rather than assuming a specific model's calling style,
  since a weaker/smaller model producing either shape is expected
  behavior, not an edge case.
- **Human-approval gate via LangGraph `interrupt()`, not a separate
  workflow/state machine**: a new `await_approval` node calls
  `interrupt()` when `report_node` extracts a High/Critical severity from
  the report text (`agents.py`'s `_extract_severity`, regex over the
  "Severity: ..." line, defaults to "high" — i.e. fails closed — if the
  model didn't follow the format). The graph is compiled with
  `MemorySaver` (`orchestrator.py`) so the pause/resume actually works;
  `api.py` exposes it as `POST /triage` (returns `status:
  "pending_approval"` + `thread_id` instead of hanging) and `POST
  /triage/{thread_id}/approve` (resumes via `Command(resume=...)`).
  Low/Medium severity is unaffected — same synchronous `status:
  "completed"` response as before, so the existing n8n workflow keeps
  working for those. `MemorySaver` is in-process only: a pending approval
  is lost if the API restarts before someone calls `/approve` — fine for
  a demo, not for production (needs a persistent checkpointer).

## Constraints
- IOC enrichment uses real APIs (VirusTotal, AbuseIPDB) when keys are
  configured in `.env`, and `_FAKE_INTEL_DB` in tools.py otherwise — keys
  must never be hardcoded, only read from `.env` (see `.env.example`).
- Human approval (`await_approval` node) only gates the *triage report*
  reaching `status: "completed"` for High/Critical alerts — there is
  still no node that takes a real destructive action (isolate a host,
  block an IP). Don't wire one up without routing it through this same
  gate first.

## Roadmap
- [ ] Replace `data/mitre_notes.md` with real notes (HTB, Elastic rules,
      vault export).
- [x] Connect `tools.py` to real APIs (VirusTotal, AbuseIPDB) with
      rate-limit handling and `.env` keys.
- [ ] Connect `tools.py` to OTX AlienVault or your own MCP servers.
- [x] Expose the pipeline over HTTP (`api.py`, `POST /triage`, Swagger at
      `/docs`) so it can be triggered by a webhook instead of the CLI only.
- [x] Deploy it somewhere reachable: `https://soc-api.aigis-cloud.com`, via
      a named Cloudflare Tunnel to the local Docker Compose stack.
- [x] Wire an actual n8n workflow (Webhook -> HTTP Request ->
      `POST /triage` on the internal Docker network -> Respond to
      Webhook), running as its own service in `docker-compose.yml`.
- [ ] Publish the triage report to Slack/Obsidian from that n8n workflow.
- [x] "Awaiting human approval" node for High/Critical reports
      (`await_approval` in `agents.py`, `POST /triage/{thread_id}/approve`
      in `api.py`). Still no node takes a real destructive action, and
      the n8n workflow doesn't yet have an approve step of its own (only
      reachable via `/docs`/`curl`) — natural next step once report
      publishing (above) exists.
- [ ] Regression set (alert, report) to measure triage quality across
      prompt/model changes.
- [x] GPU passthrough for the containerized `ollama` service, combined
      with switching to a GPU-sized model (`llama3.2:3b`) — 39.7s vs.
      6m17s per triage run. (GPU passthrough alone, with the old
      `llama3.1`, was actually slower — see Key decisions.)

## Open items
See TODO.md

## Technologies
Python, LangGraph, LangChain (langchain-ollama, langchain-chroma), Ollama
(llama3.2:3b + nomic-embed-text), ChromaDB.

## Project rules
- Never commit `chroma_db/` (derived index, rebuilt with `ingest_kb.py`).
- Once real threat intel APIs are connected, the key goes in `.env` (see
  `.env.example`), never hardcoded in `tools.py`.
- Any relevant architecture change gets documented here, under "Key
  decisions".
- Commits: Conventional Commits (feat:, fix:, docs:, chore:).
