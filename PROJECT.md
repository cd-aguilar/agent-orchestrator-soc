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
report, 100% local (Ollama + ChromaDB), with a 16-technique original
knowledge base (`data/mitre_notes.md`) and threat intel enrichment
(`tools.py`) — real VirusTotal/AbuseIPDB/OTX AlienVault lookups when API
keys are configured, mocked (`_FAKE_INTEL_DB`) otherwise.
Includes a real trigger via a dedicated n8n instance (Webhook -> `POST
/triage` -> Respond to Webhook, see `n8n/workflow-triage.json`).
Includes a human-approval gate: a High/Critical report pauses the graph
(`POST /triage` returns `status="pending_approval"`) until `POST
/triage/{thread_id}/approve` resolves it — reachable either directly or
via a second n8n workflow (`n8n/workflow-approve.json`).
Includes a regression eval (`eval/cases.json` + `eval/run_regression.py`)
that runs a fixed set of alerts against the real graph and checks
severity/approval-gate/enrichment properties — current baseline is 5/5
(see Key decisions and TODO.md's 2026-08-08 notes for what got it there).
Includes report publishing to a `reports/` folder in this repo
(gitignored) from both n8n workflows, instead of Slack/Obsidian — see
Key decisions.
Not yet included: a real OTX API key (code is wired, just unconfigured);
publishing to Slack (no chat credentials in this project's n8n).
Obsidian publishing was deliberately *not* done, since writing alert
data into the personal vault would contradict ADR-001.

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
- **Regression eval as a script against the real stack, not mocked
  pytest cases**: `eval/run_regression.py` runs 5 fixed alerts through
  `build_graph()` with real Ollama/ChromaDB and checks structural
  properties (severity in an expected set, whether the approval gate
  fired, enrichment contains expected substrings) — not exact-text
  matching, since LLM output isn't stable across runs. Deliberately
  separate from `pytest`/CI, which mock the graph and have no
  Ollama/GPU available; run manually after a prompt or model change.
  First real run (3/5) caught two genuine quality regressions:
  `enrichment_node` sometimes called `enrich_ioc` on a hostname instead
  of `get_host_criticality`, and a confirmed-malicious IOC didn't
  reliably escalate severity to High. Tightening the prompts (explicit
  tool-selection guidance; an explicit POSITIVE-finding-vs-NO-DATA
  severity rule, since a first attempt at the severity rule
  overcorrected and pushed benign/no-data alerts to High too) got to
  4/5, accepted at the time as a baseline rather than chased further
  (see the KB-expansion entry below for how it later reached 5/5 for a
  different reason).
- **Expanding the KB from 3 to 16 techniques regressed the eval to 3/5,
  for a new reason — RAG-induced hallucination**: with only 3 docs,
  `research_node`'s k=3 retrieval always returned every doc regardless
  of the alert, so there was no room to over-match. With 16 real
  techniques, retrieval became genuinely selective, and on one eval
  case it started citing a technique's *typical* description ("regular,
  machine-like interval", "sustained spike in outbound bytes") as if
  those specific details were present in an alert that only said
  "outbound connection detected... no other suspicious activity".
  Fixed by telling `research_node`'s prompt explicitly that the
  retrieved context describes what a technique typically looks like,
  not this alert — only state a detail as present if the alert text
  actually says so. Regression eval passed 5/5 on two consecutive runs
  afterward. Not fully closed: `research_node`'s free text can still
  overstate a detail on occasion even though it no longer reliably
  pushes severity up with it — left as a known soft limitation rather
  than a fourth prompt-tuning pass, same overfitting-risk reasoning as
  above.
- **OTX AlienVault wired the same way as VirusTotal/AbuseIPDB, not
  behind a different pattern**: `_query_otx` in `tools.py` only runs if
  `OTX_API_KEY` is set, reports `pulse_info.count` from
  `GET /indicators/{type}/{indicator}/general`, and falls back to
  `_FAKE_INTEL_DB` like the others when unset or when the call fails —
  no key configured yet, this session had none available.
- **`data/mitre_notes.md` expanded with original content, not copied
  from the vault's HTB Academy notes**: the vault has substantial real
  MITRE/threat-hunting notes (`05-Blue-Team/`), but those are HTB course
  material — licensed content not appropriate to redistribute in a
  public MIT-licensed repo. Wrote 16 original technique entries instead
  (same style as the previous 3), covering the tactics a SOC triage tool
  actually needs: Initial Access through Impact.
- **Report publishing goes to a `reports/` folder in this repo, not
  Slack/Obsidian**: Slack has no credentials in this project's n8n (see
  the dedicated-n8n-instance decision below), and writing alert data
  into the personal Obsidian vault would directly contradict ADR-001
  (kept alert data and personal notes in separate trust boundaries on
  purpose). Both n8n workflows got a Code node (build markdown) ->
  `convertToFile` (`toText`) -> `readWriteFile` (`write`) chain before
  "Respond to Webhook", writing `/reports/<thread_id>.md` (mounted from
  `./reports` on the host, gitignored). Needed
  `N8N_RESTRICT_FILE_ACCESS_TO=/reports` — n8n's file nodes reject
  writes outside an explicit allowlist by default; this wasn't
  documented anywhere obvious, found by running it and reading the
  error ("Access to the file is not allowed").
- **Tested against a real Wazuh/Elasticsearch alert, not just synthetic
  ones**: the sibling `aigis-detect` project (same host) runs a real
  Wazuh manager + Elasticsearch. Triggered two genuine alerts on its
  live `dpkg.log` monitoring, pulled the real documents from
  Elasticsearch, transformed their native JSON fields into `alert_raw`
  text, and POSTed through this project's actual n8n webhook. Confirmed
  the pipeline handles real Wazuh schema end-to-end, and surfaced a real
  integration requirement: `enrich_ioc`'s IP detection needs dotted
  notation, so any real "Format alert" step feeding this pipeline must
  preserve IOCs in native format rather than embedding them in a
  log-line-safe string. See TODO.md's 2026-08-08c note.

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
- [x] Replace `data/mitre_notes.md`'s placeholder with a real (original,
      not copied) 16-technique knowledge base.
- [x] Connect `tools.py` to real APIs (VirusTotal, AbuseIPDB) with
      rate-limit handling and `.env` keys.
- [x] Connect `tools.py` to OTX AlienVault — code wired (`_query_otx`),
      no `OTX_API_KEY` configured yet.
- [x] Expose the pipeline over HTTP (`api.py`, `POST /triage`, Swagger at
      `/docs`) so it can be triggered by a webhook instead of the CLI only.
- [x] Deploy it somewhere reachable: `https://soc-api.aigis-cloud.com`, via
      a named Cloudflare Tunnel to the local Docker Compose stack.
- [x] Wire an actual n8n workflow (Webhook -> HTTP Request ->
      `POST /triage` on the internal Docker network -> Respond to
      Webhook), running as its own service in `docker-compose.yml`.
- [x] Test that n8n workflow against a real Wazuh/Elasticsearch alert
      (not just the sample EDR text) — see Key decisions.
- [x] Publish the triage report — to a `reports/` folder in this repo
      (see Key decisions). Slack still pending (no credentials);
      Obsidian was ruled out (see Scope).
- [x] "Awaiting human approval" node for High/Critical reports
      (`await_approval` in `agents.py`, `POST /triage/{thread_id}/approve`
      in `api.py`), plus an n8n webhook for it
      (`n8n/workflow-approve.json`). Still no node takes a real
      destructive action, and there's no chat (Slack/Teams) button —
      natural next step once report publishing (above) exists.
- [x] Regression set (alert, report) to measure triage quality across
      prompt/model changes — `eval/cases.json` + `eval/run_regression.py`,
      run manually against the real stack. Baseline: **4/5** (see Key
      decisions).
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
