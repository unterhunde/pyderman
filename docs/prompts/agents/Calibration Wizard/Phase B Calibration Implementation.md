You are the Runtime Implementation Agent.

## Goal

Implement AUDIO-001 Phase B: integrate real Pi-to-PC calibration telemetry, synchronized stage capture, and a live telemetry-backed metrics provider into the existing Calibration Wizard.

Preserve all validated Phase A behavior, simulation safeguards, state-machine behavior, and regression coverage.

Read `"docs/AI Engineering Framework/project_state.json"` first.

Follow the applicable standards in `"docs/AI Engineering Framework/"`.

Use these artifacts as the authoritative handoff:

* `"docs/Agent Docs/architecture/audio_001_microphone_calibration_wizard_architecture_review_2026-06-27.md"`
* `"docs/Agent Docs/implementation/audio_001_phase_a_calibration_wizard_implementation_2026-06-27.md"`
* `"docs/Agent Docs/implementation/audio_001_sim_ui_001_phase_a_calibration_wizard_simulation_label_fix_2026-06-27.md"`
* `"docs/Agent Docs/validation/audio_001_phase_a_calibration_wizard_revalidation_sim_ui_001_2026-06-27.md"`

## Phase B boundary

Implement only:

* real Pi calibration telemetry
* PC telemetry reception and aggregation
* synchronized stage capture using session, stage, and audio-sequence identifiers
* a live telemetry-backed calibration metrics provider
* live/near-live metric display in the existing wizard
* explicit distinction between simulation mode and live telemetry mode
* connection-loss and incomplete-capture handling

Do not implement Phase C or later functionality, including:

* automatic parameter sweeps
* recommendation engine
* temporary calibration-value application
* production configuration persistence
* automatic promotion of calibration values
* hardware-defect conclusions

## Required architecture

Preserve the existing UDP audio packet format.

Use a separate, versioned, low-rate diagnostics/control channel for calibration telemetry and session commands.

Before implementing the channel, define:

* transport type
* bind and target hosts
* configurable port
* message framing
* schema version
* session ownership
* request, acknowledgement, and error semantics
* timeout behavior
* disconnect behavior
* stage and sequence correlation

Do not hard-code host addresses or ports when the existing configuration system can supply them.

## Allowed scope

The agent may create or modify files directly required for Phase B, including:

### PC-side

* `pc/gui/calibration_wizard_panel.py`
* `pc/services/calibration_session_controller.py`
* `pc/services/calibration_metrics_provider.py`
* a new telemetry client or adapter module
* a new telemetry aggregation module
* runtime configuration only as needed to expose a configurable diagnostics port
* directly related tests

### Pi-side

* `pi/audio/streamer.py`, only where hooks are required to collect real metrics
* `pi/audio/signal_processing.py`, only where non-invasive metrics exposure is required
* new calibration session, telemetry, or control modules
* runtime configuration only as needed to expose the diagnostics channel
* directly related tests

Prefer creating isolated Phase B modules over embedding networking and telemetry logic throughout existing audio code.

## Preserve

* existing UDP audio protocol and packet format
* existing microphone streaming behavior outside calibration mode
* existing Whisper and segmentation behavior
* existing streamer start/stop behavior
* Phase A state-machine transitions
* cancellation and stale-callback suppression
* simulation provider and simulation warning behavior
* all currently passing tests

## Required behavior

### 1. Provider modes

Support at least two explicit provider modes:

* `simulation`
* `live_telemetry`

The wizard must display:

* `SIMULATION MODE` when using the deterministic provider
* `LIVE TELEMETRY MODE` when receiving real Pi metrics

The live mode must not display simulated results or simulation warnings.

### 2. Calibration session identity

Every live calibration run must have a unique session identifier.

Every captured stage must include:

* session ID
* stage ID
* stage type
* start timestamp
* end timestamp
* audio sequence start
* audio sequence end
* chunks captured
* chunks dropped or missing

Telemetry from an old or cancelled session must not update the current wizard.

### 3. Real telemetry metrics

Expose real Pi-side metrics sufficient to populate the existing provider contract, including:

* raw RMS
* processed RMS
* peak
* clipping ratio or clipping indicator
* gate-active ratio
* AGC gain
* active channel
* chunks captured
* sequence range
* dropped or missing chunks

Where practical, provide rolling live values during preview and aggregate stage summaries after capture.

### 4. Live preview

While in preview or an active stage, display live or near-live:

* raw RMS
* processed RMS
* peak
* gate state or gate ratio
* AGC gain
* telemetry connection state

Avoid blocking the Tk main thread.

Throttle display updates to a reasonable rate while retaining all stage data needed for aggregation.

### 5. Synchronized stage capture

When the operator begins a stage:

1. The PC opens a named calibration stage.
2. The Pi resets stage-specific metric accumulators without disrupting the audio stream.
3. The Pi records metrics for the exact stage window.
4. The Pi returns a summary tied to the session ID, stage ID, and audio sequence range.
5. The PC verifies that the telemetry summary corresponds to the current stage.
6. The wizard marks capture success only when required telemetry is complete and valid.

Do not mark a stage successful solely because a timer expired.

### 6. Failure handling

Handle at minimum:

* Pi unavailable
* diagnostics channel connection failure
* telemetry timeout
* malformed or unsupported message version
* mismatched session or stage ID
* stale telemetry
* missing sequence range
* incomplete stage metrics
* operator cancellation
* calibration tab closed during capture

On failure:

* do not persist settings
* invalidate the active stage
* suppress stale callbacks and messages
* keep the existing audio stream in a known state
* allow safe retry or cancellation
* display a clear operator-facing reason

### 7. Simulation fallback

The simulation provider must remain available for:

* UI development
* automated tests
* explicit offline simulation mode

Do not silently fall back from live mode to simulation mode. Require explicit selection or clearly visible operator acknowledgement.

## Threading and concurrency

* All Tkinter updates must occur on the Tk main thread.
* Network receive and telemetry processing must not block the GUI.
* Use queues, scheduled polling, or an equivalent thread-safe handoff.
* Use session and generation identifiers to reject stale telemetry.
* Ensure cancellation closes or invalidates active Phase B work safely.
* Avoid arbitrary sleeps as synchronization.

## Tests

Add or update tests for:

### Protocol and telemetry

* message serialization and parsing
* schema-version rejection
* required-field validation
* session and stage correlation
* malformed-message handling
* timeout behavior
* stale-message rejection

### Live provider

* live provider metadata reports `live_telemetry`
* real telemetry fields map correctly to the provider contract
* aggregate stage summary is produced only from a complete stage
* incomplete telemetry yields capture failure
* simulation and live providers remain behaviorally distinct

### Controller and UI integration

* live mode is clearly labeled
* simulation warning is absent in live mode
* simulation warning remains present in simulation mode
* live preview updates do not violate Tk thread ownership
* cancelled sessions reject later telemetry
* failed telemetry prevents `Next`
* retry starts a new stage/session generation
* existing Phase A state transitions remain valid

### Regression

* all Phase A tests continue to pass
* streamer-manager tests continue to pass
* existing GUI integration tests continue to pass
* the normal microphone streamer remains operational outside calibration mode

## Validation commands

Use the project virtual-environment interpreter for all commands.

First verify the interpreter:

```bash
./.venv/bin/python -c "import sys; print(sys.executable); print(sys.version)"
```

Run all new Phase B tests plus the existing Phase A and regression suites:

```bash
./.venv/bin/python -m unittest \
  tests.test_calibration_metrics_provider \
  tests.test_calibration_session_controller \
  tests.test_calibration_wizard_panel \
  tests.test_operator_console_streamer_reliability \
  tests.test_pi_streamer_manager
```

Include any new Phase B protocol, telemetry, and aggregation test modules in the targeted command.

Then run:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Also verify normal application launch with:

```bash
./.venv/bin/python pc/client.py
```

## Implementation validation

Before handing off, demonstrate:

1. Simulation mode still works and is clearly labeled.
2. Live telemetry mode connects to the actual Pi.
3. Real microphone metrics appear in preview.
4. Silence, normal-speech, and loud-speech stages return real synchronized summaries.
5. Stage completion depends on valid telemetry, not only elapsed time.
6. Cancellation rejects delayed telemetry.
7. Disconnect and timeout paths fail safely.
8. Existing non-calibration audio streaming remains functional.
9. No calibration values are changed or persisted.
10. All targeted and full regression tests pass, or any failure is precisely documented.

Implementation validation is not a substitute for independent Validation / Test Agent review.

## Restrictions

* Do not implement Phase C.
* Do not add automatic parameter sweeps.
* Do not implement recommendation scoring.
* Do not persist calibration settings.
* Do not change production calibration values.
* Do not alter the existing UDP audio payload format.
* Do not redesign unrelated GUI controls.
* Do not update `"docs/AI Engineering Framework/project_state.json"`.
* Do not fix unrelated issues or dependencies.

## Output

Produce an Implementation Record compliant with `"docs/AI Engineering Framework/Report_Standards.md"` and save it in `"docs/Agent Docs/implementation/"`.

Include:

* files created and modified
* diagnostics/control protocol definition
* message schema and versioning
* PC/Pi responsibility split
* session and sequence synchronization design
* provider-mode design
* threading and stale-message safeguards
* failure and cancellation handling
* tests added or updated
* exact commands and results
* live Pi implementation evidence
* remaining Phase C work
* recommended next agent
* recommended independent validation objective
