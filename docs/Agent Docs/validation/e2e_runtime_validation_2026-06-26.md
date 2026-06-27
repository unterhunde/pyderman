# PiBot End-to-End Runtime Validation Report (PC GUI + Real Pi)

Date: 2026-06-26  
Validator: Validation/Test Agent  
Scope: GUI controls through PC services, Pi streamer process control, UDP audio/video flow, transcription/Ollama/inference behavior.

## Pass/Fail Table

| # | Validation target | Result | Evidence summary |
|---|---|---|---|
| 1 | PC GUI launches | PASS | `PiBot Operator Console` window created; initial state `Disconnected`. |
| 2 | Connect starts PC receiver/worker services | PASS | `connected=true`; audio/whisper/ollama threads alive; video receiver widget created. |
| 3 | Start Mic Streamer starts Pi process | PASS | Pi `mic_streamer.pid=5952`, alive, cmdline shows `pi/mic_udp_streamer.py`. |
| 4 | PC receives audio packets and RMS meter moves | PASS | Mic status `Receiving`; audio packet age `0.005s`; RMS max `0.2942`; recurring microphone packet logs. |
| 5 | Start Video Streamer starts Pi process | PASS | Pi `video_streamer.pid=6016`, alive, cmdline shows `pi/video_udp_streamer.py`; camera startup logs. |
| 6 | PC receives video heartbeat/frames | PASS | `Video UDP packets detected`; packet-flow logs; frame count advanced to `665+`. |
| 7 | Stop Mic Streamer stops real Pi process | PASS | After stop: mic PID file missing; log shows `Received signal SIGTERM` then shutdown. |
| 8 | Stop Video Streamer stops real Pi process | PASS | After stop: video PID file missing; log shows SIGTERM and clean streamer stop. |
| 9 | Start Listening produces partial + final transcript | PASS | Partial text observed and multiple final transcript lines recorded. |
| 10 | Final transcript is submitted to Ollama | FAIL | Queue submit/dequeue happened, but Ollama request failed before POST due Tk thread error in URL getter (`RuntimeError: main thread is not in main loop`). |
| 11 | Assistant output appears | FAIL | Output pane showed `Prompt: ...` then `[Ollama error]`; no model response tokens. |
| 12 | Start/Stop Inference toggles YOLO without breaking preview | PASS | Inference enabled/disabled/enabled; frames continued increasing (`496 -> 577 -> 638`). |

## Exact Commands Used

```bash
git --no-pager status --short
python3 --version; which python3; pip --version
cd /home/jorg/pyderman && python3 -m unittest discover -s tests -v
cd /home/jorg/pyderman && python3 -m venv .venv
cd /home/jorg/pyderman && ./.venv/bin/pip install --upgrade pip
cd /home/jorg/pyderman && ./.venv/bin/pip install -r requirements.txt
cd /home/jorg/pyderman && ./.venv/bin/pip install numpy scipy opencv-python openai-whisper torch ultralytics requests Pillow
cd /home/jorg/pyderman && ./.venv/bin/python -m unittest discover -s tests -v
ssh -o BatchMode=yes -o ConnectTimeout=8 jorg@192.168.0.38 'echo PI_OK && hostname && python3 --version'
ssh -o ConnectTimeout=8 jorg@192.168.0.38 'ls -d /home/jorg/pibot /home/jorg/pyderman 2>/dev/null; ls /home/jorg/pibot/pi 2>/dev/null | head -5; ls /home/jorg/pyderman/pi 2>/dev/null | head -5'
ssh -o ConnectTimeout=8 jorg@192.168.0.38 'ls -la /home/jorg/venv/bin/python 2>/dev/null && /home/jorg/venv/bin/python -V || echo NO_PI_VENV'
curl -sS --max-time 5 http://localhost:11434/api/tags | head -c 400
cd /home/jorg/pyderman && ./.venv/bin/python - <<'PY'
# Automated GUI-driven validation script:
# - create_application(Tk)
# - connect
# - start/stop mic + video streamers
# - inspect Pi PID/log state via SSH
# - monitor RMS/packet/frame stats
# - start listening + inject spoken TTS UDP audio
# - verify transcript and Ollama pane behavior
# - toggle inference and verify frame continuity
# - write /tmp/pibot_validation_run.json
PY
```

## GUI Observations

- Launch: title `PiBot Operator Console`, connection label `Disconnected`.
- After Connect: label changed to `Connected`, workers active.
- Mic panel: `Mic Status=Receiving`, audio stream `Enabled`, RMS label active (`RMS: 0.2500` at capture point).
- Video panel: transitioned to `Video UDP packets detected` and `Receiving UDP video packets`.
- Transcript panel: partial transcript updates and multiple final transcript entries visible.
- Assistant panel: displayed prompt text plus `[Ollama error]` (no successful assistant completion).
- Inference panel: status toggled to `Inference enabled` / `Inference disabled` as commanded.

## Pi Process / PID Evidence

### After Start Mic Streamer
- `pid_file=5952`
- `alive=yes`
- `cmdline=/home/jorg/venv/bin/python pi/mic_udp_streamer.py`

### After Start Video Streamer
- `pid_file=6016`
- `alive=yes`
- `cmdline=/home/jorg/venv/bin/python pi/video_udp_streamer.py`
- Pi camera initialization + streamer start logs present.

### After Stop Actions
- Mic: `pid_file=missing`, log shows `Received signal SIGTERM` then `Shutdown requested, exiting main loop`.
- Video: `pid_file=missing`, log shows `Received signal SIGTERM`, `Shutdown requested`, `Video streamer stopped`.

## UDP / Audio / Video Evidence

- Audio:
  - `audio_last_packet_age_s=0.005`
  - `max_rms=0.2942`
  - `rms_nonzero_samples=33/70`
  - Repeating logs: `Microphone activity | packets=... rms=...`
- Video:
  - Logs: `Video receiver listening`, `Video UDP packets detected`, repeated `Video packet flow`.
  - Frame progression: `frames_after_start_infer=496`, `frames_after_stop_infer=577`, `frames_after_reenable=638`.
  - Final counters observed: packets/frames `13152 / 665`.

## Remaining Defects (Ranked by Severity)

1. **HIGH** — Ollama request path is thread-unsafe in real runtime  
   - Symptom: submissions enqueue/dequeue, but worker crashes each request before POST.  
   - Evidence: traceback in `pc/services/ollama_service.py` when `self.url_getter()` reads Tk variable from non-main thread:  
     `RuntimeError: main thread is not in main loop` via `self.server_var.get()`.  
   - Impact: breaks requirements #10 and #11 (no assistant response).

2. **MEDIUM** — Streamer button status can remain transient (`Starting...`) during async operations  
   - Observed immediately after start action snapshots; eventually corrected by refresh and Pi evidence confirmed start.  
   - Impact: operator feedback ambiguity/race perception.

3. **LOW** — Startup check target mismatch warning (`target=192.168.0.189`) appears in this host context  
   - Impact: warning noise; did not block actual audio/video reception in this run.

## Artifacts

- Full structured run data: `/tmp/pibot_validation_run.json`
- Full runtime console capture: `/tmp/copilot-tool-output-1782517926088-1i0ve5.txt`

