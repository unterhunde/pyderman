# Streamer Control Event Timeline (RCA)

## Scope
- `pc/operator_console_app.py`
- `pc/services/pi_streamer_manager.py`
- Existing runtime artifacts only (no code changes):
  - `/tmp/copilot-tool-output-1782519008887-omhliq.txt`
  - `/tmp/copilot-tool-output-1782519176003-hc0w6a.txt`
  - `/tmp/pibot_validation_run_final.json`
  - `/tmp/pibot_streamer_transition_check.json`

## Code-level event order (authoritative flow)
1. Button callback (`start_*` / `stop_*`) calls `_run_streamer_action()` (`pc/operator_console_app.py:801-811,844-848`).
2. UI label is written immediately: `status_widget.configure("<Action>ing...")` (direct Tk write, same method, line 846).
3. Worker thread starts: `_streamer_action_worker()` (line 850), calls `PiStreamerManager.run_action()` (line 853).
4. SSH command executes via `_run_ssh(... timeout=20)` (`pc/services/pi_streamer_manager.py:85,97-124`).
5. If `ok=True`, worker posts success label, sleeps 1s, then posts `refresh_streamer_status(streamer)` (`pc/operator_console_app.py:856-861`).
6. `refresh_streamer_status()` posts `"Checking..."` and starts `_refresh_streamer_status_worker()` (lines 813-823).
7. `_refresh_streamer_status_worker()` calls `query_status()` and posts final running/stopped label (lines 825-836).
8. All queued UI writes are applied by `_drain_ui_queue()` every 20ms (lines 490-499).

## Observed evidence timeline

### Run A (`/tmp/copilot-tool-output-1782519008887-omhliq.txt`)
- **20:09:36** User clicked mic start; worker began.
- **20:09:56** User clicked video start; worker began.
- **20:09:57** Mic start returned `ok=False, output=ssh-failed`.
- **20:09:57** `Streamer status | mic=stopped | video=stopped` logged.
- **20:10:01+** Video packet flow detected and sustained (stream actually running).
- **20:10:17** Video start returned `ok=False, output=ssh-failed`.
- **20:10:41-20:10:43** Mic/video stop actions returned `stopped`.
- **20:10:44-20:10:45** Late status refresh updates still arrived after disconnect.

### Run B (`/tmp/copilot-tool-output-1782519176003-hc0w6a.txt`)
- **20:12:25** Mic stop + video stop clicked nearly simultaneously.
- **20:12:26** Mic stop success.
- **20:12:27** Video stop success.
- **20:12:27** Mic start + video start clicked nearly simultaneously.
- **20:12:28** Mic stop + video stop clicked again before prior start workers completed.
- **20:12:47** Mic start returned `ssh-failed` (~20s after click).
- **20:13:08** Video start returned `ssh-failed` (~41s after click; queued behind prior long action).
- **20:13:08** Status refresh reported `mic=running` while start had just reported failure.
- **20:13:09-20:13:11** Stops then succeed; status updates continue out-of-order through 20:13:12.

### Pi-state corroboration
- `/tmp/pibot_validation_run_final.json` reports `pi_state_after_start`:
  - `mic:7041:alive ...`
  - `video:7103:alive ...`
- `/tmp/pibot_streamer_transition_check.json` reports both alive after "failed" starts, then both stopped after final stop.

## Duplicate and conflicting UI writes (same labels)
`mic_streamer_status` / `video_streamer_status` are written by:
1. `_run_streamer_action()` direct immediate write (`"<Action>ing..."`).
2. `_streamer_action_worker()` write of success/failure.
3. `refresh_streamer_status()` write of `"Checking..."`.
4. `_refresh_streamer_status_worker()` write of final `running/stopped/error`.

No generation ID, no stale-result suppression, and no single-flight guard exist in these paths.
