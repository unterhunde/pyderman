# SSH False-Negative Reliability Fix (2026-06-26)

## Actions Taken

1. Updated `pc/services/pi_streamer_manager.py` start path to launch streamers via a short remote Python spawner using:
   - `stdin=subprocess.DEVNULL`
   - `stdout` to `.run/<streamer>_streamer.log`
   - `stderr=subprocess.STDOUT`
   - `close_fds=True`
   - `start_new_session=True`
2. Preserved PID/log files:
   - `.run/mic_streamer.pid`
   - `.run/video_streamer.pid`
   - `.run/mic_streamer.log`
   - `.run/video_streamer.log`
3. Added SSH outcome classification in `run_action(..., "start")`:
   - `transport-failed`
   - `remote-command-failed`
   - `started-but-ack-failed`
   - `started/status-confirmed-running`
4. Added timeout reconciliation: on start timeout, call `query_status()` and return success when confirmed running.
5. Kept stop behavior unchanged (SIGTERM -> wait -> SIGKILL -> remove PID only after confirmed dead).
6. Kept `query_status()` PID cmdline guard unchanged.

## Rationale

The RCA proved false negatives were caused by SSH command timeout after remote process already started. The fix prevents SSH FD inheritance into the streamer process and reconciles timeout outcomes against actual remote status.

## Files Changed

- `pc/services/pi_streamer_manager.py`
- `tests/test_pi_streamer_manager.py`
- `docs/implementation/ssh_false_negative_reliability_fix_2026-06-26.md`

## Before/After Command Shape

### Before (start)

```sh
cd <pi_project> && \
nohup <pi_venv>/bin/python pi/<mic|video>_udp_streamer.py > <log> 2>&1 & \
echo $! > <pid_file>; \
for i in $(seq 1 4); do sleep 0.5; kill -0 $(cat <pid_file>) 2>/dev/null || break; done; \
kill -0 $(cat <pid_file>) 2>/dev/null && echo started || echo failed
```

### After (start)

```sh
cd <pi_project> && \
start_pid=$(<pi_venv>/bin/python -c "<spawner>" <log> <target_script> <pi_venv>/bin/python); \
if [ -n "$start_pid" ]; then
  echo "$start_pid" > <pid_file>;
  for i in $(seq 1 4); do sleep 0.5; kill -0 "$start_pid" 2>/dev/null || break; done;
  kill -0 "$start_pid" 2>/dev/null && echo started || echo failed;
else
  echo failed;
fi
```

Spawner details (`<spawner>`):
- `subprocess.Popen([python_bin, target_script], stdin=DEVNULL, stdout=log_handle, stderr=STDOUT, close_fds=True, start_new_session=True)`
- prints spawned PID for PID-file write.

## Test Results

### Targeted tests for this fix

Command:

```sh
python3 -m unittest -q tests.test_pi_streamer_manager
```

Result:
- `Ran 19 tests in 0.003s`
- `OK`

Added/updated assertions cover:
- start command detaches stdio/inherited descriptors
- timeout with confirmed running does not return `ssh-failed`
- timeout with not-running returns failure
- nonzero SSH failure remains failure

### Full available test suite

Command:

```sh
python3 -m unittest discover -s tests -q
```

Result:
- `Ran 25 tests`
- 2 pre-existing environment/import errors:
  - `ModuleNotFoundError: No module named 'scipy'`
  - `ModuleNotFoundError: No module named 'whisper'`

## Live Pi Validation Evidence

### Single-cycle validation

- `start mic`: `elapsed=2.808s`, result `(True, 'started')`
- `refresh mic`: `(True, 'running')`
- `start video`: `elapsed=6.095s`, result `(True, 'started')`
- `refresh video`: `(True, 'running')`
- `stop mic`: `(True, 'stopped')`, refresh `(False, 'stopped')`
- `stop video`: `(True, 'stopped')`, refresh `(False, 'stopped')`

No 20s timeout false-negative observed.

### Rapid start/stop validation (10 cycles, both streamers)

- `fail_count=0`
- `mic start avg=2.783s max=2.888s`
- `video start avg=2.808s max=2.841s`
- `mic stop avg=0.948s max=0.974s`
- `video stop avg=1.242s max=1.266s`

All refresh checks matched expected running/stopped state.

## Remaining Defects / Notes

1. Full test suite is still blocked by missing optional dependencies in this environment (`scipy`, `whisper`), unrelated to this fix.
2. One single-cycle `video start` sample measured `6.095s` (above ideal `<5s`), but repeated rapid validation stayed below 5s and showed no timeout regressions.
