# AUDIO-001 Phase B — Runtime Implementation Record
**Date:** 2026-06-27  
**Agent:** Runtime Implementation Agent (continuation session)  
**Ticket:** AUDIO-001 Phase B

---

## Summary

Phase B implementation of the Calibration Wizard was complete from a module-creation standpoint at the start of this session. All Phase B production modules had been created by the prior agent:

- `calibration_protocol.py` — versioned diagnostics/control protocol
- `pc/services/calibration_telemetry_aggregation.py` — telemetry payload validation and mapping
- `pc/services/calibration_telemetry_client.py` — TCP telemetry client (bounded deque, thread-safe)
- `pc/services/calibration_metrics_provider.py` — `LiveTelemetryCalibrationMetricsProvider` + updated `SimulatedCalibrationMetricsProvider`
- `pc/services/calibration_session_controller.py` — state-machine controller with live polling
- `pc/gui/calibration_wizard_panel.py` — wizard panel (simulation/live mode labeling)
- `pi/audio/calibration_telemetry.py` — Pi-side `CalibrationTelemetryServer` and `_StageAccumulator`

The previous session consumed excessive RAM and destabilized VS Code/Ubuntu before completing test validation.

---

## Excessive-Resource Issue

**Cause:** The previous session encountered a process hang caused by an unbounded polling callback reschedule loop in the unit test scheduler. The `_schedule_live_poll` callback in `CalibrationSessionController` is designed to reschedule itself indefinitely (every 250 ms) while the wizard is active. The `_FakeScheduler.run_all()` helper in the controller tests drains the heap until empty. When `run_all()` was called while the controller was in an active polling state, the poll callback re-added itself faster than real time advanced, producing an infinite loop that consumed a CPU core indefinitely, preventing the Python process from terminating, and eventually destabilizing VS Code.

---

## Identified Hang Mechanisms

### Mechanism 1: Live poll runs after successful stage capture

**Location:** `_schedule_live_poll._tick()` in `pc/services/calibration_session_controller.py`

After `_finish_capture()` completes a stage successfully, `_stage_capture_complete` is set to `True` but the state remains at `CAPTURE_*` (not a terminal state). The live poll stop-condition only checked for `{IDLE, COMPLETE, CANCELLED, FAILED}`. Since `CAPTURE_SILENCE` (etc.) was not in that set, the poll kept rescheduling every 250 ms. `run_all()` in `_run_stage_capture()` never terminated.

### Mechanism 2: Live poll runs indefinitely in PREPARE state after repeat

**Location:** `_FakeScheduler.run_all()` in `tests/test_calibration_session_controller.py`

`test_stale_callback_suppression_on_repeat` calls `run_all()` after `repeat_stage()` while the controller is in `PREPARE_SILENCE` with `_stage_capture_complete = False`. Even after Mechanism 1 was fixed, the PREPARE-state live poll has no natural termination point because the test does not call `start_stage()` before `run_all()`. The `run_all()` helper had no iteration limit.

---

## Exact Fixes

### Fix 1 — Stop rescheduling after capture completes

**File:** `pc/services/calibration_session_controller.py`  
**Location:** `_schedule_live_poll._tick()`

Added a `_stage_capture_complete` guard before re-scheduling:

```python
# Stop polling once a stage capture has finished; the next stage
# start or state transition will restart polling.
if self._stage_capture_complete:
    return
```

**Effect:** After `_finish_capture()` sets `_stage_capture_complete = True`, the next firing of the live poll returns without re-scheduling. Polling automatically restarts when `start_stage()` or `_enter_prepare_stage()` resets `_stage_capture_complete = False`.

**Polling stop guarantees after fix:**

| Condition | Mechanism |
|---|---|
| Polling stops after failure | `FAILED` in terminal-state check |
| Polling stops after cancellation | `CANCELLED` in terminal-state check |
| Polling stops after close | `IDLE` in terminal-state check |
| Polling stops after timeout | Timeout → FAILED → terminal-state check |
| Polling stops after capture completes | `_stage_capture_complete` guard (new) |
| Stale callbacks cannot reschedule | `_token_current(token)` generation check |

### Fix 2 — Bound `run_all()` against infinite reschedule loops

**File:** `tests/test_calibration_session_controller.py`  
**Location:** `_FakeScheduler.run_all()`

Added a `max_steps=2000` iteration guard:

```python
def run_all(self, max_steps: int = 2000) -> None:
    steps = 0
    while self._queue and steps < max_steps:
        next_due = self._queue[0][0] - self._now_ms
        self.advance(max(next_due, 0))
        steps += 1
```

**Effect:** All bounded callback chains (stage captures with `prepare_seconds=2`, `capture_seconds=2`) terminate naturally well under 2000 steps (approximately 50–100 steps per stage). The guard only activates for the one test that calls `run_all()` while polling is intentionally infinite (PREPARE state), and 2000 steps in that state still leave the controller in the expected `PREPARE_SILENCE` state.

---

## Bounded-Resource Safeguards Added / Confirmed

| Safeguard | Location |
|---|---|
| Bounded telemetry deque (`maxlen=500`) | `CalibrationTelemetryClient._telemetry` |
| Bounded outbound queue (`maxsize=200`) | `CalibrationTelemetryServer._outbound` |
| Single active TCP client per server (kick-prior-on-new-connect) | `CalibrationTelemetryServer._serve()` |
| Socket receive timeout (0.25 s) prevents recv block | Client and server sockets |
| Receiver thread terminates deterministically on `stop_event` | `CalibrationTelemetryClient._receiver_loop()` |
| Server thread terminates deterministically on `_shutdown` | `CalibrationTelemetryServer._serve()` |
| Live poll stops on stale token (generation guard) | `_schedule_live_poll._tick()` |
| Live poll stops on terminal state | `_schedule_live_poll._tick()` |
| Live poll stops after capture completes | `_schedule_live_poll._tick()` (Fix 1) |
| `run_all()` bounded to 2000 steps | `_FakeScheduler.run_all()` (Fix 2) |
| Stage data cleared on cancel, close, end-session | `CalibrationSessionController` + `CalibrationTelemetryServer` |
| No raw audio buffer retention | All Phase B modules |
| No heavyweight runtime imports in unit tests | All Phase B tests use stubs |

---

## Tests Created This Session

| Module | Tests | Coverage |
|---|---|---|
| `tests/test_calibration_protocol.py` | 25 | Protocol serialization, schema-version rejection, required-field validation, JSON decode errors |
| `tests/test_calibration_telemetry_aggregation.py` | 21 | Stage accumulator aggregation, missing-chunk detection, drop accounting, session/stage ID correlation, validation helpers |
| `tests/test_calibration_live_provider.py` | 26 | Live provider metadata, session lifecycle, stage open/close, field mapping, stale-session rejection, malformed-payload skip, simulation vs live distinction |

All tests use in-memory stubs; no real sockets, threads, or network connections.

---

## Tests Fixed This Session

| Module | Test | Issue |
|---|---|---|
| `tests/test_calibration_metrics_provider.py` | `test_deterministic_for_same_input` | Pre-existing timing flakiness: `capture()` uses `time.time()` for timestamps making full-equality comparison non-deterministic when running in a suite. Fixed by comparing individual deterministic fields rather than full dataclass equality. |

---

## Tests Run Individually (in order per policy)

1. `tests.test_calibration_protocol` — **25/25 PASS**
2. `tests.test_calibration_telemetry_aggregation` — **21/21 PASS**
3. `tests.test_calibration_live_provider` — **26/26 PASS**
4. `tests.test_calibration_metrics_provider` — **3/3 PASS**
5. `tests.test_calibration_session_controller` — **11/11 PASS** (after fixes)
6. `tests.test_calibration_wizard_panel` — **2/2 PASS**
7. `tests.test_operator_console_streamer_reliability` — **3/3 PASS**
8. `tests.test_pi_streamer_manager` — **19/19 PASS**
9. Full discovery (`tests/test_*.py`) — **117/117 PASS** (0.178 s targeted suite, 1.578 s full discovery)

---

## Tests Deliberately Deferred

| Test category | Reason for deferral |
|---|---|
| Real Pi network integration | Requires live Pi device; validates over SSH; deferred to Validation / Test Agent |
| End-to-end GUI launch (`pc/client.py`) | Requires Tkinter/display; validates full application stack; deferred to Validation / Test Agent |
| `test_e2e_whisper_to_ollama.py` | Long-running, requires Whisper + Ollama; passes in current discovery (7 tests) but not re-run individually |
| `test_ollama_service.py` | Passes in current discovery (2 tests) but not re-run individually |
| Long-duration reliability testing | Out of scope for unit-test phase |

---

## Phase A Behavior Preserved

- All 11 Phase A controller state-machine tests pass
- All 3 Phase A metrics provider tests pass
- All 2 Phase A wizard panel formatting tests pass
- All streamer-manager regression tests pass
- All Whisper/Ollama service tests pass
- Simulation provider, simulation warning, and simulation mode labeling unchanged
- UDP audio protocol and packet format unchanged

---

## Remaining Validation Required

1. **Live Pi integration**: connect `LiveTelemetryCalibrationMetricsProvider` to a real Pi running `CalibrationTelemetryServer` and verify:
   - session open/close protocol roundtrip
   - stage open/close with real audio chunk accumulation
   - live telemetry preview in VERIFYING and PREVIEW wizard states
   - stage capture success/failure based on real telemetry
   - disconnect and timeout failure paths

2. **GUI smoke test**: launch `pc/client.py`, navigate the calibration wizard in both simulation mode and live mode, confirm mode labels, simulation warning presence/absence, and cancellation behavior.

3. **Cancellation under live connection**: cancel a live session mid-capture, verify the Pi-side server resets cleanly and accepts a new session.

4. **Non-calibration streaming unaffected**: start/stop the normal UDP audio streamer while calibration is idle; verify no interference.

---

## Recommended Next Agent

**Validation / Test Agent** — to execute:
1. Live Pi integration tests against a running Pi device
2. GUI smoke test via `pc/client.py`
3. End-to-end session-capture-complete workflow in live mode
4. Cancellation and disconnect failure-path validation
5. Confirm all 117 unit tests pass in the validation environment

Do **not** update `docs/AI Engineering Framework/project_state.json` until the Validation Agent signs off.
