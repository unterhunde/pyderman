# System Implementation Plan — PiBot

## Document Metadata

- **Title:** System Implementation Plan — PiBot
- **Purpose:** Define the prioritized engineering roadmap to resolve active technical debt, complete unwired infrastructure, and improve system observability and resilience.
- **Last Updated:** 2026-06-26
- **Source Prompt:** User request: "create an implementation plan"
- **Source Documents Used:**
  - `docs/json/system_manifest.json`
  - `docs/Repo_Audit_and_Debt.md`
  - `docs/System_Architecture_and_Interface_Control_Document.md`
  - `docs/Prompt_Header.md`
- **Source Implementation Analyzed:**
  - `pc/client.py`
  - `pc/operator_console_app.py`
  - `pc/services/thread_monitor.py`
  - `pc/services/audio_receiver.py`
  - `pc/services/whisper_service.py`
  - `pc/services/ollama_service.py`
  - `pc/services/pi_streamer_manager.py`
  - `pc/video/receiver_widget.py`
  - `tests/`
- **Related Documents:**
  - `docs/json/system_manifest.json`
  - `docs/Repo_Audit_and_Debt.md`
  - `docs/System_Architecture_and_Interface_Control_Document.md`
  - `docs/System_Diagnostic_and_Troubleshooting_Guide.md`
- **Assumptions:**
  - The active PC runtime is `pc/client.py` → `OperatorConsoleApp` as the composition root.
  - `pc/services/thread_monitor.py` is fully implemented and correct; only wiring is missing.
  - Systemd availability on the Raspberry Pi is assumed for Phase 2 streamer management.
  - All changes must preserve the `/pc/` and `/pi/` directory separation.
  - No functionality shall be duplicated across subsystems.
- **Revision History:**
  - 2026-06-26: Initial creation.

---

## 1. Executive Summary

PiBot is operationally viable but carries four areas of unresolved technical debt that limit runtime resilience, operability, and observability:

1. **Thread supervision gap** — `ThreadMonitor` is fully implemented but never instantiated.
2. **Weak streamer lifecycle** — Pi streamers are managed via SSH PID-file polling, which is fragile under stale-PID and crash-recovery conditions.
3. **Thread health not surfaced** — The GUI has no panel reflecting individual worker thread liveness.
4. **Observability deficits** — No latency/jitter tracking, no Pi resource telemetry, and no first-class error counters.

This plan resolves each item in priority order across five engineering phases. Each phase produces a working, tested, and documented increment.

---

## 2. System Baseline

### 2.1 Active Module Inventory

| Module | Status |
|---|---|
| `pc/client.py` | Active — composition root |
| `pc/operator_console_app.py` | Active — GUI + orchestration |
| `pc/runtime_config.py` | Active — thread-safe toggles |
| `pc/logging_utils.py` | Active — GUI log bridge |
| `pc/services/audio_receiver.py` | Active — UDP audio ingestion |
| `pc/services/whisper_service.py` | Active — speech segmentation + transcription |
| `pc/services/ollama_service.py` | Active — streamed LLM worker |
| `pc/services/pi_streamer_manager.py` | Active — SSH streamer control |
| `pc/services/startup_checks.py` | Active — startup validation |
| `pc/services/thread_monitor.py` | **Implemented but unwired** |
| `pc/services/prompt_submission.py` | Active — typed prompt envelope |
| `pc/video/frame_buffer.py` | Active — frame chunk assembly |
| `pc/video/inference_engine.py` | Active — YOLO inference |
| `pc/video/protocol.py` | Active — video packet constants |
| `pc/video/receiver_widget.py` | Active — UDP video widget |
| `pi/mic_udp_streamer.py` | Active — Pi mic entrypoint |
| `pi/video_udp_streamer.py` | Active — Pi video entrypoint |
| `pi/audio/*` | Active — audio pipeline modules |
| `pi/video/*` | Active — video pipeline modules |
| `pi/audio_diagnostics.py` | Active — standalone diagnostic tool |
| `archives/pc/*` | Legacy — not used by active runtime |

### 2.2 Confirmed Technical Debt

| ID | Priority | Area | Description | Effort |
|---|---|---|---|---|
| TD-01 | Critical | Thread supervision | `ThreadMonitor` never instantiated in `OperatorConsoleApp` | 4–6 h |
| TD-02 | High | Pi lifecycle | SSH/PID-file streamer control is fragile; no deterministic restart semantics | 8–12 h |
| TD-03 | High | GUI observability | No thread health panel; heartbeat-only network state | 4–6 h |
| TD-04 | Medium | Telemetry | No latency/jitter counters, no Pi resource telemetry, no error counters | 6–10 h |
| TD-05 | Low | Maintenance | Archived modules included in manifest; typo shims retained | 2–4 h |

---

## 3. Architecture Constraints

All changes must comply with the following non-negotiable structural rules:

1. **`pc/client.py` remains the sole composition root.** No other entry point may bootstrap the application.
2. **`/pc/` and `/pi/` separation is enforced.** No PC-side code may be deployed to Pi, and no Pi-side code may be imported by the PC runtime.
3. **No functionality duplication.** Extend existing modules before creating new ones.
4. **Every GUI action must accurately reflect real backend state.** Status labels must be driven by verified backend state, not by optimistic assumptions.
5. **Documentation is part of the implementation.** All phase completions must update `system_manifest.json`, the SAICD, and the diagnostics guide before the phase is considered done.

---

## 4. Implementation Phases

---

### Phase 1 — Wire `ThreadMonitor` (TD-01) ✦ Critical

**Goal:** Worker threads `audio_receiver`, `whisper_worker`, and `ollama_worker` are registered with `ThreadMonitor`. Crashed workers are detected and restarted automatically. Monitor lifecycle is tied to `connect()` and `disconnect()`.

**Scope:** `pc/operator_console_app.py` only. `pc/services/thread_monitor.py` is not modified.

#### 1.1 Changes Required

**`pc/operator_console_app.py`**

1. Add import:
   ```python
   from pc.services.thread_monitor import ThreadMonitor
   ```

2. In `__init__`, initialize the monitor after `self.streamer_manager`:
   ```python
   self.thread_monitor: ThreadMonitor | None = None
   ```

3. In `connect()`, after all workers are started, instantiate and register:
   ```python
   self.thread_monitor = ThreadMonitor(logger=self.logger)
   self.thread_monitor.register_thread(
       "audio_receiver",
       self.audio_receiver.thread,
       restart_callback=self._restart_audio_receiver,
   )
   self.thread_monitor.register_thread(
       "whisper_worker",
       self.whisper_worker.thread,
       restart_callback=self._restart_whisper_worker,
   )
   self.thread_monitor.register_thread(
       "ollama_worker",
       self.ollama_worker.thread,
       restart_callback=self._restart_ollama_worker,
   )
   self.thread_monitor.start()
   ```

4. Add private restart methods that re-create and re-start each service with the same arguments used in `connect()`. Each restart callback must return the new `threading.Thread` object.

5. In `disconnect()`, call `self.thread_monitor.stop()` and set `self.thread_monitor = None`.

6. In `on_close()`, ensure `disconnect()` is always called before `root.destroy()` (already the case — no change needed).

#### 1.2 Service Interface Prerequisite

`AudioReceiverService`, `WhisperService`, and `OllamaService` must expose their internal thread object. Audit each service's `start()` method:

- Confirm each service stores its thread as `self._thread` or similar.
- If not already exposed, add `@property def thread(self) -> threading.Thread` to each service class.

#### 1.3 Restart Callback Contract

Each `_restart_*` method must:

1. Check `self.stop_event.is_set()` and return `None` without action if disconnecting.
2. Re-create the service (or call `start()` again if the service supports re-entry).
3. Return the new `threading.Thread` object so `ThreadMonitor` can track it.
4. Log at `WARNING` level that a restart was triggered.

#### 1.4 Validation

- Unit test: mock a dead service thread; verify `ThreadMonitor._check_thread` calls the restart callback and updates the registered thread object.
- Integration: start the app, kill the audio receiver thread via test hook, confirm log shows "Worker thread died: audio_receiver" and "Thread restarted successfully: audio_receiver" within 2 seconds.

#### 1.5 Documentation Updates

- `docs/json/system_manifest.json`: update `thread_monitor.called_by` from `[]` to `["pc/operator_console_app.py"]`.
- `docs/System_Architecture_and_Interface_Control_Document.md` §3 Utilities: update the note from "not currently wired" to "wired into OperatorConsoleApp; monitors audio, whisper, and ollama workers."

---

### Phase 2 — Systemd-Managed Pi Streamers (TD-02) ✦ High

**Goal:** Replace the SSH + PID-file streamer control model with systemd unit files on the Pi. `PiStreamerManager` issues `systemctl` commands over SSH instead of manually managing PID files and background processes.

**Scope:** `pi/` (new systemd unit files), `pc/services/pi_streamer_manager.py` (updated SSH commands). No changes to `pc/operator_console_app.py` public API.

#### 2.1 Pi-Side Changes

Create two systemd user unit files on the Pi:

**`~/.config/systemd/user/pibot-mic.service`**
```ini
[Unit]
Description=PiBot Microphone UDP Streamer
After=network.target

[Service]
WorkingDirectory=%h/pibot
ExecStart=%h/pibot/venv/bin/python -m pi.mic_udp_streamer
Restart=on-failure
RestartSec=3s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

**`~/.config/systemd/user/pibot-video.service`**
```ini
[Unit]
Description=PiBot Video UDP Streamer
After=network.target

[Service]
WorkingDirectory=%h/pibot
ExecStart=%h/pibot/venv/bin/python -m pi.video_udp_streamer
Restart=on-failure
RestartSec=3s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

Deploy with:
```bash
systemctl --user daemon-reload
systemctl --user enable pibot-mic pibot-video
```

#### 2.2 `pc/services/pi_streamer_manager.py` Changes

Replace the PID-file-based shell commands in `run_action()` and `query_status()` with `systemctl --user` equivalents:

| Action | Old Command | New Command |
|---|---|---|
| start mic | background process + PID write | `systemctl --user start pibot-mic` |
| stop mic | `kill $(cat .run/mic_streamer.pid)` | `systemctl --user stop pibot-mic` |
| status mic | `kill -0 $(cat .run/mic_streamer.pid)` | `systemctl --user is-active pibot-mic` |
| start video | analogous | `systemctl --user start pibot-video` |
| stop video | analogous | `systemctl --user stop pibot-video` |
| status video | analogous | `systemctl --user is-active pibot-video` |

`query_status()` must parse `systemctl --user is-active` output: `active` → running, anything else → stopped.

The `(ok: bool, text: str)` return-value contract must not change — `OperatorConsoleApp` depends on this interface.

#### 2.3 Backward Compatibility

PID files in `.run/` become unused. They must not be removed by code (manual cleanup only). Add a comment in `PiStreamerManager` noting the migration.

#### 2.4 Deployment Documentation

Add a `SETUP.md` section "Pi Systemd Service Setup" documenting the unit file deployment steps and the `loginctl enable-linger` requirement for user services.

#### 2.5 Validation

- SSH into Pi; verify `systemctl --user status pibot-mic` reports active after the GUI start action.
- Simulate a crash: `kill -9 <pid>`; verify systemd restarts the streamer within `RestartSec`.
- Verify `query_status` returns `(True, "running")` when active and `(False, "stopped")` when inactive.

#### 2.6 Documentation Updates

- `docs/json/system_manifest.json`: update `pi_streamer_manager.calls_into` to reflect `systemctl` commands.
- SAICD §5 SSH streamer control interface: update protocol description to `systemctl --user`.
- Diagnostics guide: update Pi streamer troubleshooting section.

---

### Phase 3 — Thread Health Panel (TD-03) ✦ High

**Goal:** Surface worker thread liveness in the GUI so the operator can see at a glance whether audio, whisper, ollama, and video receiver threads are healthy. Network health state must reflect heartbeat status more precisely.

**Scope:** `pc/operator_console_app.py` (new UI panel and status polling). No new modules.

#### 3.1 UI Changes

Add a **"Worker Health"** section to the left-panel notebook (new tab after Logs):

| Row | Label | Widget | Values |
|---|---|---|---|
| 0 | Audio Receiver | status label | `running` / `dead` / `idle` |
| 1 | Whisper Worker | status label | `running` / `dead` / `idle` |
| 2 | Ollama Worker | status label | `running` / `dead` / `idle` |
| 3 | Video Receiver | status label | `running` / `dead` / `idle` |

When disconnected, all four show `idle` in `Warn.TLabel` style.

#### 3.2 Polling Loop

Add `_refresh_thread_health()` as a `root.after(2000, ...)` timer loop:

```python
def _refresh_thread_health(self) -> None:
    if self.thread_monitor is not None:
        status = self.thread_monitor.get_status()
        for name, label in self._health_labels.items():
            state = status.get(name, "unknown")
            style = "StatusValue.TLabel" if state == "running" else "Danger.TLabel"
            label.configure(text=state, style=style)
    else:
        for label in self._health_labels.values():
            label.configure(text="idle", style="Warn.TLabel")
    self.root.after(2000, self._refresh_thread_health)
```

Start `_refresh_thread_health()` from `_start_ui_loops()`.

#### 3.3 Video Receiver Health

`UDPVideoReceiver` does not register with `ThreadMonitor` (it manages its own internal loop). Surface its health by checking `self.video_widget is not None` and whether `last_video_packet_time` is recent (< 5 s) when connected.

#### 3.4 Network State Enhancement

Refine the network-online condition in `_refresh_status_bar` to distinguish degraded state:

- `heartbeat_recent` → `"online"` in `StatusValue.TLabel`
- `connected` and `video_recent` but not `heartbeat_recent` → `"degraded"` in `Warn.TLabel`
- Otherwise → `"offline"` in `Danger.TLabel`

#### 3.5 Validation

- Connect the app; verify all four health labels show `running`.
- Stop listening (audio stream paused) — audio label must remain `running` (thread is alive even when idle).
- Disconnect — all labels revert to `idle`.
- Kill a worker thread via test hook — label must show `dead` within 2 seconds.

#### 3.6 Documentation Updates

- SAICD §6 GUI Documentation: add Worker Health tab to the visible components table.
- `docs/json/system_manifest.json`: update `operator_console_app.public_classes.methods` to include any new methods added.

---

### Phase 4 — Observability Enhancements (TD-04) ✦ Medium

**Goal:** Add first-class latency/jitter tracking on the audio path, Pi CPU/memory telemetry, and explicit error counters for decode/drop/SSH failures.

**Scope:** `pc/services/audio_receiver.py`, `pc/services/pi_streamer_manager.py`, `pc/operator_console_app.py`. No new external dependencies beyond `psutil` on Pi.

#### 4.1 Audio Latency Tracker

In `AudioReceiverService.run()`:

- Record `recv_time = time.monotonic()` immediately after `socket.recvfrom()`.
- Compute `inter_packet_delta = recv_time - self._last_recv_time`.
- Accumulate a rolling window of the last 100 deltas (`collections.deque(maxlen=100)`).
- Expose `get_latency_stats() -> dict` returning `{"mean_ms": float, "jitter_ms": float, "drops": int}`.

Surface these in `OperatorConsoleApp` via a `_refresh_audio_stats()` timer loop that updates three new labels in the Audio tab.

#### 4.2 Pi Resource Telemetry

Add `query_pi_resources() -> dict | None` to `PiStreamerManager`:

```python
def query_pi_resources(self) -> dict | None:
    cmd = "python3 -c \"import psutil; print(psutil.cpu_percent(interval=0.2), psutil.virtual_memory().used // (1024*1024))\""
    ok, output = self._ssh(cmd)
    if ok:
        parts = output.strip().split()
        return {"cpu_pct": float(parts[0]), "mem_mb": float(parts[1])}
    return None
```

Add a "Pi Host" section to the bottom status bar with `Pi CPU` and `Pi Mem` labels. Populate via a 5-second `root.after` timer to avoid SSH flooding.

`psutil` must be added to `requirements.txt` under Pi dependencies and documented in `SETUP.md`.

#### 4.3 Error Counters

Add a `stats` dict to `AudioReceiverService` and `UDPVideoReceiver` tracking:

| Counter | Incremented when |
|---|---|
| `packets_received` | Any valid packet arrives |
| `queue_drops` | `queue.Full` on put |
| `decode_errors` | Exception during JPEG decode or PCM parse |

Expose via `get_stats() -> dict`. Surface in the Worker Health tab as a compact stats line.

#### 4.4 SSH Error Counter

In `PiStreamerManager`, add `_ssh_failures: int`. Increment on every failed SSH command. Expose via `get_stats() -> dict`. Surface in the Streamers tab status line.

#### 4.5 Validation

- Verify audio latency stats update in the Audio tab during live streaming.
- Verify Pi CPU/mem labels populate (show `N/A` if Pi is unreachable — acceptable).
- Artificially fill the audio queue; verify `queue_drops` increments and appears in the UI.

#### 4.6 Documentation Updates

- SAICD §5: add `query_pi_resources()` to `PiStreamerManager` interface row.
- `docs/json/system_manifest.json`: update `audio_receiver`, `pi_streamer_manager`, `receiver_widget` entries with new methods.
- Diagnostics guide: add latency/jitter interpretation guidance.

---

### Phase 5 — Archive Cleanup (TD-05) ✦ Low

**Goal:** Remove archived modules from the active runtime manifest inventory. Establish a clear archival lifecycle policy.

**Scope:** `docs/json/system_manifest.json`, `docs/System_Architecture_and_Interface_Control_Document.md`.

#### 5.1 Manifest De-scoping

In `system_manifest.json`, move all `archives/pc/*` entries from the `modules` array into a new top-level `archived_modules` array. Ensure no active module's `called_by` list references an archived path.

#### 5.2 SAICD Lifecycle Policy

Add to SAICD §4 Archived compatibility modules:

> Archived modules are retained for historical reference only. They are not imported by the active runtime and are excluded from test coverage requirements. Modules may be permanently deleted once they have remained unused for two full development cycles.

#### 5.3 Typo Shim Handling

`mic_udp_reciever.py` and `video_udp_reciever.py` are typo shims. Mark them in the archived_modules manifest with `"retention": "legacy_shim_only"`.

#### 5.4 Validation

- `grep -r "archives/" pc/` must return no results.
- `grep -r "archives/" pi/` must return no results.
- Manifest `archived_modules` array must contain exactly 5 entries.

---

## 5. Cross-Phase Dependency Map

```
Phase 1 (ThreadMonitor wiring)
    └─► Phase 3 (Thread Health Panel) — depends on Phase 1

Phase 2 (Systemd streamers)          — independent; parallel with Phase 1/3

Phase 3 (Thread Health Panel)
    └─► Phase 4 (Observability)       — extends the health panel UI

Phase 5 (Archive cleanup)            — independent; any time
```

Recommended execution order: Phase 1 → Phase 3 → Phase 4 (with Phase 2 in parallel after Phase 1).

---

## 6. Testing Requirements

| Phase | Test Type | Scope | Pass Criteria |
|---|---|---|---|
| 1 | Unit | `ThreadMonitor` restart callback invocation | Callback called within 2 s of thread death; new thread registered |
| 1 | Integration | `OperatorConsoleApp.connect()` → monitor start | Monitor thread alive after connect; stopped after disconnect |
| 2 | Integration (Pi) | `PiStreamerManager` systemctl commands | `query_status` returns `(True, "running")` when service is active |
| 2 | Integration (Pi) | Crash recovery | Streamer restarts within `RestartSec` after kill |
| 3 | UI | Worker Health tab labels | Labels match `thread_monitor.get_status()` within 2 s |
| 4 | Unit | `AudioReceiverService.get_latency_stats()` | Returns correct mean/jitter from synthetic delta list |
| 4 | Integration | Pi resource query | Returns dict with `cpu_pct` and `mem_mb` keys on reachable Pi |
| 5 | Static | `grep -r "archives/" pc/` | Zero matches |

All existing tests in `tests/` must remain green after every phase.

---

## 7. Documentation Completion Checklist

After all phases are complete, the following documents must be updated:

| Document | Required Updates |
|---|---|
| `docs/json/system_manifest.json` | Phase 1: wire thread_monitor; Phase 2: pi_streamer_manager calls_into; Phase 3: new GUI methods; Phase 4: new service methods; Phase 5: archive restructure |
| `docs/System_Architecture_and_Interface_Control_Document.md` | Phase 1: ThreadMonitor wired; Phase 2: SSH interface updated; Phase 3: health panel; Phase 4: observability; Phase 5: lifecycle policy |
| `docs/System_Diagnostic_and_Troubleshooting_Guide.md` | Phase 2: systemd troubleshooting steps; Phase 4: latency/jitter interpretation |
| `docs/Repo_Audit_and_Debt.md` | Mark TD-01 through TD-05 as resolved per phase completion |
| `SETUP.md` | Phase 2: Pi systemd setup instructions; Phase 4: psutil Pi dependency |

---

## 8. Handoff

- **Recommended next agent:** Systems Integration Engineer
- **Status:** READY_FOR_TASK_DECOMPOSITION
- **Required inputs:**
  - `docs/System_Architect/System_Implementation_Plan.md` (this document)
  - `docs/System_Architecture_and_Interface_Control_Document.md`
  - `docs/System_Diagnostic_and_Troubleshooting_Guide.md`
  - `docs/Repo_Audit_and_Debt.md`
- **Artifacts created:**
  - `docs/System_Architect/System_Implementation_Plan.md`
- **Project phase:** Planning → Execution
- **Confidence:** High
