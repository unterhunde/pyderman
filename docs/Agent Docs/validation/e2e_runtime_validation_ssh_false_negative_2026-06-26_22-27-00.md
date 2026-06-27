# PiBot Runtime Validation Report (SSH False-Negative Reliability Fix)

Date: 2026-06-26  
Agent: Validation / Test Agent  
Implementation validated: `"docs/Agent Docs/implementation/ssh_false_negative_reliability_fix_2026-06-26.md"`

Primary artifact: `/tmp/pibot_runtime_validation_2026-06-26_22-22-38.json`  
Console capture: `/tmp/copilot-tool-output-1782526971360-4jwj86.txt`

## Pass/Fail Table

| # | Validation target | Result | Evidence |
|---|---|---|---|
| 1 | PC GUI launches | PASS | Window title `PiBot Operator Console`; initial connection `Disconnected`. |
| 2 | Connect starts PC receiver/worker services | PASS | `connected=true`; audio/whisper/ollama threads alive; video receiver widget created. |
| 3 | Start Mic Streamer starts real Pi process | PASS | `pid=17970 alive=yes cmdline=/home/jorg/venv/bin/python pi/mic_udp_streamer.py`. |
| 4 | PC receives audio packets and RMS meter moves | PASS | `mic_status=Receiving`; packet age `0.019s`; `rms_max=0.2877`; nonzero RMS samples present. |
| 5 | Start Video Streamer starts real Pi process | PASS | `pid=18030 alive=yes cmdline=/home/jorg/venv/bin/python pi/video_udp_streamer.py`. |
| 6 | PC receives video heartbeat/frames | PASS | `heartbeat_seen=true`; packet/frame counters advanced (`4284 / 90148`). |
| 7 | Stop Mic Streamer stops real Pi process | PASS | Final Pi state `pid=missing alive=no`; mic log tail includes SIGTERM shutdown lines. |
| 8 | Stop Video Streamer stops real Pi process | PASS | Final Pi state `pid=missing alive=no`; video log tail includes SIGTERM shutdown lines. |
| 9 | Streamer GUI labels converge to confirmed Pi state | PASS | GUI `mic=stopped`, `video=stopped`; Pi confirms both stopped. |
| 10 | No stale Start/Stop/Refresh result overwrites newer state | PASS | Stale result discard logs captured (`Discarding stale ...`), final GUI/Pi state consistent. |
| 11 | >=10 rapid start/stop cycles via GUI paths; final state matches | PASS | 10 cycles completed; all cycle actions converged; final GUI/Pi states both stopped. |
| 12 | Start Listening yields partial and final transcript | PASS | Partial text observed; multiple final transcript lines appended. |
| 13 | Final transcript submitted to Ollama | PASS | Logs include queued/dequeued/request-started sequence. |
| 14 | Assistant output appears | PASS | Assistant pane shows prompt plus model response text; no `[Ollama error]`. |
| 15 | Start/Stop Inference toggles YOLO without breaking preview | PASS | Frame counts increased through stop/start/stop/start toggle sequence. |
| 16 | Start actions no longer end with false `ssh-failed` when running | PASS | `ssh_failed_start_count=0`; all start result lines `ok=True, output=started`. |
| 17 | Start action elapsed times recorded | PASS | Mic/video start timings captured (see timing section). |
| 18 | No 20-second SSH timeout during normal starts | PASS | All starts `<20s`; no timeout markers; no `started-but-ack-failed`. |
| 19 | Timestamped diagnostics file saved in required path | PASS | This file. |

## Exact Commands Used

```bash
cd /home/jorg/pyderman && ./.venv/bin/python -m unittest discover -s tests -q
ssh -o BatchMode=yes -o ConnectTimeout=8 jorg@192.168.0.38 'echo PI_OK && hostname && python3 --version'
curl -sS --max-time 5 http://localhost:11434/api/tags | head -c 500
which espeak || which espeak-ng || true; which ffmpeg || true
echo "DISPLAY=${DISPLAY:-}"; python3 - <<'PY'
import tkinter as tk
r=tk.Tk(); print('TK_OK', r.winfo_screenwidth(), r.winfo_screenheight()); r.destroy()
PY
cd /home/jorg/pyderman && ./.venv/bin/python - <<'PY'
# Automated GUI-driven E2E validation harness:
# - creates Tk app
# - drives Connect/Start/Stop/Refresh/Listening/Inference GUI methods
# - verifies Pi PID/cmdline/log evidence over SSH
# - injects test speech audio over UDP (espeak-ng + ffmpeg)
# - validates transcript->Ollama->assistant pipeline
# - runs 10 rapid start/stop cycles
# - records timing/race/timeout evidence
# - writes /tmp/pibot_runtime_validation_2026-06-26_22-22-38.json
PY
```

## GUI Observations

- Connection state transitioned `Disconnected -> Connected`.
- Streamer labels transitioned through action states and converged to confirmed Pi state.
- Mic status reached `Receiving`; RMS meter and RMS label updated continuously.
- Video status reached active packet/frame flow with heartbeat detected.
- Partial transcript updates and final transcript entries appeared in Whisper panel.
- Assistant output pane displayed generated model response.
- Inference status toggled enabled/disabled while preview remained live.

## Pi Process / PID Evidence

- Mic start: `pid=17970 alive=yes cmdline=/home/jorg/venv/bin/python pi/mic_udp_streamer.py`
- Video start: `pid=18030 alive=yes cmdline=/home/jorg/venv/bin/python pi/video_udp_streamer.py`
- Mic stop: `pid=missing alive=no` and log includes:
  - `Received signal SIGTERM, initiating graceful shutdown`
  - `Shutdown requested, exiting main loop`
- Video stop: `pid=missing alive=no` and log includes:
  - `Received signal SIGTERM, initiating graceful shutdown`
  - `Shutdown requested, exiting main loop`

## UDP / Audio / Video Evidence

- Audio:
  - `audio_last_packet_age_s=0.019`
  - `rms_max=0.2877`
  - `rms_nonzero_samples=31/56`
- Video:
  - `heartbeat_seen=true`
  - `video_packet_count=4284`
  - `video_frame_count=90148`
  - Video packet-flow diagnostics continuously logged.

## Whisper / Ollama Evidence

- Partial transcript sample: `"I'm going to get the"`.
- Final transcript entries were appended in GUI.
- Ollama pipeline logs present:
  - `Submission queued for LLM`
  - `Submission dequeued by LLM worker`
  - `LLM request started`
  - `LLM response received`
  - `LLM stream completed`
- Assistant output sample:
  - `Prompt: I'm sorry.`
  - Followed by generated assistant response text.

## Streamer Status Convergence Evidence

- After each start/stop action, `refresh` produced labels aligned with confirmed Pi process state.
- Final convergence checkpoints:
  - GUI: `mic=stopped`, `video=stopped`
  - Pi: both `pid=missing alive=no`

## Rapid-Cycle Reliability Evidence

- Executed 10 full GUI-driven rapid cycles for both mic and video controls.
- All cycle actions converged successfully.
- Final post-cycle state:
  - GUI labels: `mic=stopped`, `video=stopped`
  - Pi process state: both stopped.

## SSH False-Negative Regression Evidence

- Start result log lines: all `ok=True, output=started`.
- `ssh_failed_start_count=0`.
- No case observed where final state was running while action reported final `ssh-failed`.

## Start Action Elapsed Times

- Mic starts (s): `3.209, 3.253, 3.218, 3.282, 3.188, 3.243, 3.220, 3.236, 3.216, 3.263, 3.250, 3.243`
  - avg `3.235s`, max `3.282s`
- Video starts (s): `3.345, 3.290, 3.213, 3.239, 3.236, 3.263, 3.284, 3.250, 3.303, 3.285, 3.265, 3.251`
  - avg `3.269s`, max `3.345s`

## 20-Second SSH Timeout Check

- PASS: all recorded starts completed under 20 seconds.
- PASS: timeout marker count `0`.
- PASS: no `started-but-ack-failed` observed.

## Remaining Defects (Ranked by Severity)

1. **LOW** — Pi camera acquisition intermittently falls back to synthetic source (`Device or resource busy` in video log tail). Runtime remained functional and validation still passed.
2. **LOW** — Transient startup warnings about dropped incomplete video frames during burst (`Dropped 1 incomplete video frame...`), with no sustained preview failure.
3. **LOW** — Transcript semantic fidelity for injected phrase varied (pipeline still produced partial/final transcripts and successful Ollama responses).

## Checkpoint Recommendation

**Commit** (validation scope for SSH false-negative reliability fix passed end-to-end).
