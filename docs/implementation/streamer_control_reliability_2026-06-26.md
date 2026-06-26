# Streamer Control Reliability — Implementation Record

**Title:** Streamer Control Reliability Fixes — Stop/Start/Status  
**Purpose:** Record the exact changes made to `pc/services/pi_streamer_manager.py` to fix the three reliability defects identified in `streamer_control_diagnostic_2026-06-26.md`.  
**Last Updated:** 2026-06-26  
**Source Prompt:** Runtime Implementation Agent — Fix Pi streamer start/stop/status reliability  
**Source Documents Used:**
- `docs/diagnostics/diagnostics results/streamer_control_diagnostic_2026-06-26.md`
- `docs/json/system_manifest.json`

**Source Implementation Analyzed:** `pc/services/pi_streamer_manager.py`  
**Related Documents:**
- `docs/diagnostics/diagnostics results/streamer_control_diagnostic_2026-06-26.md`
- `docs/System_Architecture_and_Interface_Control_Document.md`
- `docs/System_Diagnostic_and_Troubleshooting_Guide.md`

**Assumptions:**
- Mic streamer audio hardware failure (RC-3) is a separate Pi hardware issue and is **not** addressed here.
- Pi project path and venv path are provided by the `settings` object injected into `PiStreamerManager`.
- All remote shell commands execute on the Pi under `/bin/sh` (POSIX-compatible).

---

## Revision History

| Date       | Change |
|------------|--------|
| 2026-06-26 | Initial implementation record created by Runtime Implementation Agent. |

---

## 1. Summary of Changes

| File | Change type | Defect addressed |
|------|-------------|-----------------|
| `pc/services/pi_streamer_manager.py` | Modified — `query_status()` | RC-4: Stale/reused PID file reported as running |
| `pc/services/pi_streamer_manager.py` | Modified — `run_action()` start branch | RC-2: False "started" on slow-crashing mic |
| `pc/services/pi_streamer_manager.py` | Modified — `run_action()` stop branch | RC-1: Stop always reported success regardless of process state |
| `pc/services/pi_streamer_manager.py` | Modified — `run_action()` return logic | RC-1/RC-2: `"failed"` output from start was incorrectly mapped to `(True, "failed")` |
| `tests/test_pi_streamer_manager.py` | Created | Regression coverage for all four scenarios |

---

## 2. Defect Details and Before/After

### Fix 1 — Stop: SIGTERM → poll → SIGKILL → confirm death

**Root cause (RC-1):** The original stop command deleted the PID file and echoed `stopped` unconditionally, even if the signal was silently swallowed (process blocked in a C extension like `capture_array()` or `stream.read()`).

#### Before

```bash
if [ -f {pid_file} ]; then
  pid=$(cat {pid_file}); kill $pid 2>/dev/null; rm -f {pid_file}; echo stopped;
else echo already-stopped;
fi
```

**Problems:**
- `kill` exit code discarded — a dead or unresponsive process is treated as success.
- PID file deleted before process death is confirmed.
- Unconditional `echo stopped` — caller always receives success.
- No escalation to SIGKILL if SIGTERM is not handled.

#### After

```bash
if [ -f {pid_file} ]; then
  pid=$(cat {pid_file});
  kill $pid 2>/dev/null;
  for i in $(seq 1 10); do sleep 0.3; kill -0 $pid 2>/dev/null || break; done;
  kill -9 $pid 2>/dev/null; sleep 0.1;
  if kill -0 $pid 2>/dev/null; then echo stop-failed;
  else rm -f {pid_file}; echo stopped; fi;
else echo already-stopped;
fi
```

**Properties:**
- Sends SIGTERM first.
- Polls up to 3 seconds (10 × 0.3 s) for graceful exit.
- Escalates to SIGKILL if process is still alive after the poll window.
- Only deletes the PID file after death is confirmed.
- Echoes `stop-failed` if the process survives SIGKILL (kernel zombie or uninterruptible state).
- `run_action` return logic maps `stop-failed` output to `(False, "stop-failed")`.

---

### Fix 2 — Start: Replace single 0.5 s sleep with 2 s polling loop

**Root cause (RC-2):** The mic streamer enumerates broken ALSA/JACK/PulseAudio devices before crashing; this enumeration can take longer than 0.5 s. The health check fires while the process is still alive mid-enumeration, reports `started`, and the subsequent `refresh_streamer_status` finds the crash a second later.

#### Before

```bash
cd {project_path} &&
nohup {venv}/bin/python {script} > {log} 2>&1 &
echo $! > {pid_file}; sleep 0.5;
kill -0 $(cat {pid_file}) 2>/dev/null && echo started || echo failed
```

**Problem:** One-shot `sleep 0.5` is too short for slow-crashing ALSA enumeration.

#### After

```bash
cd {project_path} &&
nohup {venv}/bin/python {script} > {log} 2>&1 &
echo $! > {pid_file};
for i in $(seq 1 4); do sleep 0.5;
kill -0 $(cat {pid_file}) 2>/dev/null || break; done;
kill -0 $(cat {pid_file}) 2>/dev/null && echo started || echo failed
```

**Properties:**
- Polls up to 2 seconds (4 × 0.5 s).
- Breaks out of the loop immediately if the process dies (`|| break`), so a fast crash is detected quickly.
- A process that survives all 4 iterations is considered healthy.
- `run_action` return logic maps `"failed"` output from the health check to `(False, "failed")`.

---

### Fix 3 — query_status: Guard against stale PID file and PID reuse

**Root cause (RC-4):** After a non-graceful kill (SIGKILL, OOM, reboot), the atexit handler does not run and the PID file is left stale. If the OS recycles that PID for an unrelated process, `kill -0 $pid` succeeds and `query_status` incorrectly reports `running`.

#### Before

```bash
if [ -f {pid_file} ]; then
  pid=$(cat {pid_file}); kill -0 $pid 2>/dev/null && echo running || echo stopped;
else echo stopped;
fi
```

**Problem:** `kill -0` only checks process existence, not identity.

#### After

```bash
if [ -f {pid_file} ]; then
  pid=$(cat {pid_file});
  if kill -0 $pid 2>/dev/null; then
    grep -q '{script_name}' /proc/$pid/cmdline 2>/dev/null \
    && echo running || echo stopped;
  else echo stopped; fi;
else echo stopped;
fi
```

Where `{script_name}` is `mic_udp_streamer` or `video_udp_streamer` (derived from the `streamer` argument).

**Properties:**
- After confirming liveness with `kill -0`, verifies `/proc/$pid/cmdline` contains the expected script name.
- A recycled PID belonging to an unrelated process does not have the script name in its cmdline → reported as `stopped`.
- A dead process (stale PID file) → `kill -0` fails → reported as `stopped`.

---

### Fix 4 — Return logic: map "failed" to (False, …)

The original return clause was:

```python
if code == 0:
    return True, output or f"{action}ed"
return False, output or "failed"
```

This returned `(True, "failed")` when the start health check echoed `failed` (exit code 0 from the remote shell). Fixed to:

```python
if code != 0:
    return False, output or "failed"
if output in ("stop-failed", "failed"):
    return False, output
return True, output or f"{action}ed"
```

---

## 3. Test Results

```
tests/test_pi_streamer_manager.py::TestQueryStatus::test_live_streamer_reports_running PASSED
tests/test_pi_streamer_manager.py::TestQueryStatus::test_no_pid_file_reports_stopped PASSED
tests/test_pi_streamer_manager.py::TestQueryStatus::test_pid_reuse_unrelated_process_reports_stopped PASSED
tests/test_pi_streamer_manager.py::TestQueryStatus::test_query_status_command_contains_cmdline_guard PASSED
tests/test_pi_streamer_manager.py::TestQueryStatus::test_ssh_failure_reports_error PASSED
tests/test_pi_streamer_manager.py::TestQueryStatus::test_stale_pid_file_dead_process_reports_stopped PASSED
tests/test_pi_streamer_manager.py::TestRunActionStop::test_stop_already_stopped PASSED
tests/test_pi_streamer_manager.py::TestRunActionStop::test_stop_command_removes_pid_file_only_after_confirmed_dead PASSED
tests/test_pi_streamer_manager.py::TestRunActionStop::test_stop_command_uses_sigterm_before_sigkill PASSED
tests/test_pi_streamer_manager.py::TestRunActionStop::test_stop_does_not_succeed_when_process_survives PASSED
tests/test_pi_streamer_manager.py::TestRunActionStop::test_stop_success_when_process_dies PASSED
tests/test_pi_streamer_manager.py::TestRunActionStart::test_start_command_health_check_polls_at_least_2_seconds PASSED
tests/test_pi_streamer_manager.py::TestRunActionStart::test_start_command_uses_polling_loop_not_single_sleep PASSED
tests/test_pi_streamer_manager.py::TestRunActionStart::test_start_fails_if_process_exits_during_health_window PASSED
tests/test_pi_streamer_manager.py::TestRunActionStart::test_start_success PASSED

15 passed in 0.01s
```

---

## 4. What Was NOT Changed

- GUI layout (`pc/operator_console_app.py`) — not touched.
- Pi-side scripts (`pi/mic_udp_streamer.py`, `pi/video_udp_streamer.py`, `pi/audio/streamer.py`) — not touched.
- Mic audio hardware configuration (`pi/audio/config.py`) — RC-3 is a hardware failure on the Pi, not a PC-side software defect. Fix requires diagnosing the Pi audio subsystem and setting `INPUT_DEVICE_INDEX` to a valid device.
- SSH connection infrastructure (`_run_ssh`) — unchanged.

---

## 5. Known Remaining Issues

| ID | Description | Owner |
|----|-------------|-------|
| RC-3 | Mic streamer fails with `OSError: [Errno -9999]` due to broken Pi audio device (`INPUT_DEVICE_INDEX = None` selects a failing default). Must be resolved by running `python -m pi.audio_diagnostics` on the Pi, identifying a working device, and setting `INPUT_DEVICE_INDEX` explicitly. | Pi hardware / audio config |
| RC-4 (partial) | Pi-side atexit handler does not run on SIGKILL or reboot, leaving stale PID files. The PC-side guard in `query_status` mitigates the false-positive detection, but the stale file remains until the next successful start/stop cycle. A Pi-side fix would use a lock file or a `systemd` service with proper cleanup. | Future / Pi-side |
