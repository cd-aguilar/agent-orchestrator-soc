# Changelog

## [Unreleased]
### Added
- `enrich_ioc` now queries VirusTotal and AbuseIPDB over `requests` when
  `VIRUSTOTAL_API_KEY` / `ABUSEIPDB_API_KEY` are set in `.env`, with timeouts
  and exponential backoff on rate-limit (429) and 5xx responses.
### Changed
- Translated the entire repo (docs, comments, docstrings, sample data) to English.
### Fixed
- Confirmed `.git-broken/` residue is inert (gitignored, no effect on `main`), safe to delete.
### Status
- `main` clean and in sync with `origin/main`. No open changes.

## [0.2.0]
### Added
- PROJECT.md, TODO.md, CLAUDE.md, SECURITY.md, .gitignore, .env.example — AI context layer.
- Docker + docker-compose (app + ollama).
- CI: lint (ruff), tests (pytest), Docker image build.

## [0.1.0] - baseline
### Added
- Multi-agent supervisor-worker graph (LangGraph) for alert triage: enrichment,
  research (local RAG), report (functionality that existed before this changelog).
