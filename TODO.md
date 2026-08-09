# TODO

## Pending
- [ ] Publish the triage report to Slack once this project's n8n has
      credentials (see PROJECT.md's "Dedicated n8n instance" decision).
      Obsidian publishing intentionally not done — would contradict
      ADR-001 (don't mix alert data into the personal vault); a
      `reports/` folder in this repo was built instead (see Done).
- [x] Initialize git + push to GitHub as a portfolio piece

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
- [x] Human-approval node (`await_approval` in `agents.py`) for
      High/Critical severity reports, via LangGraph `interrupt()` +
      `MemorySaver` checkpointer. `POST /triage` returns
      `status="pending_approval"` + `thread_id` instead of the finished
      report; `POST /triage/{thread_id}/approve` resumes it. Low/Medium
      severity is unaffected (still synchronous `status="completed"`).
      Verified end-to-end against the real stack (not mocked): a
      High-severity alert paused correctly, `/approve` resolved it, and
      an unknown `thread_id` 404s. 3 new tests in `tests/test_api.py`.
- [x] Approve step for the n8n workflow (`n8n/workflow-approve.json`):
      Webhook (`POST /webhook/soc-approve`) -> HTTP Request (`POST
      /triage/{thread_id}/approve` over the internal Docker network) ->
      Respond to Webhook. Same import/publish/restart quirk as the
      triage workflow (see 2026-08-04b note). Tested end-to-end: a
      High-severity alert triggered via `POST /triage`, then approved
      via this n8n webhook, returned `status: "completed"`. Still no
      Slack/Teams button — this project's n8n has no chat credentials
      (see PROJECT.md's "Dedicated n8n instance" decision), so approval
      still requires manually calling this webhook or `/docs`.
- [x] Regression set to evaluate prompt/model changes
      (`eval/cases.json` + `eval/run_regression.py`): 5 alerts covering
      the two implemented "escalate to High" paths, one clearly benign
      alert, one ambiguous/no-data alert, and the credential-dumping
      path — checked against real Ollama + real ChromaDB (not mocked),
      not part of `pytest`/CI (no GPU/Ollama there), run manually with
      `python -m eval.run_regression`. See the 2026-08-08 note below for
      the current baseline and what it caught on its first real run.
- [x] Replaced `data/mitre_notes.md`'s 3-technique placeholder with 16
      original entries across Initial Access, Execution, Persistence,
      Privilege Escalation, Defense Evasion, Credential Access,
      Discovery, Lateral Movement, C2, Exfiltration, and Impact —
      written for this project, not copied from HTB Academy course
      material (that's licensed content, not appropriate for a public
      MIT repo) or any vendor source. Rebuilt the Chroma index (both the
      local `chroma_db/` and the container's `chroma_data` volume).
- [x] Connected `enrich_ioc` to OTX AlienVault (`_query_otx` in
      `tools.py`, same pattern as VirusTotal/AbuseIPDB — only runs if
      `OTX_API_KEY` is set in `.env`, reports `pulse_info.count` from
      `GET /indicators/{IPv4,file,domain}/{indicator}/general`). No key
      configured yet (none available this session) — falls back to
      `_FAKE_INTEL_DB` exactly like before until one is added.
- [x] Fixed a real hallucination the KB expansion surfaced: with only 3
      KB docs, `research_node`'s retrieval (k=3) always returned every
      doc regardless of the alert, so it never had room to over-match.
      With 16 techniques, retrieval became genuinely selective — and on
      the `unknown_external_ip_standard_host` eval case, it started
      citing T1071.001's *typical* description ("regular, machine-like
      interval", "sustained spike in outbound bytes") as if those
      specific details were observed in the alert, when the alert only
      said "outbound connection detected... no other suspicious
      activity". Regression eval dropped to 3/5. Fixed by adding an
      explicit instruction to `research_node`'s prompt: the retrieved
      context describes what a technique typically looks like, not this
      alert — only state a specific detail as present if the alert text
      actually says so. Regression eval passed **5/5 on two consecutive
      runs** afterward (including the previously-accepted
      Low-vs-Medium gap). Residual issue, not fully closed: research
      _node's free-text output can still overstate a detail (observed
      once post-fix, "regular interval" again) even though it no longer
      reliably pushes severity up — the downstream severity rule seems
      to compensate better than the root cause is fixed. Left as a
      known soft limitation rather than a fourth prompt-tuning pass;
      same overfitting-risk reasoning as the earlier severity-rule note.
- [x] Publish the triage report to a `reports/` folder in this repo
      (gitignored — real alert data never gets committed) instead of
      Slack/Obsidian: both n8n workflows (`workflow-triage.json`,
      `workflow-approve.json`) now have a Code node ("Build report
      markdown") -> `n8n-nodes-base.convertToFile` (`toText`) ->
      `n8n-nodes-base.readWriteFile` (`write`) chain before "Respond to
      Webhook", writing `/reports/<thread_id>.md`. Required mounting
      `./reports:/reports` on the `n8n` service in `docker-compose.yml`
      and setting `N8N_RESTRICT_FILE_ACCESS_TO=/reports` — n8n's file
      nodes reject writes outside an explicitly allowlisted path by
      default ("Access to the file is not allowed", found by actually
      running it, not from docs). Verified end-to-end: a High-severity
      alert wrote `pending_approval` to the file via the triage webhook,
      then approving via the approve webhook overwrote the same file
      with `status: completed`.
- [x] GIF of the pipeline running, added to the README. `choco install
      ffmpeg` needed admin rights this session didn't have ("Acceso
      denegado" writing to `C:\ProgramData\chocolatey`), and real screen
      recording wasn't reliable/safe to attempt blind anyway (no
      guaranteed visible window, risk of capturing unintended desktop
      content). Used Pillow instead (`pip install pillow`, no admin
      needed) — no video encoder involved. Captured a real transcript
      (`echo y | python orchestrator.py`, fixed a cp1252 mojibake byte
      from Windows' console encoding of the em dash) into
      `docs/cli_demo_transcript.txt`, then `scripts/make_demo_gif.py`
      renders it as a typewriter-effect terminal GIF
      (`docs/demo.gif`, ~7s, 1.4MB) and saves directly via
      `Image.save(..., save_all=True)` — genuinely reproducible, not a
      recording of anything.

## Notes (2026-08-08c) — tested against a real Wazuh/Elasticsearch alert
- The `aigis-detect` stack (sibling project, same host) has a real,
  running Wazuh manager + Elasticsearch (`aigis-wazuh-manager`,
  `aigis-elasticsearch`) monitoring its own `/var/log/dpkg.log`.
  Elasticsearch's `wazuh-alerts-*` indices had no naturally-occurring
  high-severity alert at hand (only routine SCA compliance checks and
  `dpkg` install events), so — reusing the same technique already
  validated in that project's own session notes (`aigis-detect/CLAUDE.md`,
  2026-07-30/31: append realistic-but-synthetic content to a real,
  actively-monitored log file rather than hand-typing a fake alert
  document) — appended two real log lines to the live `dpkg.log`: one
  routine, one referencing PowerShell/Tor/lateral-movement content. Both
  triggered genuine Wazuh detections (rule 2902) and were confirmed
  indexed in Elasticsearch (`wazuh-alerts-2026.08.08`, ids
  `1786223828.249` and `.746`).
- Pulled both real alert documents from Elasticsearch and transformed
  their fields (`rule.id`, `rule.level`, `rule.description`, `agent.name`,
  `location`, `full_log`) into `alert_raw` text — the transform a real
  Elastic Watcher/n8n "Format alert" step would need to do, since Wazuh's
  native JSON schema doesn't match this pipeline's plaintext input.
  POSTed both through the actual n8n webhook (`POST
  /webhook/soc-alert`), not `/triage` directly.
- Routine alert → `status: "completed"`, `severity: "low"`, correct.
- Suspicious alert → `status: "completed"`, `severity: "medium"`
  (not High). Real finding, not a bug: the injected IP had to be written
  as `185-220-101-5` (hyphens) to survive as a valid `dpkg` package name
  field — `tools.py`'s IP detection expects dotted notation, so it
  correctly did *not* match it against `_FAKE_INTEL_DB`'s Tor exit node
  entry. The model still correctly flagged the obfuscated-PowerShell
  wording and cited T1059.001, landing on a defensible Medium rather
  than hallucinating a threat-intel match that didn't actually resolve.
  **Real integration takeaway**: a genuine Wazuh/Elastic integration
  needs IOCs preserved in their native format (dotted IPs, not munged
  into a log-line-safe string) for `enrich_ioc` to match them — worth
  keeping in mind whenever a real "Format alert" transform step is built
  for a live SIEM (see the other still-open "OTX AlienVault" /real KB
  items above).

## Notes (2026-08-09) — third enrich_ioc tool-calling shape: dict
- A separate real-alert test (built independently, not through the
  `aigis-detect` route above): a full nested Wazuh/Sysmon alert JSON
  (`rule.mitre`, `agent`, `data.win.eventdata`, `network.destination`)
  passed as `alert_raw` verbatim, instead of flattened to a log-line
  string first. This is the shape a naive "just forward the raw
  document" n8n transform would produce, as opposed to the field-by-field
  flattening used in the 2026-08-08c test above.
- That richer input surfaced a third `enrich_ioc` tool-calling shape from
  `llama3.2:3b`, beyond the list (`b2671df`) and `"ip:port"` string
  cases already handled: a **dict** of named fields
  (`{"hostname": ..., "ip": ..., "port": 443}`), bundling one entity's
  related fields into a single call. `enrich_ioc` only accepted
  `str | list[str]`, so this failed Pydantic validation and returned a
  502 — same failure class as the earlier list case, different shape.
- Fixed in `tools.py`: `enrich_ioc` now also accepts
  `dict[str, str | int]`, enriching each value individually and labeling
  it by key. Covered by a new test
  (`test_enrich_ioc_accepts_dict_of_named_fields`). Re-ran the same
  nested-JSON alert through the n8n webhook afterward: `HTTP 200`,
  `status: "pending_approval"`, `severity: "high"`, report written to
  `reports/wazuh-92099-001.md` — full pipeline, no crash.
- Takeaway that stacks with 2026-08-08c's: `enrich_ioc`'s job isn't just
  "handle IPs in dotted notation" but "handle whatever calling
  convention this model's tool-use lands on for a given input shape" —
  str, list, or dict are all things `llama3.2:3b` has now actually
  produced depending on how much structure is in the alert text. A
  fourth shape is plausible with a different alert or model; treat this
  as an open-ended robustness surface, not a closed list.

## Notes (2026-08-08) — regression eval baseline
- First real run (before any fix) was 3/5: `enrichment_node` sometimes
  called `enrich_ioc("DC01")` instead of `get_host_criticality("DC01")`
  for a hostname (wrong tool, so the report never surfaced "critical
  asset"); and, more seriously, a confirmed-malicious IP match
  (Tor exit node) in the enrichment didn't reliably push severity to
  High — one case classified a beacon to a known-malicious IP as Low.
- Fix 1: `enrichment_node`'s prompt now explicitly says which tool is
  for what (`enrich_ioc` for IPs/hashes/domains, `get_host_criticality`
  for hostnames) instead of leaving tool selection implicit.
- Fix 2: `report_node`'s prompt got an explicit severity rule that a
  POSITIVE enrichment finding (malicious/Tor/abuse score) must be at
  least High regardless of other context. First retest went to 3/5 in
  the *other* direction — it started reading "No matches in feeds" as
  grounds to escalate too, pushing two genuinely benign/no-data alerts
  to High. Rewrote the rule to explicitly contrast POSITIVE finding vs.
  NO DATA (naming the literal phrases `tools.py` returns, e.g. "No
  matches in feeds"), and telling the model absence of data is not
  evidence of malice. That got it to **4/5**.
- Remaining known gap: `benign_vpn_login` classifies as Medium instead
  of Low (over-caution on a routine VPN login with "no anomalies
  detected" stated explicitly) — a soft calibration miss in the safe
  direction, not a missed detection. Deliberately left as a documented
  baseline gap rather than continuing to tune the prompt against a
  5-case set — the risk of overfitting the prompt to this exact eval
  (rather than improving general judgment) outweighs closing one
  Low-vs-Medium borderline call. **4/5 is the accepted baseline**; a
  future run should be compared against this, not against 5/5.

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
