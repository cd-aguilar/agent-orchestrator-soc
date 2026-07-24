# TODO

## Pending
- [ ] Replace `data/mitre_notes.md` with a real knowledge base
- [ ] Connect `enrich_ioc` to a real API (VirusTotal/AbuseIPDB/OTX) or a custom MCP server
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
