# Instructions for Claude Code

Before any task:
1. Read PROJECT.md in full.
2. Read TODO.md.
3. If `../AI/GlobalContext.md` exists, read it. Don't duplicate it here.

## How to run this
No Makefile. Everything runs with:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.2:3b
ollama pull nomic-embed-text
python ingest_kb.py       # builds the RAG index (once, or whenever data/ changes)
python orchestrator.py    # runs the triage
```

## Project rules
- Never commit `chroma_db/` or a future `.env` with real keys.
- If a real threat intel API gets connected, add error/rate-limit
  handling and document the decision in PROJECT.md.
- Don't add a node that performs destructive actions (isolate a host,
  block an IP) without the human-approval node first — see Roadmap in
  PROJECT.md.
- When finishing a task: update TODO.md and CHANGELOG.md.

## Conventions
- Commits: Conventional Commits (feat:, fix:, docs:, chore:).
- Code/comment language: English. Documentation: English.
