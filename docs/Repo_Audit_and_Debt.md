# Repository Audit & Technical Debt Report — PiBot

## Document Metadata

- **Title:** Repository Audit & Technical Debt Report — PiBot
- **Purpose:** Capture current technical debt inventory and prioritized remediation guidance for the PiBot repository.
- **Last Updated:** 2026-06-26
- **Source Prompt:** User request: "update all files in /docs/ to be compliant with the attached file"
- **Source Documents Used:** `docs/json/prompt_header.json`, `docs/Prompt_Header.md`, `docs/json/system_manifest.json`
- **Source Implementation Analyzed:** `docs/`
- **Related Documents:** `docs/json/prompt_header.json`, `docs/Prompt_Header.md`, `docs/json/repo_audit_and_debt.json`, `docs/json/system_manifest.json`
- **Assumptions:** Compliance is satisfied by including the required fields defined in `docs/json/prompt_header.json` under `documentation_generation_rules.required_fields`.
- **Revision History:**
  - 2026-06-26: Added Prompt Header compliance metadata block.

## 1) Executive Summary
PiBot presents a dual-runtime architecture: a PC-side orchestration/UI stack (`pc/`) and Pi-side UDP edge streamers (`pi/`), with `pibot_config.py` + `pibot.env` as centralized configuration input.  
Current state is operationally viable but carries meaningful debt in runtime resilience and observability.

## 2) Repository Topology & Active Inventory
Cross-referencing `docs/json/system_manifest.json` with physical layout:

| Area | Manifest Signal | Filesystem Signal | Audit Result |
|---|---|---|---|
| Module inventory | 33 modules declared | 33/33 paths exist | Consistent |
| PC runtime | `pc/client.py`, `pc/operator_console_app.py`, `pc/services/*`, `pc/video/*` | Present and wired as main app | Active |
| Pi runtime | `pi/mic_udp_streamer.py`, `pi/video_udp_streamer.py`, `pi/audio/*`, `pi/video/*` | Present and executable | Active |
| Cross-cutting config | `pibot_config.py` | Present; loaded by PC + Pi entrypoints | Active SSOT config loader |
| Archive scope | `archives/pc/*` listed in manifest | Present (5 modules incl. typo shims) | Legacy debt retained in manifest |

## 3) Dead Code & Wiring Gaps Analysis
**Target:** `pc/services/thread_monitor.py`

- Present in manifest, but with no runtime caller wiring in `OperatorConsoleApp`.
- `ThreadMonitor` class is implemented but not instantiated by active PC runtime.
- Current long-lived workers are started manually in `connect()` with no watchdog supervision.

Recommended integration:
1. Instantiate `ThreadMonitor` in `OperatorConsoleApp`.
2. Register audio/whisper/ollama/video worker threads with restart callbacks.
3. Start monitor during connect lifecycle and stop during disconnect/on_close.
4. Surface monitor status in UI for operator visibility.

## 4) Legacy & Archived Debt Identification
`archives/pc/` includes stale compatibility artifacts including typo shims:
- `mic_udp_reciever.py`
- `video_udp_reciever.py`

Remediation:
- De-scope archived modules from active runtime inventory.
- Move old shims to explicit legacy namespace or remove if no retention need.
- Add a clear archival lifecycle policy in docs.

## 5) Infrastructure & Telemetry Debt
### Process Supervision Constraint
`pc/services/pi_streamer_manager.py` relies on SSH shell actions plus PID files (`.run/*_streamer.pid`) and `kill -0`.

Limitations:
- Stale PID ambiguity
- Weak lifecycle semantics
- Limited failure-state diagnostics

### Telemetry Gaps
Current health model is mostly passive recency-based.

Missing baselines:
- Active latency/jitter tracking
- Pi host CPU/memory telemetry
- First-class error counters for decode/drop/SSH failures

## 6) Prioritized Technical Debt Remediation Roadmap
| Priority | Horizon | Action | Expected Outcome | Effort |
|---|---|---|---|---|
| Critical | 0–1 sprint | Wire `ThreadMonitor` into `OperatorConsoleApp` | Worker self-healing and faster runtime recovery | 4–6h |
| High | 1 sprint | Replace PID/`kill -0` supervision with systemd-managed streamers | Deterministic lifecycle and richer status | 8–12h |
| High | 1 sprint | Wire heartbeat state to app-level network health + add thread health panel | Improved liveness accuracy and operability | 4–6h |
| Medium | 1–2 sprints | Add latency/jitter, Pi resource telemetry, and explicit counters | Actionable observability | 6–10h |
| Low | 1 sprint | Archive cleanup and manifest de-scoping | Lower maintenance noise | 2–4h |
