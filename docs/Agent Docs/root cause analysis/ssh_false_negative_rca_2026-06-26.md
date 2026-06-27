# Root Cause Analysis: Intermittent `ssh-failed` False-Negative on Streamer Start

Date: 2026-06-26  
Scope: `pc/services/pi_streamer_manager.py`, `pc/operator_console_app.py`, SSH subprocess behavior

## Executive Summary

The `ssh-failed` action result is emitted by `run_action(..., "start")` when `_run_ssh(...)` returns `None`.  
In this code, `_run_ssh` returns `None` only on **`subprocess.TimeoutExpired`** (or unexpected exceptions), and `run_action` maps that to `"ssh-failed"` (`pc/services/pi_streamer_manager.py:85-87, 114-118`).

Observed + reproduced behavior proves this specific failure is a **command-timeout false-negative**:

- The remote start command echoes `started` and the streamer process is running.
- But the local SSH subprocess does not exit before the 20s timeout.
- The timeout causes `run_action` to report `ok=False, output=ssh-failed`.
- Immediate refresh then reports `running`.

This is not an auth/connectivity failure and not a remote startup failure.

---

## 1) Which SSH command returns `ssh-failed`

`ssh-failed` comes from `PiStreamerManager.run_action(..., action="start")` only:

- `result = self._run_ssh(remote_cmd, timeout=20)`  
- `if result is None: return False, "ssh-failed"`  

Start command shape (`pc/services/pi_streamer_manager.py:58-66`):

```bash
cd <pi_project> && \
nohup <pi_venv>/bin/python pi/<mic|video>_udp_streamer.py > <log> 2>&1 & \
echo $! > <pid_file>; \
for i in $(seq 1 4); do sleep 0.5; kill -0 $(cat <pid_file>) 2>/dev/null || break; done; \
kill -0 $(cat <pid_file>) 2>/dev/null && echo started || echo failed
```

SSH argv (`pc/services/pi_streamer_manager.py:112`):

```bash
["ssh", "-o", "ConnectTimeout=8", "<user>@<host>", "<remote_cmd>"]
```

---

## 2) Failure mode classification

### Runtime artifact evidence (`/tmp/copilot-tool-output-1782521945632-shcy8g.txt`)

- All recorded **start** results were `ok=False, output=ssh-failed` (7/7).
- Failures align to timeout windows:
  - Most: exactly ~20s from `Executing start...` to result.
  - Some video starts show ~41s because action execution is serialized by the manager SSH lock and the second start waits behind another timeout before its own timeout.

### Controlled reproduction (same command path, same host)

Measured start attempts (thread `MainThread`, id `124528895414784`):

| Timestamp | Streamer | Action | SSH argv | Timeout | Return code | Stdout | Stderr | Elapsed |
|---|---|---|---|---:|---:|---|---|---:|
| 2026-06-26T21:26:28.543 | mic | start | `ssh -o ConnectTimeout=8 jorg@192.168.0.38 "<start_cmd>"` | yes | n/a | `started\n` | `None` | 20.007s |
| 2026-06-26T21:26:51.013 | video | start | `ssh -o ConnectTimeout=8 jorg@192.168.0.38 "<start_cmd>"` | yes | n/a | `started\n` | `None` | 20.016s |

Collected per-attempt state transitions:

| Streamer | Thread | Pi PID before | Pi PID immediately after failure | Pi status after refresh |
|---|---|---|---|---|
| mic | `MainThread` / `124528895414784` | `pid=missing alive=no cmdline=` | `pid=13187 alive=yes cmdline=/home/jorg/venv/bin/python pi/mic_udp_streamer.py` | `running` |
| video | `MainThread` / `124528895414784` | `pid=12201 alive=yes cmdline=/home/jorg/venv/bin/python pi/video_udp_streamer.py` | `pid=13304 alive=yes cmdline=/home/jorg/venv/bin/python pi/video_udp_streamer.py` | `running` |

### Classification matrix

| Candidate failure source | Status | Evidence |
|---|---|---|
| SSH connection timeout (`ConnectTimeout=8`) | **Not primary cause** | Timeout occurs at ~20s command timeout, not ~8s connect timeout; follow-up SSH calls succeed in ~0.4s. |
| Command timeout (`subprocess.run(..., timeout=20)`) | **Confirmed** | Repro hits `TimeoutExpired` at ~20s while partial stdout already contains `started`. |
| Nonzero SSH exit code | Not this failure | On timeout path there is no exit code (`run_action` gets `None`), yet output later confirms running. |
| Empty stdout | Not cause | Timeout exception captured stdout `started\n`. |
| Stderr noise | Not cause | `stderr` was empty/None in reproduced timeout events. |
| Remote command failed to start process | Rejected | PID and `/proc/<pid>/cmdline` show streamer running immediately after timeout. |
| Overlapping SSH sessions | Partially contributes to latency only | `_ssh_lock` serializes SSH; no concurrent SSH execution in manager. Queuing explains 41s wall-time cases, not root timeout mechanism. |
| Pi load/auth delay | Not primary cause | Immediate post-failure state/refresh SSH calls consistently fast (<0.5s). |

---

## 3) Did streamer start before SSH returned failure?

**Yes.**

Mic repro:
- Before command: `pid=missing alive=no`
- Start command timed out at 20.007s with stdout `started`
- Immediate post-failure PID check: `pid=13187 alive=yes cmdline=/home/jorg/venv/bin/python pi/mic_udp_streamer.py`
- Refresh command: `running`

Video repro:
- Start command timed out at 20.016s with stdout `started`
- Immediate post-failure PID check: `pid=13304 alive=yes cmdline=/home/jorg/venv/bin/python pi/video_udp_streamer.py`
- Refresh command: `running`

This exactly matches the field symptom: action reports failure, refresh confirms running.

---

## 4) Why refresh succeeds after `ssh-failed`

Refresh uses `query_status(..., timeout=12)` with a short read-only command (`kill -0` + `/proc/$pid/cmdline` grep).  
These calls complete quickly and return `running`, because the process was already started by the prior action command.

---

## 5) Proven mechanism

The remote streamer process inherits an extra socket FD from the SSH session (observed as FD 3), even though stdio is redirected:

```text
pid=13662
0 -> /dev/null
1 -> /home/jorg/pibot/.run/mic_streamer.log
2 -> /home/jorg/pibot/.run/mic_streamer.log
3 -> socket:[129465]
```

Because that inherited SSH-related socket remains open in the child, the SSH client process does not terminate promptly; local `subprocess.run(..., timeout=20)` expires and `_run_ssh` returns `None`, producing `ssh-failed`.

So the defect class is:

**started-but-ack-failed due local SSH command timeout, not transport failure and not remote start failure.**

---

## Event Timeline (key sequence)

| Time | Event |
|---|---|
| 20:58:31 | `Executing start on mic streamer (token=2)` |
| 20:58:51 | `mic streamer start result ... ok=False, output=ssh-failed` |
| 20:58:51 | `Streamer status | mic=running` |
| 20:58:58 | `Executing start on video streamer (token=2)` |
| 20:59:18 | `video streamer start result ... ok=False, output=ssh-failed` |
| 20:59:18 | `Streamer status | video=running` |

(Repeated similarly for later tokens in the same artifact.)

---

## Recommendation (no implementation in this RCA)

`run_action` should classify start outcomes into at least:

1. `transport-failed` (SSH connect/auth/session errors)  
2. `remote-command-failed` (nonzero/explicit `failed`)  
3. `started-but-ack-failed` (timeout but remote evidence shows started/running)  
4. `status-confirmed-running` (post-action refresh reconciliation)

The proven mechanism above should be used to design that change; no code change was performed in this RCA.
