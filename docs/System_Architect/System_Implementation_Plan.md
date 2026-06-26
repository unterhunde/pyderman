# System Implementation Plan — PiBot

## Document Metadata

- **Title:** System Implementation Plan — PiBot
- **Version:** 1.0
- **Purpose:** Define the phased implementation roadmap for completing, integrating, and validating the PiBot system based on the June 2026 architecture audit findings.
- **Last Updated:** 2026-06-26
- **Source Prompt:** User request: "Create a comprehensive System Implementation Plan based on the architecture audit results."
- **Source Documents Used:**
  - `docs/json/system_manifest.json`
  - `docs/System_Architecture_and_Interface_Control_Document.md`
  - `docs/System_Diagnostic_and_Troubleshooting_Guide.md`
  - `docs/Repo_Audit_and_Debt.md`
- **Source Implementation Analyzed:** `pc/`, `pi/`, `tests/`, `pibot_config.py`, `requirements.txt`
- **Related Documents:**
  - `docs/System_Architecture_and_Interface_Control_Document.md`
  - `docs/System_Diagnostic_and_Troubleshooting_Guide.md`
  - `docs/Repo_Audit_and_Debt.md`
  - `docs/json/system_manifest.json`
- **Assumptions:**
  - All 33 documented modules exist on disk and parse without errors (verified 2026-06-26).
  - Hardware Pi is not available in the development environment; Pi-side validation requires physical device or simulation.
  - `pibot.env` is the documented default configuration path but is absent from the repository.
  - `ThreadMonitor` is the only active module that is code-complete but not wired into runtime.
  - `pibot.env` is not committed to version control by policy; its absence does not indicate lost functionality but is a deployment gap.

---

## Revision History

| Version | Date       | Author           | Change Summary                            |
|---------|------------|------------------|-------------------------------------------|
| 1.0     | 2026-06-26 | System Architect | Initial creation from June 2026 audit.    |

---

## 1. Executive Summary

The June 2026 architecture audit established:

| Metric                              | Result            |
|-------------------------------------|-------------------|
| Files physically present            | 100% (33/33)      |
| Active modules parse-clean          | 100% (28/28)      |
| Active modules wired into runtime   | 96.4% (27/28)     |
| Runtime configuration file present  | FAIL (missing)    |
| Archive modules functional          | N/A (intentional) |

The system is **near-complete**. All source files exist and are syntactically valid. One active module (`ThreadMonitor`) is implemented but not connected to the runtime. The `pibot.env` configuration file is absent. Structural technical debt exists in process supervision and observability.

The dominant risks are:
1. Worker crash storms with no self-healing (ThreadMonitor not wired)
2. Ambiguous Pi streamer lifecycle via stale PID files
3. No active telemetry for latency, jitter, or error rates
4. Missing `pibot.env` deployment artifact

This plan assigns every remaining item to a phase, agent, and task, moving the system from its current 96.4% wired state to full operational readiness.

---

## 2. Audit Findings Summary

### 2.1 Implementation Gaps (Action Required)

| ID  | Finding                                         | Severity | Module(s) Affected                         |
|-----|-------------------------------------------------|----------|--------------------------------------------|
| G-1 | `ThreadMonitor` not wired into runtime          | Critical | `pc/services/thread_monitor.py`, `pc/operator_console_app.py` |
| G-2 | `pibot.env` absent from deployment              | High     | `pibot_config.py`, all services            |
| G-3 | PID/`kill -0` supervision is stale-prone        | High     | `pc/services/pi_streamer_manager.py`       |
| G-4 | No active latency/jitter/error counters         | Medium   | `pc/services/audio_receiver.py`, `pc/video/receiver_widget.py` |
| G-5 | ThreadMonitor thread listed in manifest but never started | Medium | `system_manifest.json` threads section |
| G-6 | Archive modules included in active manifest scope | Low    | `archives/pc/`                             |
| G-7 | No integration tests for video pipeline        | Medium   | `pc/video/`, `pi/video/`                   |
| G-8 | No integration tests for audio pipeline        | Medium   | `pc/services/audio_receiver.py`, `pi/audio/` |

### 2.2 Confirmed Working (No Action Required)

| Area                                  | Status             |
|---------------------------------------|--------------------|
| PC GUI bootstrap (`client.py`)        | Wired and active   |
| Audio receive/resample pipeline       | Wired and active   |
| Whisper transcription pipeline        | Wired and active   |
| Ollama streaming LLM pipeline         | Wired and active   |
| Video receive/reassemble/render       | Wired and active   |
| YOLO inference engine                 | Wired and active   |
| Pi mic streamer (entrypoint + modules)| Wired and active   |
| Pi video streamer (entrypoint + modules) | Wired and active|
| SSH streamer control                  | Wired and active   |
| Startup checks                        | Wired and active   |
| RuntimeConfig thread-safe toggles     | Wired and active   |
| Logging bridge to GUI                 | Wired and active   |
| PromptSubmission envelope             | Wired and active   |
| FrameBuffer chunk assembly            | Wired and active   |

---

## 3. Component Dependency Map

```
pibot_config.py
  └── pc/client.py
        └── pc/operator_console_app.py
              ├── pc/runtime_config.py
              ├── pc/logging_utils.py
              ├── pc/services/startup_checks.py
              ├── pc/services/audio_receiver.py ──► pc/runtime_config.py
              ├── pc/services/whisper_service.py ──► pc/services/prompt_submission.py
              ├── pc/services/ollama_service.py ──► pc/services/prompt_submission.py
              ├── pc/services/pi_streamer_manager.py ──► [SSH] pi/mic_udp_streamer.py
              │                                       └── [SSH] pi/video_udp_streamer.py
              ├── pc/video/receiver_widget.py ──► pc/video/frame_buffer.py
              │                               ──► pc/video/inference_engine.py
              │                               ──► pc/video/protocol.py
              └── [NOT WIRED] pc/services/thread_monitor.py  ◄── G-1 GAP

pi/mic_udp_streamer.py ──► pi/audio/streamer.py ──► pi/audio/config.py
                                                 ──► pi/audio/device_selection.py
                                                 ──► pi/audio/protocol.py
                                                 ──► pi/audio/signal_processing.py

pi/video_udp_streamer.py ──► pi/video/streamer.py ──► pi/video/config.py
                                                   ──► pi/video/frame_source.py
                                                   ──► pi/video/protocol.py
```

**Critical dependency for G-1:** `ThreadMonitor` must be instantiated after `OperatorConsoleApp` creates worker threads in `connect()`, and stopped before `disconnect()` / `on_close()`.

---

## 4. Phased Implementation Roadmap

---

### Phase 1 — Critical Blockers

**Objective:** Eliminate the two blockers that prevent safe production operation: missing runtime self-healing and missing configuration bootstrap.

| Task ID | Task                                                       | Priority | Effort  |
|---------|------------------------------------------------------------|----------|---------|
| T-001   | Wire `ThreadMonitor` into `OperatorConsoleApp`             | P0       | 4–6 h   |
| T-002   | Create `pibot.env.example` template with all config keys   | P0       | 1 h     |
| T-003   | Add `pibot.env` to `.gitignore` with deployment note       | P0       | 0.5 h   |
| T-004   | Validate `ThreadMonitor` restart callbacks for audio/whisper/ollama/video threads | P0 | 2–3 h |

**Components Involved:**
- `pc/services/thread_monitor.py`
- `pc/operator_console_app.py`
- `pibot_config.py`
- `.gitignore`, `SETUP.md`

**Interfaces Affected:**
- Connect/Disconnect lifecycle in `OperatorConsoleApp`
- Thread ownership model (all worker threads)

**Expected Deliverables:**
- `ThreadMonitor` instantiated and running during connected state
- Worker threads registered with restart callbacks
- `pibot.env.example` committed to repository root
- `SETUP.md` updated with configuration bootstrap instructions

**Success Criteria:**
- [ ] `ThreadMonitor` starts when `connect()` is called
- [ ] `ThreadMonitor` stops when `disconnect()` or `on_close()` is called
- [ ] `ThreadMonitor.get_status()` returns meaningful state for all registered threads
- [ ] `pibot.env.example` contains all 14 config keys documented in `system_manifest.json`
- [ ] Application starts normally with a copied `pibot.env`

**Risks:**
- Restart callbacks must not double-start threads already alive; logic must guard against it
- `ThreadMonitor` interval must be tuned to avoid restart storms on slow model loads (Whisper, YOLO)

**Responsible Agent:** Systems Integration Engineer + GUI Engineer

---

### Phase 2 — Runtime Integration

**Objective:** Close remaining integration gaps in process supervision, surface `ThreadMonitor` status in the GUI, and harden the SSH streamer lifecycle.

| Task ID | Task                                                                                  | Priority | Effort  |
|---------|---------------------------------------------------------------------------------------|----------|---------|
| T-005   | Surface `ThreadMonitor` health in the bottom status bar                               | P1       | 2–3 h   |
| T-006   | Replace stale-PID supervision with atomic PID-write + `kill -0` + fallback `pgrep`   | P1       | 3–4 h   |
| T-007   | Add SSH command retry (max 1 retry) to `PiStreamerManager`                            | P1       | 2 h     |
| T-008   | Add structured SSH failure codes to differentiate connection fail vs. process fail    | P1       | 2 h     |
| T-009   | Update `system_manifest.json` `threads` entry to reflect ThreadMonitor wiring state  | P1       | 0.5 h   |

**Components Involved:**
- `pc/services/thread_monitor.py`
- `pc/services/pi_streamer_manager.py`
- `pc/operator_console_app.py`

**Interfaces Affected:**
- Streamer tab GUI controls (SSH action feedback)
- Bottom status bar (thread health panel)
- `PiStreamerManager.query_status()` and `run_action()` return contracts

**Expected Deliverables:**
- Thread health indicator visible in operator console
- `PiStreamerManager` returns unambiguous status codes
- At least one SSH retry on timeout

**Success Criteria:**
- [ ] Bottom status bar shows thread health (alive/dead/restarting) for each worker
- [ ] SSH timeout returns distinguishable status vs. process-not-found
- [ ] PID file write/read is atomic (write to temp, rename)
- [ ] `system_manifest.json` updated with new ThreadMonitor `called_by` entry

**Risks:**
- GUI threading constraint: all Tk updates must go through `Tk.after()` or the UI queue
- SSH retry must respect existing timeout budget (12/20 s per interface spec)

**Responsible Agent:** Systems Integration Engineer + GUI Engineer

---

### Phase 3 — Functional Validation

**Objective:** Establish automated test coverage for the audio, whisper, and video pipelines.

| Task ID | Task                                                                              | Priority | Effort  |
|---------|-----------------------------------------------------------------------------------|----------|---------|
| T-010   | Write unit tests for `ThreadMonitor` register/start/stop/get_status              | P1       | 2 h     |
| T-011   | Write unit tests for `PiStreamerManager` status parsing and error branches        | P1       | 3 h     |
| T-012   | Write integration test for audio pipeline (UDP send → resample → queue)          | P2       | 4 h     |
| T-013   | Write integration test for video pipeline (chunk send → reassemble → frame ready)| P2       | 4 h     |
| T-014   | Extend existing Whisper tests to cover silence timeout boundary                   | P2       | 2 h     |
| T-015   | Verify `pibot.env.example` keys match `AppSettings` defaults in `pibot_config.py`| P1       | 1 h     |

**Components Involved:**
- `tests/`
- `pc/services/thread_monitor.py`
- `pc/services/pi_streamer_manager.py`
- `pc/services/audio_receiver.py`
- `pc/video/`
- `pc/services/whisper_service.py`

**Interfaces Affected:**
- `tests/test_whisper_service.py` (extension)
- New test files in `tests/`

**Expected Deliverables:**
- 6 new or extended test files in `tests/`
- All tests passing in CI-equivalent run

**Success Criteria:**
- [ ] `ThreadMonitor` unit tests cover all four public methods
- [ ] Audio pipeline test confirms resampling from 48 kHz to 16 kHz produces correct shape
- [ ] Video pipeline test confirms `FrameBuffer.assemble()` produces complete JPEG bytes from valid chunk sequence
- [ ] All existing tests continue to pass

**Risks:**
- Pi-side audio tests require mock PyAudio if hardware unavailable
- Video pipeline test requires synthetic JPEG chunking fixtures

**Responsible Agent:** Verification & Test Engineer

---

### Phase 4 — System Integration

**Objective:** Validate end-to-end system behavior across PC ↔ Pi boundary using all active interfaces.

| Task ID | Task                                                                                          | Priority | Effort   |
|---------|-----------------------------------------------------------------------------------------------|----------|----------|
| T-016   | Deploy updated PC runtime and verify connect/disconnect lifecycle with ThreadMonitor active   | P1       | 2–3 h    |
| T-017   | Start Pi mic and video streamers via SSH; verify PC receives audio and video                  | P1       | 2 h      |
| T-018   | Trigger Whisper → Ollama pipeline with live audio; verify transcript + LLM response           | P1       | 2 h      |
| T-019   | Enable YOLO inference; verify frame overlay and inference stats                               | P1       | 1 h      |
| T-020   | Simulate worker crash; verify `ThreadMonitor` restarts thread within expected interval        | P1       | 2 h      |
| T-021   | Verify startup checks pass with correct `pibot.env` and fail gracefully with bad values       | P1       | 1 h      |

**Components Involved:** All active runtime modules across `pc/` and `pi/`

**Interfaces Affected:** All network interfaces (UDP 5000, UDP 5001, SSH 22, HTTP 11434)

**Expected Deliverables:**
- Signed-off end-to-end test checklist
- Any discovered defects filed and resolved before Phase 5

**Success Criteria:**
- [ ] All 4 network interfaces operational simultaneously
- [ ] `ThreadMonitor` demonstrably restarts a killed worker
- [ ] GUI status bar accurately reflects all component states
- [ ] No orphaned threads or sockets on disconnect

**Risks:**
- Pi hardware dependency — requires physical device or sufficiently realistic emulation
- Whisper model load time (~10 s) may interact with ThreadMonitor restart timing

**Responsible Agent:** Systems Integration Engineer

---

### Phase 5 — Verification & Validation

**Objective:** Independent review of implementation completeness, interface compliance, and documentation accuracy.

| Task ID | Task                                                                                    | Priority | Effort |
|---------|-----------------------------------------------------------------------------------------|----------|--------|
| T-022   | Cross-check every manifest module entry against actual implementation                   | P1       | 3 h    |
| T-023   | Audit every GUI control in SAICD against live `operator_console_app.py`                 | P1       | 2 h    |
| T-024   | Verify all interface packet formats (AUDIO_HEADER, CHUNK_HEADER, HEARTBEAT_PACKET)      | P1       | 2 h    |
| T-025   | Confirm all config keys in `AppSettings` are documented in manifest                     | P1       | 1 h    |
| T-026   | Review `ThreadMonitor` wiring against architectural intent in SAICD                     | P1       | 1 h    |
| T-027   | Update `system_manifest.json` and SAICD to reflect all Phase 1–4 changes               | P1       | 2 h    |
| T-028   | Update Diagnostic Guide with ThreadMonitor failure-mode and recovery playbook           | P1       | 2 h    |

**Components Involved:** All documentation under `docs/`, all active source modules

**Expected Deliverables:**
- Updated `system_manifest.json` reflecting post-Phase-4 state
- Updated SAICD and Diagnostic Guide
- V&V checklist signed off

**Success Criteria:**
- [ ] Zero discrepancies between manifest and implementation
- [ ] All GUI controls in SAICD match live code
- [ ] All packet formats in SAICD match struct definitions in protocol modules
- [ ] Diagnostic Guide includes ThreadMonitor failure-mode section

**Responsible Agent:** Verification & Test Engineer + Documentation Engineer

---

### Phase 6 — Performance Optimization

**Objective:** Address observability gaps and process supervision quality without changing functional interfaces.

| Task ID | Task                                                                                           | Priority | Effort   |
|---------|------------------------------------------------------------------------------------------------|----------|----------|
| T-029   | Add per-packet latency and jitter tracking to `AudioReceiverService`                          | P2       | 4 h      |
| T-030   | Add per-frame decode time and drop rate counters to `UDPVideoReceiver`                        | P2       | 3 h      |
| T-031   | Add explicit SSH failure/success counters to `PiStreamerManager`                              | P2       | 2 h      |
| T-032   | Evaluate `systemd` unit files as replacement for PID-file-based streamer supervision on Pi    | P2       | 6–8 h    |
| T-033   | Expose latency/jitter/error counters in bottom status bar or diagnostics panel                | P2       | 3 h      |

**Components Involved:**
- `pc/services/audio_receiver.py`
- `pc/video/receiver_widget.py`
- `pc/services/pi_streamer_manager.py`
- `pc/operator_console_app.py`

**Interfaces Affected:**
- Status bar data model (new counter fields)
- Pi systemd units (new deployment artifact if T-032 adopted)

**Expected Deliverables:**
- Latency/jitter/counter instrumentation in audio and video pipelines
- Decision document for systemd adoption (yes/no + rationale)

**Success Criteria:**
- [ ] `AudioReceiverService` exposes per-chunk latency and rolling jitter
- [ ] `UDPVideoReceiver` exposes per-frame decode time and cumulative drop count
- [ ] Counters visible in operator UI or logs
- [ ] `systemd` recommendation documented

**Risks:**
- systemd on Pi requires Pi OS configuration access; scope may exceed this repository boundary
- New counter fields must not block existing UI rendering path

**Responsible Agent:** Streaming Engineer + Systems Integration Engineer

---

### Phase 7 — Release Readiness

**Objective:** Confirm the system meets all pre-release criteria: documentation complete, tests green, no open critical/high items.

| Task ID | Task                                                                                   | Priority | Effort |
|---------|----------------------------------------------------------------------------------------|----------|--------|
| T-034   | Final pass: de-scope or annotate archive modules in `system_manifest.json`             | P2       | 1 h    |
| T-035   | Confirm `requirements.txt` covers all runtime imports for both PC and Pi              | P2       | 1 h    |
| T-036   | Update `SETUP.md` with full deployment walkthrough (copy `pibot.env.example`, SSH keys, Ollama) | P1 | 2 h |
| T-037   | Tag repository at `v1.0.0` with annotated release notes                               | P1       | 0.5 h  |
| T-038   | Archive Phase 1–7 task closure report in `docs/System_Architect/`                     | P2       | 1 h    |

**Components Involved:** `SETUP.md`, `requirements.txt`, `system_manifest.json`, `docs/`

**Expected Deliverables:**
- Clean `v1.0.0` release tag
- Complete `SETUP.md` deployment guide
- Closed-out task list

**Success Criteria:**
- [ ] All P0 and P1 tasks closed
- [ ] All tests passing
- [ ] `SETUP.md` sufficient to bootstrap a fresh deployment without oral knowledge
- [ ] `system_manifest.json` matches the tagged implementation state

**Responsible Agent:** Documentation Engineer + System Architect

---

## 5. Project Health Summary

### Overall Status

| Dimension                          | Value              | Notes                                              |
|------------------------------------|--------------------|----------------------------------------------------|
| Implementation completeness        | **96.4%**          | 27/28 active modules fully wired                   |
| Architectural compliance           | **High**           | `/pc/` and `/pi/` separation maintained; composition root intact |
| Open critical blockers             | **2**              | G-1 (ThreadMonitor), G-2 (pibot.env)               |
| Open high-risk items               | **2**              | G-3 (PID supervision), G-4 (no telemetry)          |
| Documentation accuracy             | **High**           | Manifest self-aware of all gaps; no phantom modules |
| Test coverage                      | **Partial**        | Whisper and e2e tests exist; audio/video pipeline tests missing |

### Current Blockers

| Blocker | Impact | Required Action |
|---------|--------|-----------------|
| `ThreadMonitor` not wired | Worker crashes are unrecovered; operator must manually reconnect | T-001, T-004 |
| `pibot.env` missing | Fresh deployments fail without manual env setup; no documented template | T-002, T-003, T-036 |

### High-Risk Items

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Stale PID file causes `PiStreamerManager` to report wrong state | Medium | Operator sees "running" for a dead streamer | T-006, T-007, T-008 |
| Whisper/YOLO model load time triggers premature ThreadMonitor restart | Medium | Restart storm on startup | Tune ThreadMonitor startup delay in T-004 |
| SSH key or network not configured in deployment | High | All Pi features non-functional | T-036 (SETUP.md) |
| Audio or video pipeline test gap conceals regression | Medium | Silent breakage after refactor | T-012, T-013 |

### Recommended Next Action

**Immediately assign T-001 (Wire ThreadMonitor) and T-002 (pibot.env.example) to the Systems Integration Engineer.** These are the only items that block safe production operation and can be completed in a single sprint.

---

## 6. Engineering Task Queue

All remaining tasks in priority order for assignment by the Systems Integration Engineer.

| # | Task ID | Description                                                          | Phase | Priority | Effort  | Agent                       | Depends On |
|---|---------|----------------------------------------------------------------------|-------|----------|---------|-----------------------------|------------|
| 1 | T-001   | Wire `ThreadMonitor` into `OperatorConsoleApp`                       | 1     | P0       | 4–6 h   | Systems Integration / GUI   | —          |
| 2 | T-002   | Create `pibot.env.example` template                                  | 1     | P0       | 1 h     | Systems Integration         | —          |
| 3 | T-003   | Add `pibot.env` to `.gitignore` with deployment note                 | 1     | P0       | 0.5 h   | Systems Integration         | T-002      |
| 4 | T-004   | Validate `ThreadMonitor` restart callbacks for all worker threads     | 1     | P0       | 2–3 h   | Systems Integration / GUI   | T-001      |
| 5 | T-005   | Surface `ThreadMonitor` health in bottom status bar                   | 2     | P1       | 2–3 h   | GUI Engineer                | T-001      |
| 6 | T-006   | Replace stale-PID supervision with atomic write + fallback `pgrep`   | 2     | P1       | 3–4 h   | Systems Integration         | —          |
| 7 | T-007   | Add SSH command retry (max 1) to `PiStreamerManager`                  | 2     | P1       | 2 h     | Systems Integration         | T-006      |
| 8 | T-008   | Add structured SSH failure codes                                      | 2     | P1       | 2 h     | Systems Integration         | T-007      |
| 9 | T-009   | Update `system_manifest.json` threads section (ThreadMonitor wired)  | 2     | P1       | 0.5 h   | Documentation Engineer      | T-001      |
|10 | T-010   | Unit tests for `ThreadMonitor`                                        | 3     | P1       | 2 h     | Verification & Test         | T-001      |
|11 | T-011   | Unit tests for `PiStreamerManager` status/error branches              | 3     | P1       | 3 h     | Verification & Test         | T-006      |
|12 | T-015   | Verify `pibot.env.example` keys match `AppSettings`                  | 3     | P1       | 1 h     | Verification & Test         | T-002      |
|13 | T-021   | Startup check pass/fail with valid/invalid `pibot.env`                | 4     | P1       | 1 h     | Verification & Test         | T-002      |
|14 | T-016   | Deploy and verify connect/disconnect with ThreadMonitor active        | 4     | P1       | 2–3 h   | Systems Integration         | T-001, T-004 |
|15 | T-017   | Start Pi streamers via SSH; verify PC receives audio/video            | 4     | P1       | 2 h     | Systems Integration         | T-006      |
|16 | T-018   | Whisper → Ollama pipeline with live audio                             | 4     | P1       | 2 h     | Systems Integration         | T-016      |
|17 | T-019   | Enable YOLO; verify frame overlay + stats                             | 4     | P1       | 1 h     | Systems Integration         | T-016      |
|18 | T-020   | Simulate worker crash; verify ThreadMonitor restart                   | 4     | P1       | 2 h     | Verification & Test         | T-016      |
|19 | T-022   | Cross-check manifest vs. implementation                               | 5     | P1       | 3 h     | Verification & Test         | T-009      |
|20 | T-023   | Audit SAICD GUI controls vs. live code                                | 5     | P1       | 2 h     | Verification & Test         | T-005      |
|21 | T-024   | Verify all interface packet formats                                    | 5     | P1       | 2 h     | Verification & Test         | —          |
|22 | T-025   | Confirm all config keys documented in manifest                        | 5     | P1       | 1 h     | Verification & Test         | T-002      |
|23 | T-026   | Review ThreadMonitor wiring vs. architectural intent                  | 5     | P1       | 1 h     | Verification & Test         | T-001      |
|24 | T-027   | Update manifest and SAICD for Phase 1–4 changes                      | 5     | P1       | 2 h     | Documentation Engineer      | T-009      |
|25 | T-028   | Update Diagnostic Guide: ThreadMonitor playbook                       | 5     | P1       | 2 h     | Documentation Engineer      | T-001      |
|26 | T-036   | Update `SETUP.md` with full deployment walkthrough                    | 7     | P1       | 2 h     | Documentation Engineer      | T-002      |
|27 | T-012   | Integration test: audio pipeline (UDP → resample → queue)             | 3     | P2       | 4 h     | Verification & Test         | —          |
|28 | T-013   | Integration test: video pipeline (chunks → reassemble → frame)        | 3     | P2       | 4 h     | Verification & Test         | —          |
|29 | T-014   | Extend Whisper tests: silence timeout boundary                        | 3     | P2       | 2 h     | Verification & Test         | —          |
|30 | T-029   | Add latency/jitter tracking to `AudioReceiverService`                 | 6     | P2       | 4 h     | Streaming Engineer          | —          |
|31 | T-030   | Add frame decode time and drop rate to `UDPVideoReceiver`             | 6     | P2       | 3 h     | Streaming Engineer          | —          |
|32 | T-031   | Add SSH failure/success counters to `PiStreamerManager`               | 6     | P2       | 2 h     | Streaming Engineer          | T-006      |
|33 | T-033   | Expose counters in status bar or diagnostics panel                    | 6     | P2       | 3 h     | GUI Engineer                | T-029, T-030 |
|34 | T-032   | Evaluate `systemd` for Pi streamer supervision                        | 6     | P2       | 6–8 h   | Systems Integration         | T-006      |
|35 | T-034   | De-scope archive modules in `system_manifest.json`                    | 7     | P2       | 1 h     | Documentation Engineer      | —          |
|36 | T-035   | Confirm `requirements.txt` covers all PC and Pi imports               | 7     | P2       | 1 h     | Verification & Test         | —          |
|37 | T-037   | Tag repository at `v1.0.0`                                            | 7     | P1       | 0.5 h   | System Architect            | All P1     |
|38 | T-038   | Archive Phase 1–7 closure report                                      | 7     | P2       | 1 h     | Documentation Engineer      | T-037      |

**Total estimated effort:** ~85–105 engineering hours across 7 phases.

---

## 7. Cross-Reference: Recommendations vs. Source Documents

| Task(s)        | System Manifest               | SAICD Reference                   | Diagnostic Guide Reference              | Audit Report Reference           |
|----------------|-------------------------------|-----------------------------------|-----------------------------------------|----------------------------------|
| T-001, T-004   | `thread_monitor` notes: "not wired" | §3 Utilities: "not currently wired" | N/A (no playbook exists yet)          | §3 Dead Code & Wiring Gaps       |
| T-002, T-003   | `repository.current_scope` lists `pibot.env` | §3 Configuration layer        | N/A                                     | §5 Infrastructure Debt           |
| T-005          | `threads.ThreadMonitor` present | §5 ICD: status bar widget         | N/A                                     | §3                               |
| T-006, T-007   | `pi_streamer_manager` PID note  | §5 ICD: SSH interface failure behavior | §Streamer lifecycle playbook       | §5 Process Supervision Constraint |
| T-012, T-013   | `audio_receiver`, `receiver_widget` modules | §5 Network interfaces     | Audio/video pipeline diagrams           | §5 Telemetry Gaps                |
| T-022, T-027   | All modules                   | Full SAICD                        | Full Diagnostic Guide                   | §2 Active Inventory              |
| T-028          | N/A                           | N/A                               | Failure-mode section (missing)          | §3                               |
| T-032          | `pi_streamer_manager` responsibilities | §5 SSH interface               | Streamer control lifecycle diagram      | §5 Process Supervision           |

---

## 8. Next Agent Handoff

**Recommended Next Agent:** Systems Integration Engineer

**Required Input Documents:**
- `docs/System_Architect/System_Implementation_Plan.md` (this document)
- `docs/System_Architecture_and_Interface_Control_Document.md`
- `docs/json/system_manifest.json`

**Requested Outputs:**
```
docs/Systems_Integration/
├── Integration_Plan.md
├── Task_001.md        (T-001: Wire ThreadMonitor)
├── Task_002.md        (T-002: pibot.env.example)
├── Task_003.md        (T-003: .gitignore update)
└── Master_Task_List.md
```

**Handoff Instructions:**
1. Decompose Phase 1 tasks (T-001 through T-004) into engineering work packages.
2. Assign each task to the appropriate specialized agent from the available agent roster.
3. Define acceptance criteria for each task (mirror the Success Criteria tables in §4 Phase 1).
4. Create individual task assignment documents (`Task_001.md` through `Task_003.md`).
5. Create `Master_Task_List.md` covering all 38 tasks from the Engineering Task Queue (§6).
6. Begin execution of T-001 (wire `ThreadMonitor`) as the first work package.
