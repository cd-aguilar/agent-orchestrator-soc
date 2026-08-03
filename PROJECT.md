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
Not yet included: OTX AlienVault, a real trigger via SIEM/n8n,
human-in-the-loop before destructive actions, evaluation with a
regression set. See Roadmap.

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

## Constraints
- IOC enrichment uses real APIs (VirusTotal, AbuseIPDB) when keys are
  configured in `.env`, and `_FAKE_INTEL_DB` in tools.py otherwise — keys
  must never be hardcoded, only read from `.env` (see `.env.example`).
- No human-in-the-loop yet: don't wire this up to real destructive
  actions (isolate a host, block an IP) without adding that approval node
  first.

## Roadmap
- [ ] Replace `data/mitre_notes.md` with real notes (HTB, Elastic rules,
      vault export).
- [x] Connect `tools.py` to real APIs (VirusTotal, AbuseIPDB) with
      rate-limit handling and `.env` keys.
- [ ] Connect `tools.py` to OTX AlienVault or your own MCP servers.
- [x] Expose the pipeline over HTTP (`api.py`, `POST /triage`, Swagger at
      `/docs`) so it can be triggered by a webhook instead of the CLI only.
- [ ] Wire an actual n8n workflow (webhook from SIEM/Elastic) against
      `POST /triage` + publish the report to Slack/Obsidian.
- [ ] "Awaiting human approval" node before destructive actions.
- [ ] Regression set (alert, report) to measure triage quality across
      prompt/model changes.

## Open items
See TODO.md

## Technologies
Python, LangGraph, LangChain (langchain-ollama, langchain-chroma), Ollama
(llama3.1 + nomic-embed-text), ChromaDB.

## Project rules
- Never commit `chroma_db/` (derived index, rebuilt with `ingest_kb.py`).
- Once real threat intel APIs are connected, the key goes in `.env` (see
  `.env.example`), never hardcoded in `tools.py`.
- Any relevant architecture change gets documented here, under "Key
  decisions".
- Commits: Conventional Commits (feat:, fix:, docs:, chore:).
