# Security

## Context
This project processes security alerts and IOCs. Today it runs 100%
locally (Ollama + mocked threat intel), but the roadmap includes
connecting real threat intel APIs and, eventually, actions against real
hosts (isolate, block IP).

## Practices to maintain
- No real threat intel key ever hardcoded — use `.env` (see
  `.env.example`) as soon as `_FAKE_INTEL_DB` gets replaced with a real
  API.
- Don't wire up any node that performs destructive actions (host
  isolation, IP blocking, etc.) without a human-approval node in front of
  it — this is a design requirement, not just a best practice, for an
  agent that operates on real security infrastructure.
- If real HTB content ever gets ingested into `data/`, apply the same
  rule as in `_rag_project`: never publish that content to a public repo.

## Reporting an issue
Open a private issue or contact cdario.a@gmail.com.
