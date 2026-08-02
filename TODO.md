# TODO

## Pending
- [ ] Replace `data/mitre_notes.md` with a real knowledge base
- [ ] Connect `enrich_ioc` to OTX AlienVault or a custom MCP server
- [ ] Real trigger via n8n (SIEM/Elastic webhook) + report publishing (Slack/Obsidian)
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

## Notes (2026-08-02)
- `.git-broken/` is a leftover from a failed git init, already gitignored — not blocking anything, can be deleted with `rm -rf .git-broken`.
- `enrich_ioc` (tools.py) now hits VirusTotal / AbuseIPDB when `VIRUSTOTAL_API_KEY` /
  `ABUSEIPDB_API_KEY` are set in `.env`; with no keys configured it behaves exactly as
  before (mocked `_FAKE_INTEL_DB`), so existing tests are unaffected.
- OTX AlienVault is still not wired up — left for a follow-up.
