# PiBot System Diagnostic & Troubleshooting Guide

## Document Metadata

- **Title:** PiBot System Diagnostic & Troubleshooting Guide
- **Purpose:** Provide operational diagnostics, troubleshooting workflows, and runtime failure-mode guidance for PiBot.
- **Last Updated:** 2026-06-26
- **Source Prompt:** User request: "update all files in /docs/ to be compliant with the attached file"
- **Source Documents Used:** `docs/json/prompt_header.json`, `docs/Prompt_Header.md`, `docs/json/system_manifest.json`
- **Source Implementation Analyzed:** `docs/`
- **Related Documents:** `docs/json/prompt_header.json`, `docs/Prompt_Header.md`, `docs/json/system_manifest.json`, `docs/json/System_Diagnostic_and_Troubleshooting_Guide.json`, `docs/diagnostics/*.mmd`
- **Assumptions:** Compliance is satisfied by including the required fields defined in `docs/json/prompt_header.json` under `documentation_generation_rules.required_fields`.
- **Revision History:**
  - 2026-06-26: Added Prompt Header compliance metadata block.

Last updated: 2026-06-26  
Primary index: `docs/json/system_manifest.json`

## 1) Purpose, Scope, and Method

This guide is the engineering troubleshooting reference for PiBot runtime operations across:

- `/home/jorg/pibot/pc`
- `/home/jorg/pibot/pi`

Primary source is `docs/json/system_manifest.json` (modules, threads, processes, interfaces, controls, ports, configuration).  
Implementation was spot-checked in referenced files to reflect current code behavior where it differs or needs clarification.

### What this guide covers

- Runtime module responsibilities and dependencies
- GUI controls and callback execution paths
- Thread/process ownership and lifecycle
- Queue/timer/background-worker behavior
- UDP/HTTP/SSH interfaces and network ports
- Config entries and misconfiguration symptoms
- Failure-mode diagnostics and repair playbooks

### What is intentionally excluded

- Exhaustive private helper analysis
- Full-program call graphing
- Archived experimental code as active runtime behavior

---

## 2) Runtime Topology (Manifest Cross-Reference)

Manifest references:

- `repository`
- `modules` (runtime modules in `pc/` and `pi/`)
- `threads`
- `processes`
- `network_ports`
- `interfaces`
- `relationships`

### 2.1 Main runtime composition

1. **PC GUI process** (`pc/client.py`) starts `OperatorConsoleApp`.
2. GUI creates and controls:
   - `AudioReceiverService` thread (UDP audio ingest)
   - `WhisperService` thread (speech segmentation/transcription)
   - `OllamaService` thread (streaming LLM output)
   - `UDPVideoReceiver` widget + render worker thread
3. GUI uses `PiStreamerManager` for SSH start/stop/status of Pi streamers.
4. **Pi mic process** (`pi/mic_udp_streamer.py`) runs `UDPMicStreamer` -> UDP audio to PC:5001.
5. **Pi video process** (`pi/video_udp_streamer.py`) runs `UDPVideoStreamer` -> UDP video+heartbeat to PC:5000.

### 2.2 Data pipelines

- Whisper pipeline diagram: `docs/diagnostics/whisper_pipeline_flow.mmd`
- Video pipeline diagram: `docs/diagnostics/video_pipeline_flow.mmd`
- Streamer control lifecycle diagram: `docs/diagnostics/streamer_control_lifecycle.mmd`

### 2.3 Active queues and timers

From implementation (`pc/operator_console_app.py`, `pc/video/receiver_widget.py`):

- `audio_queue` maxsize 400 (`np.ndarray`, rms tuples)
- `ollama_queue` maxsize 16 (`PromptSubmission`)
- `log_queue` maxsize 2000 (formatted log lines)
- `ui_queue` maxsize 4000 (UI callbacks marshaled to Tk thread)
- `UDPVideoReceiver._render_queue` maxsize 2
- `UDPVideoReceiver._ui_queue` maxsize 8
- Tk timers:
  - UI queue drain every 20ms
  - Log queue drain every 80ms
  - Status bar refresh every 1000ms
  - Video socket poll every 15ms

---

## 3) Process Inventory and Operations

Manifest references: `processes`

| Process | Launch mechanism | Expected PID ownership | Start sequence | Stop sequence | Health checks | Recovery |
|---|---|---|---|---|---|---|
| PC GUI process (`pc/client.py`) | Manual: `python3 pc/client.py` | Foreground shell PID | Creates Tk root -> `OperatorConsoleApp` -> optional Connect | GUI Disconnect / window close | GUI shows Connected + packet activity + logs | Restart app; re-run startup checks |
| Pi microphone streamer process (`pi/mic_udp_streamer.py`) | Manual on Pi or SSH via `PiStreamerManager.run_action("mic","start")` | `.run/mic_streamer.pid` on Pi | Writes PID file -> constructs `UDPMicStreamer` -> `run()` loop | SIGTERM/SIGINT or SSH stop action kills PID and removes pid file | Pi `.run/mic_streamer.pid`, `.run/mic_streamer.log`, PC audio packet activity | Stop + start via Streamers tab; verify `PIBOT_PC_HOST` and UDP reachability |
| Pi video streamer (`pi/video_udp_streamer.py`) | Manual on Pi or SSH via `PiStreamerManager.run_action("video","start")` | `.run/video_streamer.pid` on Pi | Writes PID file -> constructs `UDPVideoStreamer` -> `run()` loop | SIGTERM/SIGINT or SSH stop action kills PID and removes pid file | Pi `.run/video_streamer.pid`, `.run/video_streamer.log`, PC video packets/frames and heartbeat | Stop + start via Streamers tab; inspect camera fallback/logs |
| Pi audio diagnostics process (`pi/audio_diagnostics.py`) | Manual command on Pi | Foreground shell PID | Opens input device -> samples ~5 seconds -> prints diagnostics | Process exits after run | Console output includes RMS and suppression stats | Adjust `pi/audio/config.py` constants and device setup; rerun |
| SSH child processes (`pc/services/pi_streamer_manager.py`) | Spawned per query/action (`subprocess.run(["ssh",...])`) | Child process under PC GUI | Command created, lock/rate-limit applied, remote shell executes | Exits after command or timeout | Streamer status results (`running/stopped/error`) | Fix SSH connectivity/auth; retry action/status |

### Pi streamer process notes

- When started through GUI, stdout/stderr are redirected to:
  - `/home/jorg/pibot/.run/mic_streamer.log`
  - `/home/jorg/pibot/.run/video_streamer.log`
- PID files expected:
  - `/home/jorg/pibot/.run/mic_streamer.pid`
  - `/home/jorg/pibot/.run/video_streamer.pid`

---

## 4) Thread Inventory and Diagnostics

Manifest references: `threads`

| Thread/timer | Owner | Startup | Shutdown | Synchronization | Failure symptoms | Diagnostic procedure |
|---|---|---|---|---|---|---|
| Tk main thread | `pc/client.py` / Tk | `root.mainloop()` | window close | Tk event loop | Frozen GUI, non-responsive controls | Confirm process alive; check log queue still draining |
| AudioReceiverService thread | `pc/services/audio_receiver.py` | `connect()` -> `.start()` | `stop_event.set()` + socket close | `stop_event`, `audio_queue`, runtime-config lock accessors | No audio packets, mic idle, no RMS updates | Check bind success log and UDP 5001 traffic |
| WhisperService thread | `pc/services/whisper_service.py` | `connect()` -> `.start()` | `stop_event.set()` | `audio_queue`, `ollama_queue`, `RuntimeConfig` | Partial transcripts absent/frozen; no final transcript | Check transcript status + queue depth logs + whisper load log |
| OllamaService thread | `pc/services/ollama_service.py` | `connect()` -> `.start()` | `stop_event.set()` | `ollama_queue`, request streaming loop | Final transcript appears but assistant output stalls/errors | Check Ollama URL and `/api/tags` reachability |
| UDPVideoReceiver poll timer | `pc/video/receiver_widget.py` | `video_widget.start()` schedules `after(15ms)` | `video_widget.stop()` cancels poll job | Tk `after` | No incoming packet handling despite running process | Confirm socket bind + packet counters |
| UDPVideoReceiver render worker | `pc/video/receiver_widget.py` | `_start_worker()` | `_worker_stop.set()` + join | `_render_queue`, `_ui_queue`, inference lock | Frames received but no rendering / inference errors | Inspect status messages (`Loading model`, `Inference error`, decode failures) |
| GUI drain timers | `pc/operator_console_app.py` | `_start_ui_loops()` | app exits | Tk `after` and queues | UI stale despite worker activity, log box not updating | Confirm `_drain_ui_queue`/`_drain_log_queue` still scheduled |
| Startup checks thread | `pc/operator_console_app.py` | `run_startup_checks()` | one-shot thread exit | posts UI updates via `_post_ui` | Startup checks stuck at checking | Inspect background exceptions and connectivity |
| Streamer status thread | `pc/operator_console_app.py` | `refresh_streamer_status()` | one-shot thread exit | `_post_ui`, SSH lock in manager | Streamer status never updates / always unknown | Run manual SSH status command and inspect output |
| Streamer action thread | `pc/operator_console_app.py` | `_run_streamer_action()` | one-shot thread exit | `_post_ui`, SSH lock | Start/stop button shows failed or hangs at *ing* | Inspect SSH result and Pi `.run` logs |
| ThreadMonitor monitor thread | `pc/services/thread_monitor.py` | Not wired in current app | N/A | internal lock/stop event | None at runtime (unused) | Treat as inactive module until integrated |

---

## 5) Module Diagnostic Catalog

Manifest references: `modules` (33 entries)

Log-location shorthand:

- **GUI log box** = Logs tab in operator console (`GuiLogHandler` output)
- **PC stdout** = terminal launching `pc/client.py`
- **Pi streamer log** = `.run/mic_streamer.log` or `.run/video_streamer.log` when started by GUI

### 5.1 Active runtime modules (`pc/`, `pi/`, root)

| Module | Purpose | Key dependencies | Common failures | Log locations | Verification procedure | Recovery procedure |
|---|---|---|---|---|---|---|
| `pibot_config.py` | Load env/config into `AppSettings` | env vars, `pibot.env`, `Path` | wrong host/port/model path; bad int parse silently falls to default | indirect in GUI checks | Run startup checks; print loaded settings in REPL | Fix `pibot.env` or env vars and restart process |
| `pc/client.py` | PC composition root | Tkinter, `OperatorConsoleApp`, `load_settings` | launch failure, import errors | PC stdout | `python3 pc/client.py` opens GUI | fix venv/deps, ensure project root imports resolve |
| `pc/runtime_config.py` | Thread-safe runtime toggles | `threading.Lock` | stale toggles if UI not updating | GUI state widgets | Toggle controls and observe behavior changes | reconnect app if state appears desynced |
| `pc/logging_utils.py` | Pipe logs into GUI queue | `logging.Handler`, `queue.Queue` | dropped logs if queue full | GUI log box, PC stdout | Generate logs and confirm logs tab updates | reduce log volume or restart app |
| `pc/operator_console_app.py` | Main orchestration/UI | all services, queues, Tk timers | connect/disconnect issues; UI queue overflow | GUI log box, PC stdout | Connect, verify audio/video/transcript transitions | disconnect/reconnect; inspect failing worker from logs |
| `pc/services/audio_receiver.py` | UDP audio ingest and downsample 48k->16k | UDP socket, numpy, scipy | bind failure on 5001; packet drops; queue full | GUI log box | confirm “Audio receiver listening”, RMS updates, packet timestamps | free UDP port, ensure Pi mic streamer active, reconnect |
| `pc/services/whisper_service.py` | phrase detection + transcription + queue to LLM | whisper model, audio queue | model load/transcribe errors; no finalization | GUI log box | see “Whisper model ready”, partial/final transcript updates | check CPU load/audio threshold/silence timeout, restart connection |
| `pc/services/ollama_service.py` | stream LLM response tokens | `requests`, Ollama HTTP | timeout/refused connection, stream parse issues | GUI log box + assistant output | startup check Ollama reachable; final transcript triggers output | fix Ollama endpoint/model and retry |
| `pc/services/pi_streamer_manager.py` | SSH start/stop/status remote streamers | `ssh`, remote shell, pid files | ssh-failed, command timeout, stale pid file | GUI log box | Refresh status returns running/stopped | verify SSH auth/network; clear stale pid/log on Pi |
| `pc/services/startup_checks.py` | model/UDP/Ollama/target checks | filesystem, UDP bind probe, HTTP GET | false negatives if already connected; host mismatch | GUI check labels + log | Run Checks button updates 3 labels | align config, fix endpoint, rerun checks |
| `pc/services/thread_monitor.py` | watchdog helper (currently unused) | thread callbacks | not active in current runtime | none in normal runtime | `rg ThreadMonitor` shows no use | integrate or ignore as inactive |
| `pc/services/prompt_submission.py` | typed envelope for Whisper->LLM | dataclass | none | n/a | queue items are `PromptSubmission` with phrase_id/text | n/a |
| `pc/video/frame_buffer.py` | store/reassemble frame chunks | chunk dict | missing chunks -> assemble error | GUI log box via receiver warnings | check warnings for “Frame reassembly failed” | investigate UDP loss/network saturation |
| `pc/video/inference_engine.py` | decode JPEG and optional YOLO track | OpenCV, Ultralytics | bad model path, decode failure, inference exception | GUI status + log | start inference and verify model-ready + detections | correct model path/deps, disable inference temporarily |
| `pc/video/protocol.py` | packet format constants | struct | protocol mismatch if changed on one side only | manifests as no frames | packet counters rise but frames fail | keep PC/Pi protocol definitions aligned |
| `pc/video/receiver_widget.py` | UDP video receiver widget + worker | socket, queues, frame buffer, inference engine | bind failure on 5000, decode failures, queue pressure | GUI video status + logs | packet/frame counters and FPS increase | restart receiver via disconnect/connect; check Pi video stream |
| `pi/mic_udp_streamer.py` | mic streamer entrypoint + PID file | `UDPMicStreamer`, `load_settings` | cannot write pid file; startup failure | Pi streamer log/stdout | pid file exists and process alive | fix permissions/path; restart |
| `pi/video_udp_streamer.py` | video streamer entrypoint + PID file | `UDPVideoStreamer`, `load_settings` | cannot write pid file; startup failure | Pi streamer log/stdout | pid file exists and process alive | fix permissions/path; restart |
| `pi/audio/config.py` | audio tuning constants | pyaudio symbols | wrong gain/gate/channel values | observed in diagnostics output | run `pi/audio_diagnostics.py` | tune constants and rerun |
| `pi/audio/device_selection.py` | choose audio input device | PyAudio enumeration | no device, wrong selected device | Pi streamer log/stdout | confirm selected device print at startup | set preferred index or fix OS audio devices |
| `pi/audio/protocol.py` | audio header struct | struct | header mismatch with receiver | audio parse failures/silence | confirm same `AUDIO_HEADER` on PC and Pi | deploy matching code versions |
| `pi/audio/signal_processing.py` | channel select + AGC/noise gate | numpy | over/under-amplification; excessive suppression | `audio_diagnostics.py` output | inspect RMS/suppression counts | adjust gate/target/gain parameters |
| `pi/audio/streamer.py` | capture/process/send audio | PyAudio, UDP socket | stream read errors, no send, weak signal | Pi mic log/stdout | continuous startup print + PC packet activity | restart process, fix device/network, adjust config |
| `pi/video/config.py` | video constants | n/a | unrealistic FPS/quality/resolution causing load | Pi video log | verify stream fps and packet volume | tune constants conservatively |
| `pi/video/frame_source.py` | camera open + synthetic fallback | Picamera2, cv2 | camera init failure -> synthetic fallback | Pi video log warning/info | log indicates `source=picamera2` or `synthetic` | fix camera stack or accept synthetic mode |
| `pi/video/protocol.py` | video/heartbeat protocol structs | struct | protocol mismatch | PC receives packets but decode/path fails | verify matching packet formats on PC/Pi | synchronize protocol modules |
| `pi/video/streamer.py` | capture/encode/chunk/send video + heartbeat | cv2, camera source, UDP | camera failure, encode failures, network send issues | Pi video log | frame logs every 30 frames + heartbeat reflected on PC network state | restart, inspect camera fallback, reduce load |
| `pi/audio_diagnostics.py` | one-shot mic diagnostic tool | PyAudio, signal processing | fails to open device; weak RMS | terminal output | run script; inspect RMS/gate analysis | apply recommended tuning or device fixes |

### 5.2 Archived manifest modules (not active runtime)

Manifest includes archived compatibility/experimental modules under `archives/pc/`.

| Module | Runtime status | Diagnostic note |
|---|---|---|
| `archives/pc/mic_udp_receiver.py` | archived | historical playback receiver, not used by active GUI |
| `archives/pc/mic_udp_reciever.py` | archived | typo shim |
| `archives/pc/video_udp_receiver.py` | archived | compatibility facade |
| `archives/pc/video_udp_reciever.py` | archived | typo shim |
| `archives/pc/yolo_packet.py` | archived | legacy structured YOLO container |

---

## 6) GUI Control-to-Backend Mapping

Manifest references: `gui_controls`

| Visible control | Callback | Backend module path | Expected behavior / status updates | Failure symptoms | Diagnostic procedure |
|---|---|---|---|---|---|
| Connect / Disconnect button | `toggle_connection` | `pc/operator_console_app.py` | Starts/stops workers and video receiver; connection label switches | Stuck disconnected; connect errors | check logs around “Starting connection sequence” and worker startup |
| Server URL entry | `server_var` (read by workers/checks) | `pc/operator_console_app.py` | Used by startup checks + Ollama requests | checks fail / LLM unreachable | verify URL format and `/api/tags` |
| Run Checks | `run_startup_checks` | `pc/services/startup_checks.py` | Updates model/UDP/Ollama labels | labels stuck in “checking...” | inspect startup thread exceptions |
| Enable Audio Stream | `toggle_audio_stream` | `pc/runtime_config.py`, `pc/services/audio_receiver.py` | Toggles ingestion into `audio_queue` and stream status label | mic packets present but no transcription | verify `audio_stream_enabled` and queue depth |
| Volume Threshold scale | `_on_threshold_change` | `pc/runtime_config.py`, `pc/services/whisper_service.py` | Adjusts speech activation threshold | speech never starts or triggers too easily | tune while observing partial transcript behavior |
| Silence Timeout scale | `_on_silence_change` | `pc/runtime_config.py`, `pc/services/whisper_service.py` | Controls phrase finalization delay | delayed or premature final transcripts | tune and observe `Speech end detected` logs |
| Start Listening | `start_listening` | `pc/runtime_config.py` | Enables segmentation; transcript status “Listening” | no transcript despite audio | confirm listening not paused |
| Stop Listening | `stop_listening` | `pc/runtime_config.py` | Pauses segmentation; status “Listening paused” | still transcribing unexpectedly | verify status and queue clearing behavior |
| Start Inference | `start_inference` | `pc/video/receiver_widget.py` | Enables YOLO overlay; model status updates | no detections / inference error | check model path and status messages |
| Stop Inference | `stop_inference` | `pc/video/receiver_widget.py` | Disables YOLO but continues video display | still high inference load | verify model status “Inference disabled” |
| Start Mic Streamer | `start_mic_streamer` | `pc/services/pi_streamer_manager.py` | SSH start Pi mic streamer; status should become running | ssh-failed/failed | inspect SSH connectivity and Pi logs |
| Stop Mic Streamer | `stop_mic_streamer` | `pc/services/pi_streamer_manager.py` | SSH stop mic streamer; status stopped/already-stopped | stale running status | verify PID file/process alignment |
| Start Video Streamer | `start_video_streamer` | `pc/services/pi_streamer_manager.py` | SSH start Pi video streamer; packets should appear on PC | started but no packets | check `PIBOT_PC_HOST` target and firewall |
| Stop Video Streamer | `stop_video_streamer` | `pc/services/pi_streamer_manager.py` | SSH stop video streamer and remove pid file | process persists | manual kill on Pi and clear pid file |
| Refresh Streamer Status | `refresh_streamer_status` | `pc/services/pi_streamer_manager.py` | Queries remote pid+process liveness | always unknown/error | run equivalent SSH command manually |
| Video placeholder label | `removed/reinserted by video receiver lifecycle` | `pc/operator_console_app.py` | hidden when receiver active; shown when stopped | blank/incorrect widget state | reconnect video receiver |
| Logs ScrolledText | `GuiLogHandler + _drain_log_queue` | `pc/logging_utils.py`, `pc/operator_console_app.py` | streams logs into UI | logs missing while app active | verify queue drain timer and queue fullness |

### 6.1 Complete remote command execution path (for streamer buttons)

`Start/Stop Mic Streamer` and `Start/Stop Video Streamer` path:

1. Tk button callback (`start_*` / `stop_*`) in `OperatorConsoleApp`
2. `_run_streamer_action(streamer, action)` marks status “Starting/Stopping...”
3. Background thread `_streamer_action_worker`
4. `PiStreamerManager.run_action()` builds remote shell command
5. `subprocess.run(["ssh", "-o", "ConnectTimeout=8", "<user>@<pi>", "<cmd>"], timeout=20)`
6. Remote Pi command:
   - **start**: `nohup <venv>/bin/python pi/*_udp_streamer.py > .run/*_streamer.log 2>&1 &; echo $! > .run/*_streamer.pid; ...`
   - **stop**: read pid, `kill`, remove pid file
7. SSH output returned (`started`, `failed`, `stopped`, etc.)
8. UI status label updated
9. After 1s, app calls `refresh_streamer_status(streamer)` for acknowledgement
10. `query_status()` checks pid file + `kill -0 pid` and updates final running/stopped state

Diagram: `docs/diagnostics/streamer_control_lifecycle.mmd`

---

## 7) Interfaces and Message Contracts

Manifest references: `interfaces`

| Interface | Producer | Consumer | Protocol / format | Ack semantics | Timeout behavior | Retry behavior | Failure modes | Diagnostics |
|---|---|---|---|---|---|---|---|---|
| Audio UDP | `UDPMicStreamer` | `AudioReceiverService` | UDP datagram: `AUDIO_HEADER(!IH)` + int16 PCM | no explicit ack | receiver socket timeout 0.5s loop | none | packet loss, bind failure, queue overflow | check PC audio packet timestamps + 5001 traffic |
| Video UDP | `UDPVideoStreamer` | `UDPVideoReceiver` | UDP datagram chunks: `CHUNK_HEADER(!IHH)` + JPEG bytes | no explicit ack | 15ms GUI poll; worker get timeout 0.2s | none | out-of-order/lost chunks, frame drops | packet/frame counters, reassembly warnings |
| Heartbeat UDP | `UDPVideoStreamer` | `UDPVideoReceiver` / status bar | UDP `HEARTBEAT_PACKET(!BQ)` every 500ms | implicit via status freshness | network considered offline after ~2s stale | none | stale network state despite partial traffic | monitor `last_heartbeat_time`-driven state |
| Ollama HTTP | `OllamaService` | Ollama daemon | POST JSON `{model,prompt,stream:true}` | HTTP status + streamed `done` token | request timeout 120s | none in worker | refused, timeout, bad model | startup check + curl to `/api/tags` |
| SSH control | `PiStreamerManager` | Pi sshd | shell command over SSH | command return code/output | connect timeout 8s; cmd timeout 12/20s | no automatic retry | auth/network failure, remote script path issues | run same SSH command manually |
| Whisper in-process API | `WhisperService` | `whisper` model | float32 waveform to `model.transcribe()` | return dict with `text` | queue get timeout 0.2s | n/a | model load/transcription exceptions | look for “Whisper transcription error” |
| YOLO in-process API | `InferenceEngine` | `ultralytics.YOLO` | frame arrays, `YOLO.track` result | return frame/boxes | worker queue timeout 0.2s | n/a | model path/decode/inference exceptions | status “Inference error: ...” |
| Camera API | `frame_source.open_camera` | Picamera2 | RGB888 frame capture | n/a | none explicit | fallback to synthetic source | camera init failure | Pi log warning + source switches to synthetic |
| Logging queue | `GuiLogHandler` | GUI log drain timer | formatted string queue | n/a | 80ms periodic drain | none | queue full drops log lines | compare PC stdout vs GUI logs |

---

## 8) Network Port Ownership and Troubleshooting

Manifest references: `network_ports`

| Port | Owner | Protocol | Purpose | Expected traffic | Diagnostics | Troubleshooting |
|---|---|---|---|---|---|---|
| 5000 | `UDPVideoStreamer` -> `UDPVideoReceiver` | UDP | video chunks + heartbeat | continuous bursty chunks + heartbeat every 500ms | PC: packet/frame counters, status online, FPS > 0 | verify Pi target host, firewall, socket bind conflicts |
| 5001 | `UDPMicStreamer` -> `AudioReceiverService` | UDP | microphone PCM stream | continuous PCM packets during mic capture | PC audio meter updates; microphone activity logs | verify mic streamer alive, audio device, bind conflicts |
| 22 | `PiStreamerManager` | SSH | remote control start/stop/status | short command sessions per action/status refresh | manual `ssh user@pi 'echo ok'` | fix SSH keys/password/auth, host reachability |
| 11434 | Ollama server | HTTP | LLM generation and startup tag checks | GET `/api/tags`, POST `/api/generate` stream | `curl http://localhost:11434/api/tags` | ensure Ollama daemon/model availability |

---

## 9) Configuration Reference and Misconfiguration Symptoms

Manifest references: `configuration` (33 entries)

### 9.1 Environment-backed app settings (`pibot_config.py`)

| Key | Meaning | Default | Valid values | Consumed by | Incorrect-config symptoms |
|---|---|---|---|---|---|
| `PIBOT_CONFIG_FILE` | env file path | `pibot.env` | readable file path | `pibot_config.load_settings` | wrong or missing settings loaded |
| `PIBOT_UDP_BIND_HOST` | PC UDP bind address | `0.0.0.0` | host/IP local to PC | `AudioReceiverService`, `UDPVideoReceiver`, `StartupChecks` | bind failures or listeners on wrong interface |
| `PIBOT_PC_HOST` | destination host for Pi streamers | `192.168.0.189` | reachable PC IP/hostname from Pi | `UDPMicStreamer`, `UDPVideoStreamer`, startup alignment check | streamers run but PC receives no packets |
| `PIBOT_UDP_AUDIO_PORT` | UDP audio port | `5001` | free UDP port 1..65535 | Pi mic sender + PC audio receiver + checks | audio bind conflicts / no ingress |
| `PIBOT_UDP_VIDEO_PORT` | UDP video port | `5000` | free UDP port 1..65535 | Pi video sender + PC video receiver + checks | video bind conflicts / no ingress |
| `PIBOT_WHISPER_SAMPLE_RATE` | PC Whisper expected rate | `16000` | positive int | `WhisperService` | timing/segmentation artifacts if mismatched assumptions |
| `PIBOT_PI_SAMPLE_RATE` | Pi mic capture rate | `48000` | PyAudio-supported rate | `UDPMicStreamer` | distorted/choppy capture if unsupported |
| `PIBOT_YOLO_MODEL_PATH` | YOLO model file path | `yolo26m.pt` | existing model path | `InferenceEngine`, startup model check | inference/model load errors |
| `PIBOT_OLLAMA_URL` | Ollama generate endpoint | `http://localhost:11434/api/generate` | reachable HTTP URL | `OllamaService`, `StartupChecks` | startup check unreachable, LLM errors |
| `PIBOT_OLLAMA_MODEL` | model name passed to Ollama | `llama3:instruct` | installed Ollama model name | `OllamaService` | stream error or empty responses |
| `PIBOT_PI_HOST` | Pi SSH host | `192.168.0.38` | reachable host/IP | `PiStreamerManager` | streamer control ssh-failed |
| `PIBOT_PI_USER` | Pi SSH user | `jorg` | valid remote account | `PiStreamerManager` | permission/auth failures |
| `PIBOT_PI_VENV_PATH` | remote venv root | `/home/jorg/venv` | path containing `bin/python` | `PiStreamerManager` start action | remote start fails (`python` not found) |
| `PIBOT_PI_PROJECT_PATH` | remote project root | `/home/jorg/pibot` | valid path on Pi | PID/log paths, `cd` before run, status checks | PID/log files missing, start/stop/query mismatch |

### 9.2 Runtime toggles (`RuntimeConfig`)

| Key | Meaning | Default | Valid values | Consumed by | Incorrect-config symptoms |
|---|---|---|---|---|---|
| `RuntimeConfig.volume_threshold` | speech detection baseline | `0.045` | float > 0 | `WhisperService` | never triggers or too many false triggers |
| `RuntimeConfig.silence_timeout` | silence to finalize phrase | `1.2` | float > 0 | `WhisperService` | delayed or fragmented final transcripts |
| `RuntimeConfig.audio_stream_enabled` | accept audio into queue | `True` | bool | `AudioReceiverService` | packets received but no transcription |
| `RuntimeConfig.listening_enabled` | allow segmentation/transcribe | `True` | bool | `WhisperService` | transcript status stuck paused |

### 9.3 Pi audio constants (`pi/audio/config.py`)

| Key | Meaning | Default | Valid values | Consumed by | Incorrect-config symptoms |
|---|---|---|---|---|---|
| `INPUT_CHANNELS` | capture channels requested | `2` | 1..device max | `UDPMicStreamer`, diagnostics | open failure or unexpected channel mapping |
| `OUTPUT_CHANNELS` | logical output channels | `1` | usually 1 | `UDPMicStreamer` logs/assumptions | misleading diagnostics if inconsistent |
| `FORMAT` | PyAudio sample format | `pyaudio.paInt32` | PyAudio format constant | `UDPMicStreamer`, diagnostics | stream open/type mismatch issues |
| `CHUNK_FRAMES` | frames per packet/read | `1024` | positive int | `UDPMicStreamer`, header frame_count | high latency (too large) or high overhead (too small) |
| `CHANNEL_MODE` | mono extraction mode | `left` | `left/right/mix/auto` (non-explicit treated as auto) | signal processing | weak channel or noisy channel selected |
| `NOISE_GATE_RMS` | suppression threshold | `0.0005` | float >= 0 | AGC/gate pipeline | speech suppressed if too high |
| `TARGET_RMS` | AGC target level | `0.08` | float > 0 | AGC | clipping/weak output |
| `MIN_GAIN` | lower AGC clamp | `1.0` | float >= 0 | AGC | inadequate amplification |
| `MAX_GAIN` | upper AGC clamp | `28.0` | float > min | AGC | noise pumping or low max loudness |
| `AGC_ATTACK` | gain rise speed | `0.35` | 0..1 | AGC | delayed gain-up if too low |
| `AGC_RELEASE` | gain fall speed | `0.15` | 0..1 | AGC | gain lingering/instability if poorly tuned |

### 9.4 Pi video constants (`pi/video/config.py`)

| Key | Meaning | Default | Valid values | Consumed by | Incorrect-config symptoms |
|---|---|---|---|---|---|
| `FRAME_WIDTH` | capture width | `640` | camera-supported width | camera config/synthetic frame size | camera init failure/perf strain |
| `FRAME_HEIGHT` | capture height | `480` | camera-supported height | camera config/synthetic frame size | camera init failure/perf strain |
| `FPS` | target frame rate | `20` | >0 practical FPS | frame pacing + camera controls | lag/drops/high CPU or low throughput |
| `JPEG_QUALITY` | compression quality | `50` | 1..100 | JPEG encode | oversized packets at high quality or poor image at low |

---

## 10) Failure Mode Catalog by Subsystem

Manifest references used throughout: `modules`, `threads`, `processes`, `interfaces`, `network_ports`, `gui_controls`

Each subsystem includes: symptoms, likely causes, files/modules/threads/processes/interfaces, verification, repair, regression.

### 10.1 GUI

- **Symptoms:** frozen controls, stale labels, no log updates
- **Likely causes:** Tk event-loop blockage, UI/log queue overload, crashed worker leaving stale state
- **Files/modules:** `pc/operator_console_app.py`, `pc/logging_utils.py`
- **Threads/processes:** Tk main thread, GUI drain timers, PC GUI process
- **Interfaces:** Logging queue
- **Verification:** confirm CPU/memory values continue refreshing each second; logs still appended
- **Repair:** restart GUI process; reduce log flood; reconnect workers
- **Regression tests:** manual connect/disconnect + tab interactions + logs update

### 10.2 Networking / Connection Management

- **Symptoms:** network status offline, no packet counters
- **Likely causes:** bad `PIBOT_PC_HOST`, firewall, wrong bind host/ports, stale streamers
- **Files/modules:** `pibot_config.py`, `pc/services/startup_checks.py`, `pc/operator_console_app.py`
- **Threads/processes:** startup-check thread, GUI status timer, Pi streamer processes
- **Interfaces:** Audio UDP, Video UDP, Heartbeat UDP
- **Verification:** startup checks + UDP packet counters + heartbeat-driven online status
- **Repair:** correct host/ports, restart streamers, reopen GUI connection
- **Regression tests:** run checks before and after connect, verify transition offline->online

### 10.3 Video Streaming (Pi sender side)

- **Symptoms:** no packets on PC, synthetic mode unexpectedly, encode warnings
- **Likely causes:** camera init failure, wrong destination host, send errors
- **Files/modules:** `pi/video/streamer.py`, `pi/video/frame_source.py`, `pi/video_udp_streamer.py`
- **Threads/processes:** Pi video streamer process
- **Interfaces/ports:** Video UDP + Heartbeat UDP on 5000
- **Verification:** Pi log shows periodic frame stats and source type; PC packet counter rises
- **Repair:** fix camera stack or accept synthetic fallback; fix `PIBOT_PC_HOST`; restart streamer
- **Regression tests:** start/stop video streamer from GUI and validate packet/frame growth

### 10.4 Video Receiver / Rendering

- **Symptoms:** packets but no frames, decode failures rising, inference errors
- **Likely causes:** chunk loss, corrupted payloads, model load errors, queue pressure
- **Files/modules:** `pc/video/receiver_widget.py`, `pc/video/frame_buffer.py`, `pc/video/inference_engine.py`
- **Threads/processes:** receiver poll timer, render worker, PC GUI process
- **Interfaces:** Video UDP, YOLO in-process API
- **Verification:** `video_packet_count`, `video_frame_count`, FPS label, inference status
- **Repair:** disable inference to isolate decode path; reconnect receiver; reduce video load
- **Regression tests:** inference on/off while stream active; ensure frame updates continue

### 10.5 Audio Streaming

- **Symptoms:** mic status idle, no RMS meter movement, no whisper activity
- **Likely causes:** mic streamer down, bad audio device, wrong port/host, suppressed by gate
- **Files/modules:** `pi/audio/streamer.py`, `pc/services/audio_receiver.py`, `pi/audio/config.py`
- **Threads/processes:** AudioReceiver thread, Pi mic streamer process
- **Interfaces/ports:** Audio UDP on 5001
- **Verification:** packet activity logs + RMS updates + queue depth
- **Repair:** restart mic streamer, run `pi/audio_diagnostics.py`, tune gate settings
- **Regression tests:** sustained speech yields consistent RMS and packet logs

### 10.6 Whisper / Speech Pipeline

- **Symptoms:** partial transcript appears but no final, final but no LLM submission
- **Likely causes:** threshold/silence tuning, whisper exceptions, queue full to Ollama
- **Files/modules:** `pc/services/whisper_service.py`, `pc/runtime_config.py`, `pc/services/prompt_submission.py`
- **Threads/processes:** WhisperService thread
- **Interfaces:** Whisper API, ollama_queue handoff
- **Verification:** logs for `Speech detected`, `Speech end detected`, `Final transcript generated`, `Submission queued`
- **Repair:** adjust threshold/silence; restart connection; inspect queue pressure
- **Regression tests:** `tests/test_whisper_service.py`, `tests/test_e2e_whisper_to_ollama.py`

### 10.7 Inference / YOLO

- **Symptoms:** inference errors, no detection overlay, high inference latency
- **Likely causes:** missing model file, unsupported environment, overloaded CPU/GPU
- **Files/modules:** `pc/video/inference_engine.py`, `pc/video/receiver_widget.py`, `pibot_config.py`
- **Threads/processes:** receiver render worker
- **Interfaces:** YOLO in-process API
- **Verification:** status transitions `Loading model` -> `Model ready`; detection count updates
- **Repair:** fix `PIBOT_YOLO_MODEL_PATH`, reinstall dependencies, temporarily disable inference
- **Regression tests:** start/stop inference buttons toggle behavior without breaking video

### 10.8 Ollama / LLM

- **Symptoms:** final transcript present, assistant output shows `[Ollama error]` or hangs
- **Likely causes:** Ollama not running, wrong URL/model, request timeout
- **Files/modules:** `pc/services/ollama_service.py`, `pc/services/startup_checks.py`
- **Threads/processes:** OllamaService thread, Ollama external daemon
- **Interfaces/ports:** Ollama HTTP on 11434
- **Verification:** startup check `Ollama: reachable`, curl `/api/tags`
- **Repair:** start/restart Ollama daemon, use installed model name, fix URL
- **Regression tests:** speak phrase, verify streamed token output in assistant panel

### 10.9 Remote Commands / Streamer Control

- **Symptoms:** Start/Stop buttons fail, status stuck “Checking...”, wrong state shown
- **Likely causes:** SSH auth/network issues, stale pid files, wrong remote paths/venv
- **Files/modules:** `pc/services/pi_streamer_manager.py`, `pc/operator_console_app.py`
- **Threads/processes:** streamer action/status threads, SSH child processes
- **Interfaces/ports:** SSH control on 22
- **Verification:** refresh status output + manual SSH command parity
- **Repair:** fix SSH path/auth; clear stale pid files on Pi; restart streamer
- **Regression tests:** start/stop each streamer twice, including already-stopped path

### 10.10 Camera

- **Symptoms:** no real camera feed, synthetic frames only
- **Likely causes:** Picamera2 unavailable, camera init/config failure
- **Files/modules:** `pi/video/frame_source.py`, `pi/video/streamer.py`
- **Threads/processes:** Pi video streamer process
- **Interfaces:** Camera API
- **Verification:** Pi log indicates source `picamera2` or `synthetic`
- **Repair:** fix Pi camera drivers/configuration; validate camera with native tools
- **Regression tests:** confirm source returns to `picamera2` after fix

### 10.11 Microphone

- **Symptoms:** weak/no voice detection, excessive suppression
- **Likely causes:** wrong input device/channel, aggressive gate, system mic gain issues
- **Files/modules:** `pi/audio/device_selection.py`, `pi/audio/config.py`, `pi/audio_diagnostics.py`
- **Threads/processes:** Pi mic streamer process
- **Interfaces:** Audio capture + Audio UDP
- **Verification:** run `pi/audio_diagnostics.py` and inspect RMS/suppression stats
- **Repair:** select correct device, lower `NOISE_GATE_RMS`, tune AGC, fix ALSA levels
- **Regression tests:** repeated diagnostics with consistent pass conditions

### 10.12 Logging

- **Symptoms:** missing lines in GUI logs, sparse diagnostics
- **Likely causes:** `log_queue` full drops, worker not posting, high log volume
- **Files/modules:** `pc/logging_utils.py`, `pc/operator_console_app.py`
- **Threads/processes:** GUI drain timers, all worker threads
- **Interfaces:** Logging queue
- **Verification:** compare PC stdout with GUI logs
- **Repair:** reduce log flood, restart app, inspect queue-size pressure
- **Regression tests:** sustained operation still shows periodic logs (video/audio diagnostics)

### 10.13 Configuration

- **Symptoms:** startup checks fail; streamers launch but no data; wrong endpoints
- **Likely causes:** stale `pibot.env`, mixed env override values, invalid paths
- **Files/modules:** `pibot_config.py`, `pibot.env`, startup checks and service modules
- **Threads/processes:** startup-check thread, all dependent workers
- **Interfaces:** all dependent
- **Verification:** run startup checks + inspect resolved values + targeted command checks
- **Repair:** normalize config file, restart affected processes
- **Regression tests:** startup checks all green from clean launch

---

## 11) Special Focus: Streamer Control Lifecycle

Manifest references: `gui_controls` (streamer buttons), `interfaces` (SSH control), `processes` (Pi streamers, SSH child processes)

Detailed lifecycle for each action:

### 11.1 Start Video Streamer

1. GUI: **Start Video Streamer** -> `OperatorConsoleApp.start_video_streamer()`
2. Routes to `_run_streamer_action("video","start")`
3. Spawns `_streamer_action_worker` thread
4. Calls `PiStreamerManager.run_action("video","start")`
5. SSH command executes on Pi:
   - `cd <PIBOT_PI_PROJECT_PATH>`
   - `nohup <PIBOT_PI_VENV_PATH>/bin/python pi/video_udp_streamer.py > .run/video_streamer.log 2>&1 &`
   - writes PID to `.run/video_streamer.pid`
   - checks `kill -0` and returns `started`/`failed`
6. GUI status label updates immediately from SSH result
7. After 1 second, GUI refreshes only video streamer status
8. `query_status("video")` returns `running` or `stopped`
9. PC should then show video packets/frames and online network state (with heartbeat)

### 11.2 Stop Video Streamer

1. GUI button -> `stop_video_streamer()` -> `_run_streamer_action("video","stop")`
2. `run_action` SSH command:
   - if pid file exists: `kill <pid>`, remove pid file, echo `stopped`
   - else echo `already-stopped`
3. GUI updates status and refreshes actual state
4. Video packet/frame counts should stop increasing; network may go offline after heartbeat timeout

### 11.3 Start Mic Streamer

Same lifecycle as video with:

- script: `pi/mic_udp_streamer.py`
- log: `.run/mic_streamer.log`
- pid: `.run/mic_streamer.pid`
- expected PC effect: audio packet activity, RMS updates, Whisper pipeline activity

### 11.4 Stop Mic Streamer

Same stop semantics as video using mic pid/log files.

### 11.5 Common streamer-control failure modes

- `ssh-failed`: host unreachable, auth failure, timeout
- `failed`: remote command returned non-zero
- `running` shown but no traffic: wrong `PIBOT_PC_HOST` target or blocked UDP
- stale pid file points to dead process (query shows stopped)

### 11.6 Streamer-control verification checklist

1. Status label reports `running`
2. PID file exists on Pi and `kill -0 <pid>` succeeds
3. Corresponding `.run/*.log` shows active loop output
4. PC receives matching packet stream (audio or video)

Diagram: `docs/diagnostics/streamer_control_lifecycle.mmd`

---

## 12) Special Focus: Whisper Pipeline End-to-End

Manifest references: `interfaces` (Audio UDP, Whisper API, Ollama HTTP), `threads` (AudioReceiver, WhisperService, OllamaService)

Pipeline trace:

1. **Microphone capture on Pi** (`pi/audio/streamer.py`)
2. Channel select + AGC/gate (`pi/audio/signal_processing.py`)
3. UDP send to PC:5001 (`AUDIO_HEADER + PCM`)
4. **AudioReceiverService** receives packets, computes RMS, downsamples to 16k, enqueues `(chunk, rms)`
5. **WhisperService** consumes queue, maintains pre-roll and speech activity state
6. Partial transcript callback updates GUI
7. Phrase finalization on silence timeout or max phrase duration
8. Final transcription
9. Enqueue `PromptSubmission(phrase_id, text)` to `ollama_queue`
10. **OllamaService** POST stream to Ollama
11. Streamed tokens appended to assistant output

Failure points and diagnostics:

- Pi capture failure -> no PC packets
- over-aggressive gate -> no effective speech chunks
- audio queue full -> chunk drops, delayed/unstable transcription
- Whisper model load/transcribe exception -> empty text and error logs
- Ollama queue full -> dropped submission warning
- HTTP/Ollama failure -> `[Ollama error]` in output

Regression coverage in repo:

- `tests/test_whisper_service.py`
- `tests/test_e2e_whisper_to_ollama.py`

Diagram: `docs/diagnostics/whisper_pipeline_flow.mmd`

---

## 13) Special Focus: Video Pipeline End-to-End

Manifest references: `interfaces` (Video UDP, Heartbeat UDP, YOLO API, Camera API), `threads` (receiver poll + render worker)

Pipeline trace:

1. **Camera capture on Pi** (`open_camera()` with synthetic fallback)
2. JPEG encode in `pi/video/streamer.py`
3. Chunk payload using `CHUNK_HEADER`; send UDP packets to PC:5000
4. Send heartbeat packet every 500ms
5. **UDPVideoReceiver** polls non-blocking socket every 15ms
6. Chunk reassembly in `FrameBuffer`
7. Complete JPEG enqueued to render worker queue
8. Render worker decodes JPEG, optionally runs YOLO
9. Frame event posted to UI queue
10. Tk thread updates preview label and stats

Failure points and diagnostics:

- Camera unavailable -> synthetic source mode
- JPEG encode failures -> frame drops
- UDP loss -> incomplete frame buffers, reassembly warnings
- decode failure -> rising decode failure counter
- model load/inference error -> status messages and no overlay
- no heartbeat -> network state offline after ~2s

Diagram: `docs/diagnostics/video_pipeline_flow.mmd`

---

## 14) Diagnostic Command Playbooks

For each subsystem: PC commands, Pi commands, expected output, failure output, interpretation, recovery.

> Use project venv where needed: `source /home/jorg/pibot/venv/bin/activate` (PC) or Pi venv path.

### 14.1 GUI subsystem

- **PC command:** `python3 /home/jorg/pibot/pc/client.py`
- **Pi command:** N/A
- **Expected:** GUI opens; status bar updates CPU/memory/network every second
- **Failure:** traceback/import/tk errors
- **Interpretation:** local runtime dependency or display issue
- **Recovery:** reinstall deps, verify Tk availability, rerun

### 14.2 Networking / connection management

- **PC command:** `python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.bind(('0.0.0.0',5000)); s2=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s2.bind(('0.0.0.0',5001)); print('udp bind ok')"`
- **Pi command:** `ping -c 3 <pc_host>`
- **Expected:** bind ok + ping success
- **Failure:** bind errors or host unreachable
- **Interpretation:** port conflicts/firewall/path mismatch
- **Recovery:** free ports, fix host config, verify network route

### 14.3 Video streaming (sender)

- **PC command:** watch GUI packet/frame counters
- **Pi command:** `python3 /home/jorg/pibot/pi/video_udp_streamer.py`
- **Expected:** periodic log lines with frames/fps and packet counts
- **Failure:** camera initialization failed (synthetic fallback) or streamer errors
- **Interpretation:** camera stack or network target issue
- **Recovery:** fix camera environment; validate `PIBOT_PC_HOST`; restart streamer

### 14.4 Video receiver

- **PC command:** `python3 /home/jorg/pibot/pc/client.py` then Connect
- **Pi command:** ensure video streamer running
- **Expected:** `Video UDP packets detected`, FPS > 0, frame count increases
- **Failure:** decode failures, no frames despite packets
- **Interpretation:** payload corruption/loss or model/decode issues
- **Recovery:** reconnect, disable inference, reduce sender load

### 14.5 Audio streaming

- **PC command:** monitor logs for `Microphone activity` and audio meter updates
- **Pi command:** `python3 /home/jorg/pibot/pi/mic_udp_streamer.py`
- **Expected:** mic streamer startup line + PC packet and RMS activity
- **Failure:** no packets, audio queue full warnings, idle mic state
- **Interpretation:** capture, network, or queue pressure problem
- **Recovery:** restart mic stream, tune audio config, verify 5001 route

### 14.6 Whisper

- **PC command:** `python3 -m unittest /home/jorg/pibot/tests/test_whisper_service.py`
- **Pi command:** N/A
- **Expected:** tests pass; logs show speech detect/end/final/submission flow
- **Failure:** missing final transcript path, assertion failures
- **Interpretation:** segmentation/finalization regression
- **Recovery:** inspect threshold/silence logic and queue handling

### 14.7 Speech pipeline E2E

- **PC command:** `python3 -m unittest /home/jorg/pibot/tests/test_e2e_whisper_to_ollama.py`
- **Pi command:** N/A
- **Expected:** phrase flows through partial->final->submission in tests
- **Failure:** no submission, phrase ID/order mismatches
- **Interpretation:** broken handoff to `ollama_queue`
- **Recovery:** inspect `WhisperService` enqueue and queue capacity

### 14.8 Ollama

- **PC command:** `curl -sS http://localhost:11434/api/tags`
- **Pi command:** N/A
- **Expected:** JSON model list
- **Failure:** connection refused/timeout
- **Interpretation:** Ollama daemon unavailable or wrong URL
- **Recovery:** start Ollama, update `PIBOT_OLLAMA_URL`, rerun checks

### 14.9 Streamer control (SSH)

- **PC command:** `ssh <pi_user>@<pi_host> "echo ok"`
- **Pi command:** `ps -ef | grep -E 'mic_udp_streamer.py|video_udp_streamer.py' | grep -v grep`
- **Expected:** SSH succeeds; streamer process lines visible when running
- **Failure:** auth error, timeout, no process lines
- **Interpretation:** control plane broken or process not running
- **Recovery:** fix SSH access; start via GUI buttons or manual command

### 14.10 Camera

- **PC command:** observe GUI video source behavior via logs
- **Pi command:** `python3 /home/jorg/pibot/pi/video_udp_streamer.py` (look for camera init logs)
- **Expected:** `Camera opened successfully` or explicit synthetic fallback warning
- **Failure:** repeated camera init exceptions
- **Interpretation:** camera device/driver unavailable
- **Recovery:** fix camera stack/permissions and retest

### 14.11 Microphone

- **PC command:** monitor RMS and transcript status
- **Pi command:** `python3 /home/jorg/pibot/pi/audio_diagnostics.py`
- **Expected:** RMS values above gate threshold during speech, manageable suppression count
- **Failure:** very weak max RMS or mostly suppressed chunks
- **Interpretation:** gain/device/noise-gate issue
- **Recovery:** adjust gate/AGC and system mic levels

### 14.12 Logging

- **PC command:** compare logs tab with terminal output of PC app
- **Pi command:** `tail -n 100 /home/jorg/pibot/.run/mic_streamer.log; tail -n 100 /home/jorg/pibot/.run/video_streamer.log`
- **Expected:** active periodic diagnostics for running streamers
- **Failure:** empty/stale logs
- **Interpretation:** streamer not running or output redirected elsewhere
- **Recovery:** restart streamers and verify log path config

### 14.13 Configuration

- **PC command:** `cat /home/jorg/pibot/pibot.env`
- **Pi command:** `cat /home/jorg/pibot/pibot.env`
- **Expected:** consistent host/port/model settings across environments
- **Failure:** mismatched addresses/paths
- **Interpretation:** sender-target mismatch or wrong remote execution paths
- **Recovery:** normalize env file and restart affected processes

### 14.14 Video receiver + inference stress triage

- **PC command:** use GUI controls: Stop Inference then Start Inference while stream active
- **Pi command:** keep video streamer running
- **Expected:** video remains visible with/without inference; model status updates
- **Failure:** inference errors or frozen frames when toggled
- **Interpretation:** model/path/decode coupling issue
- **Recovery:** validate model path and dependency health; keep inference disabled temporarily

### 14.15 Remote PID management

- **PC command:** `ssh <pi_user>@<pi_host> "ls -l /home/jorg/pibot/.run/*.pid 2>/dev/null || true"`
- **Pi command:** `for f in /home/jorg/pibot/.run/*_streamer.pid; do [ -f \"$f\" ] && echo \"$f -> $(cat $f)\"; done`
- **Expected:** pid files map to live processes
- **Failure:** stale pid points to dead process
- **Interpretation:** unclean shutdown or manual process kill
- **Recovery:** remove stale pid file and restart streamer

---

## 15) Health Monitoring Recommendations (GUI Additions)

Manifest-aligned recommendations for missing or partially visible runtime indicators:

1. **Pi heartbeat age (ms)**  
   - Current: implicit online/offline state via `last_heartbeat_time`  
   - Recommend: explicit numeric age + warning threshold (e.g., >1500ms)

2. **Streamer process status with PID**  
   - Current: running/stopped text only  
   - Recommend: include remote PID and last status check timestamp

3. **Thread health panel**  
   - Current: no explicit worker alive/dead indicators  
   - Recommend: list AudioReceiver/Whisper/Ollama/Video worker alive state

4. **Queue depth indicators**  
   - Current: only occasional log messages  
   - Recommend: live `audio_queue`, `ollama_queue`, render/ui queue sizes

5. **Last packet/frame timestamps**  
   - Current: internal only  
   - Recommend: surface “last audio packet”, “last video packet”, “last frame rendered”

6. **Whisper pipeline state**  
   - Current: transcript status text  
   - Recommend: state machine display (Listening / Speech Active / Processing / Paused)

7. **LLM state**  
   - Current: generic status text  
   - Recommend: request start time, first-token latency, stream duration

8. **Network latency estimate**  
   - Current: none  
   - Recommend: heartbeat jitter/age trend or active ping metric

9. **Host resource telemetry**  
   - Current: local CPU/memory only  
   - Recommend: optional Pi CPU/memory (via SSH query) and PC worker load summary

10. **Error counters**  
   - Current: some counters in logs  
   - Recommend: visible decode failures, dropped audio chunks, failed SSH actions

---

## 16) Manifest vs Implementation Notes

1. `pc/services/thread_monitor.py` exists in manifest but is **not currently wired** into `OperatorConsoleApp`.
2. Heartbeat packets are implemented in `pi/video/streamer.py` and consumed in `pc/video/receiver_widget.py`; network-online status uses heartbeat or audio+video recency fallback.
3. Streamer status is pid-file-based (`.run/*_streamer.pid`) plus `kill -0`; there is no richer remote supervisor.
4. Startup checks are asynchronous one-shot worker threads, not persistent monitors.

---

## 17) Operational Baseline Checklist

1. Launch PC app (`pc/client.py`)
2. Run startup checks until model/UDP/Ollama are healthy
3. Start Pi streamers (GUI streamers tab or manual on Pi)
4. Connect GUI and confirm:
   - audio meter active
   - video packets/frames increasing
   - network state online
5. Validate whisper->final transcript->assistant output flow
6. Validate start/stop lifecycle for both streamers

If any step fails, use sections 10 and 14 for targeted diagnosis and repair.
