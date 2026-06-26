# Streamer Control Diagnostic Report

**Title:** Streamer Control Diagnostic — Start/Stop/Status Validation  
**Purpose:** Document the true current state of mic and video streamer control before any code edits. Identify failing logic paths, hardware issues, and root cause candidates.  
**Last Updated:** 2026-06-26  
**Source Prompt:** Validation / Diagnostic Agent session — inspect local PC code + SSH Pi live state  
**Source Documents Used:** `docs/System_Architecture_and_Interface_Control_Document.md`  
**Source Implementation Analyzed:**
- `pc/services/pi_streamer_manager.py`
- `pc/operator_console_app.py`
- `pi/mic_udp_streamer.py`
- `pi/video_udp_streamer.py`
- `pi/audio/streamer.py`
- `pi/video/streamer.py`
- `pi/audio/config.py`
- `pibot_config.py`  
**Related Documents:**
- `docs/System_Architecture_and_Interface_Control_Document.md`
- `docs/System_Diagnostic_and_Troubleshooting_Guide.md`
- `docs/diagnostics/streamer_control_lifecycle.mmd`  
**Assumptions:** SSH access to Pi at `jorg@192.168.0.38` was live during inspection. Pi project path is `/home/jorg/pibot`. No code was edited during this session.

---

## Revision History

| Date | Change |
|------|--------|
| 2026-06-26 | Initial diagnostic report created from live inspection. |

---

## 1. Pi Live State at Time of Inspection

SSH target: `jorg@192.168.0.38`  
Pi project path: `/home/jorg/pibot`  
Inspection time: 2026-06-26 ~18:00 EDT

| Item | Finding |
|------|---------|
| Running Python processes | **None** — both streamers are dead |
| `mic_streamer.pid` | **Absent** — atexit handler cleaned it up after crash |
| `video_streamer.pid` | **Present, stale** — contained PID `1314`, process dead |
| `mic_streamer.log` | Ends with `OSError: [Errno -9999] Unanticipated host error` inside `pa.open()` |
| `video_streamer.log` | Ends abruptly at `22:18:45` — no "Shutdown requested", no "Video streamer stopped", no SIGTERM message |

### `.run/` Directory Contents at Inspection

```
-rw-rw-r-- 1 jorg jorg   4994 Jun 25 22:16 mic_streamer.log
-rw-rw-r-- 1 jorg jorg 214806 Jun 25 22:19 video_streamer.log
-rw-rw-r-- 1 jorg jorg      5 Jun 25 21:43 video_streamer.pid   ← stale
```

### PID 1314 Liveness Check

```
kill -0 1314 → exit code 1 → DEAD (stale PID file confirmed)
```

---

## 2. Observed vs Intended Behavior

### Mic Streamer

| | State |
|---|---|
| **Intended** | Start launches `mic_udp_streamer.py` via SSH nohup, writes PID file, streams audio indefinitely. Stop sends SIGTERM, deletes PID file, GUI shows "stopped". |
| **Observed** | Start executes; ALSA device enumeration runs, USB card invalid, PulseAudio/JACK unavailable, `pa.open()` raises `OSError -9999`. The atexit handler **correctly** cleans up the PID file. `run_action` may return `(True, "started")` if the crash takes longer than the 0.5 s health check window — giving a brief false-green in the GUI before the follow-up `refresh_streamer_status` reveals the crash. **Mic streamer cannot start on current Pi audio state.** |

### Video Streamer

| | State |
|---|---|
| **Intended** | Start launches `video_udp_streamer.py` via SSH nohup, streams camera frames. Stop sends SIGTERM → graceful loop exit → `finally` block logs "Video streamer stopped" → atexit deletes PID file. |
| **Observed** | Video streamer ran from 21:43 to 22:18 (35 minutes) on 2026-06-25. It died **without any graceful shutdown log entry** — the `finally` block log line and the SIGTERM handler message are both absent. The atexit handler did **not** run. PID file was left behind stale. The process was killed by SIGKILL or a system event (Pi reboot or OOM), not the GUI Stop button. |

---

## 3. Root Cause Candidates

### RC-1 (Critical) — Stop command does not confirm process death before reporting success

**File:** `pc/services/pi_streamer_manager.py`  
**Function:** `run_action()`, lines 56–62  

```python
remote_cmd = (
    f"if [ -f {pid_file} ]; then "
    f"pid=$(cat {pid_file}); kill $pid 2>/dev/null; rm -f {pid_file}; echo stopped; "
    f"else echo already-stopped; "
    f"fi"
)
```

**Problem:** The semicolons run sub-commands unconditionally. `kill $pid 2>/dev/null` failing (dead/absent process) is silently swallowed — exit code discarded. The script then **unconditionally** removes the PID file and echoes `stopped`, causing `run_action` to always return `(True, "stopped")` regardless of whether the process actually died.

**Consequence:** If SIGTERM is not handled quickly (process blocked in a C extension like libcamera's `capture_array()` or PyAudio's `stream.read()`), the process keeps streaming with no PID file. The GUI shows "stopped" (because the PID file is gone), but audio/video is still being transmitted. The process becomes untrackable — no mechanism to stop it without a manual `kill -9` on the Pi.

**Verification:** Simulated stop command during inspection. `kill` returned exit code 1 (process already dead), but the script still echoed `stopped` and removed the PID file — confirming unconditional success reporting.

---

### RC-2 (Medium) — Start command 0.5 s health check is too short for slow-crashing mic streamer

**File:** `pc/services/pi_streamer_manager.py`  
**Function:** `run_action()`, lines 48–53  

```python
f"nohup {self.settings.pi_venv_path}/bin/python {target_script} "
f"> {log_file} 2>&1 & "
f"echo $! > {pid_file}; sleep 0.5; "
f"kill -0 $(cat {pid_file}) 2>/dev/null && echo started || echo failed"
```

**Problem:** The mic streamer crashes inside `pa.open()` — but only after ALSA enumerates multiple broken devices (USB invalid, JACK, PulseAudio). This enumeration takes variable time. If >0.5 s, the health check finds the process alive → echoes `started` → `run_action` returns `(True, "started")` → GUI shows green. One second later, the follow-up `refresh_streamer_status` detects the crash and flips back to "stopped". The user sees a **momentary false "started"** state.

**Verification:** Confirmed from mic log — ALSA/JACK/Pulse errors appear before the crash, indicating a slow enumeration path.

---

### RC-3 (Active / Hardware) — Mic streamer cannot start: audio device failure on Pi

**File:** `pi/audio/streamer.py`  
**Function:** `UDPMicStreamer.run()`, line 60  
**Config:** `pi/audio/config.py`, `INPUT_DEVICE_INDEX = None`

**Mic log evidence:**
```
ALSA lib pcm_usb_stream.c:481:(_snd_pcm_usb_stream_open) Invalid card 'card'
Cannot connect to server socket err = No such file or directory
jack server is not running or cannot be started
JackShmReadWritePtr::~JackShmReadWritePtr - Init not done for -1, skipping unlock
PulseAudio: Unable to create stream: Timeout
Expression 'alsa_snd_pcm_prepare( stream->capture.pcm )' failed in 'src/hostapi/alsa/pa_linux_alsa.c', line: 2932
OSError: [Errno -9999] Unanticipated host error
```

**Problem:** `INPUT_DEVICE_INDEX = None` forces automatic device selection. `select_input_device()` selects device 12 ("default"), which fails because the USB audio card descriptor is invalid, JACK is not running, and PulseAudio timed out. The streamer **will fail on every start attempt** until the Pi audio subsystem is repaired or a working device index is explicitly configured.

---

### RC-4 (Low) — Stale PID file after non-graceful process death

**Files:** `pi/video_udp_streamer.py`, `pi/mic_udp_streamer.py`  
**Function:** `cleanup_pid` atexit handler inside `main()`

**Problem:** `atexit` callbacks run on normal exit, `sys.exit()`, and handled signals (SIGTERM via the signal handler which exits the loop). They do **not** run on SIGKILL, SIGKILL from kernel OOM, or a system reboot. The video streamer was killed by one of these non-graceful events, leaving `video_streamer.pid` stale on disk.

**Additional risk:** If the OS reuses PID 1314 for an unrelated process, `query_status`'s `kill -0 $pid` would succeed and falsely report "running." The current implementation has no safeguard (e.g., cmdline check) against PID reuse.

---

### RC-5 (Non-issue / Confirmed Safe) — Direct widget.configure() call in `_run_streamer_action`

**File:** `pc/operator_console_app.py`  
**Function:** `_run_streamer_action()`, line 828  

```python
status_widget.configure(text=f"{action.title()}ing...", style="Warn.TLabel")
```

This is called directly from the Tkinter button callback (main/UI thread), so it is **thread-safe**. All subsequent UI updates from the worker thread correctly go through `_post_ui` → queue → `_drain_ui_queue`. **No action required.**

---

## 4. Exact Files and Functions Involved

| Component | File | Function | Lines | Issue |
|-----------|------|----------|-------|-------|
| Stop logic | `pc/services/pi_streamer_manager.py` | `run_action()` | 55–62 | Kill failure silently ignored; PID file deleted before process confirmed dead; always reports success |
| Start health check | `pc/services/pi_streamer_manager.py` | `run_action()` | 48–53 | 0.5 s sleep too short for slow mic crash; may give false "started" |
| Stop dispatch | `pc/operator_console_app.py` | `_streamer_action_worker()` | 832–847 | 1 s sleep after stop; relies on PID-file absence which is already guaranteed by the rm-f |
| Status query | `pc/services/pi_streamer_manager.py` | `query_status()` | 19–38 | Logic correct; minor PID-reuse vulnerability |
| Mic hardware crash | `pi/audio/streamer.py` | `UDPMicStreamer.run()` | 60 | `pa.open()` crashes on broken audio device |
| Mic device config | `pi/audio/config.py` | `INPUT_DEVICE_INDEX` | 11 | `None` forces auto-selection to broken default |
| Pi atexit cleanup | `pi/video_udp_streamer.py` / `pi/mic_udp_streamer.py` | `cleanup_pid` inside `main()` | 30–35 | Not called on SIGKILL or reboot → stale PID file |

---

## 5. Recommended Minimal Edit Plan

> These are recommendations only. No code was modified during this diagnostic session.

### Fix 1 — Stop: wait for process death, escalate to SIGKILL
**Target:** `pc/services/pi_streamer_manager.py`, `run_action()` stop branch

Replace the current one-liner with a polling loop that waits up to ~3 s for SIGTERM, then escalates to SIGKILL:

```bash
if [ -f {pid_file} ]; then
  pid=$(cat {pid_file})
  kill $pid 2>/dev/null
  for i in $(seq 1 10); do
    sleep 0.3
    kill -0 $pid 2>/dev/null || break
  done
  kill -9 $pid 2>/dev/null   # escalate if still alive after 3 s
  rm -f {pid_file}
  kill -0 $pid 2>/dev/null && echo "stop-failed" || echo stopped
else
  echo already-stopped
fi
```

### Fix 2 — Stop: only report stopped after confirming dead
Extend Fix 1: the final `echo stopped` should only fire after confirming `kill -0` fails. Currently, success is assumed unconditionally.

### Fix 3 — Start: extend health check window for mic
**Target:** `pc/services/pi_streamer_manager.py`, `run_action()` start branch

Increase `sleep 0.5` to `sleep 2.0` (or replace with a polling loop checking 4× at 0.5 s intervals). This ensures the health check fires after the ALSA enumeration crash window.

### Fix 4 — Mic audio hardware on Pi
Diagnose the audio subsystem on the Pi:
```bash
cd /home/jorg/pibot
source /home/jorg/venv/bin/activate
python -m pi.audio_diagnostics
```
Identify the correct working device index and set `INPUT_DEVICE_INDEX` explicitly in `pibot.env` or `pi/audio/config.py`.

### Fix 5 — PID reuse guard in query_status (optional hardening)
**Target:** `pc/services/pi_streamer_manager.py`, `query_status()`

After confirming `kill -0 $pid` succeeds, also verify:
```bash
grep -q "mic_udp_streamer\|video_udp_streamer" /proc/$pid/cmdline 2>/dev/null
```
This prevents a recycled PID from being reported as a live streamer.

---

## 6. Command Execution Trace (inspection session)

The following SSH commands were run during the diagnostic session (read-only except for the accidental cleanup of the stale `video_streamer.pid` during stop-command simulation):

```bash
# Directory listing
ls -la /home/jorg/pibot/.run/

# PID file contents
cat /home/jorg/pibot/.run/video_streamer.pid   # → 1314

# Liveness checks
kill -0 1314   # → exit 1 (dead)
ps aux | grep -E "python|streamer"   # → no results

# Log inspection
tail -30 /home/jorg/pibot/.run/video_streamer.log
tail -30 /home/jorg/pibot/.run/mic_streamer.log  # (piped to same output)
grep "Shutdown requested|SIGTERM|stopped" /home/jorg/pibot/.run/video_streamer.log   # → 0 matches

# Stop command simulation (this cleaned up the stale video_streamer.pid)
# kill returned exit code 1 (process dead), script still echoed "stopped" and rm -f'd the PID file
# → confirmed RC-1 unconditional success reporting

# Status query simulation (after PID file removal)
# → correctly reported "stopped"
```

> **Note:** The simulation of the stop command during inspection consumed and deleted the stale `video_streamer.pid`. The `.run/` directory now contains only the two log files.
