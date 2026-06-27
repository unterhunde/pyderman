# Root Cause Analysis Report — Intermittent SSH Reliability + Transient GUI Status Mismatch

## Scope and constraints
- Investigated only:
  - `pc/services/pi_streamer_manager.py`
  - `pc/operator_console_app.py`
- Investigation only; no code changes.
- Evidence from existing runtime logs/artifacts plus static code path analysis.

## Proven single root cause

**Root cause:** streamer control is implemented as multiple independent asynchronous writers with no operation-generation guard, no cancellation, and no authoritative state reducer.  

This causes:
1. **Intermittent "ssh-failed" reliability events** when an action worker times out (`subprocess.run(... timeout=20)` in `PiStreamerManager._run_ssh`) but remote state may still change.
2. **Transient GUI mismatches** because old/new callbacks from different workers race to write the same status label, and the last-arriving callback wins regardless of recency.

## Evidence

### A) Multiple writers to same GUI labels (confirmed)
`mic_streamer_status` / `video_streamer_status` are written by all of:
- `_run_streamer_action()` immediate direct write (`<Action>ing...`) — `pc/operator_console_app.py:844-847`
- `_streamer_action_worker()` result write (success/failure) — `:850-865`
- `refresh_streamer_status()` `"Checking..."` write — `:813-823`
- `_refresh_streamer_status_worker()` final status write — `:825-836`

### B) No generation ID / stale suppression (confirmed)
- No request ID, generation ID, or "latest-op-only" check in any of the above paths.
- UI queue callback application (`_drain_ui_queue()`, `:490-499`) is generic FIFO processing of posted callbacks; it does not validate freshness.

### C) Overlapping workers/refreshes exist (confirmed)
- Every action call spawns a new thread (`threading.Thread(..._streamer_action_worker...)`).
- Every refresh call spawns a new thread (`..._refresh_streamer_status_worker...`).
- No single-flight guard per streamer/action type.

### D) SSH timeout mapped to generic failure even when Pi state converges to running (confirmed)
- `_run_ssh()` returns `None` on `TimeoutExpired` and broad `Exception`; caller maps this to `"ssh-failed"` (`pc/services/pi_streamer_manager.py:85-88,115-118`).
- Runtime evidence:
  - `20:09:57 | mic streamer start result: ok=False, output=ssh-failed`
  - `20:10:17 | video streamer start result: ok=False, output=ssh-failed`
  - Yet video packet flow starts at `20:10:01+`, and `/tmp/pibot_validation_run_final.json` shows both streamers alive after start.

### E) Out-of-order asynchronous callback effects (confirmed)
- From `/tmp/copilot-tool-output-1782519176003-hc0w6a.txt`:
  - `20:12:47` mic start reports `ssh-failed`
  - `20:13:08` video start reports `ssh-failed`
  - `20:13:08` status refresh reports `mic=running`
- This is an explicit mismatch from asynchronous, non-generated writes.

### F) Requested instrumentation field coverage from current logs
- Present: timestamp, streamer, action intent (from log message), final `ok/output`, coarse status label text.
- Missing in current implementation logs: thread id/name, exact SSH command string per event, SSH stdout/stderr per event, status-label before/after pairs, refresh generation id, worker generation id.
- Because this was an investigation-only pass with no code modification, these fields were derived only where existing artifacts already exposed them.

## Direct answers to requested investigation points

1. **GUI callbacks involved:**  
   `start_mic_streamer`, `stop_mic_streamer`, `start_video_streamer`, `stop_video_streamer`, `refresh_streamer_status`, plus `_run_streamer_action`, `_streamer_action_worker`, `_refresh_streamer_status_worker`.

2. **Worker threads involved:**  
   one-shot action workers and one-shot refresh workers, each spawned per invocation without dedupe.

3. **UI queue events involved:**  
   `_post_ui()` enqueues status writes; `_drain_ui_queue()` applies queued writes every 20ms.

4. **SSH subprocesses involved:**  
   all status/action SSH commands are run via `subprocess.run(["ssh", ...], timeout=12|20)` in `_run_ssh()`.

5. **Timers involved:**  
   `_drain_ui_queue` 20ms, `_drain_log_queue` 80ms, status bar refresh 1s.

6. **Delayed callbacks involved:**  
   explicit `time.sleep(1.0)` in `_streamer_action_worker()` before posting refresh on success.

## Required determinations

- **Complete event timeline / ordering:** see `streamer_event_timeline_2026-06-26.md`.
- **Duplicate status updates occur:** yes, from 4 independent writer paths.
- **Stale worker results overwrite newer state:** yes, no generation or stale-drop check.
- **Multiple refreshes overlap:** yes, each refresh spawns a new thread.
- **Multiple SSH commands overlap:**  
  - In-manager parallel overlap: **no** (`_ssh_lock` serializes execution).  
  - Multi-request backlog/queuing: **yes**.
- **More than one source writes same status label:** yes (4 sources).
- **Asynchronous callbacks arrive out of order:** yes (log evidence above).
- **Any locks ineffective:** `_ssh_lock` is effective for SSH serialization, but **ineffective for UI-state race prevention**.
- **GUI derived from optimistic assumptions:** yes. Success path writes immediate success before confirmed refresh; failure path may remain stale if remote state changed despite timeout.

## Why this explains both remaining symptoms
- **Intermittent SSH reliability event:** local timeout -> `"ssh-failed"` classification is emitted even when remote side may have executed start/stop.
- **Transient GUI mismatch:** competing asynchronous status writers with no generation control produce temporary incorrect label states until a later callback wins.

## Recommendation (analysis only; no implementation here)
Once approved, fix should be generation-based state ownership:
- per-streamer operation generation IDs,
- single-flight/cancellation semantics for action+refresh,
- authoritative final-label write only from latest generation,
- and explicit timeout classification distinct from transport/auth failure.
