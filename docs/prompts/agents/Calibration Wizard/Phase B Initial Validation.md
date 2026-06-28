You are the Validation / Test Agent.

## Goal

Independently validate AUDIO-001 Phase B against the real PC and Raspberry Pi runtime.

Prove that the Calibration Wizard can receive live microphone telemetry, display real metrics, complete synchronized capture stages, and fail safely without affecting normal PiBot audio streaming.

Read `"docs/AI Engineering Framework/project_state.json"` first.

Follow the applicable standards in `"docs/AI Engineering Framework/"`.

Use this implementation record as the primary handoff:

`"docs/Agent Docs/implementation/audio_001_phase_b_calibration_wizard_implementation_2026-06-27.md"`

Also use:

* `"docs/Agent Docs/architecture/audio_001_microphone_calibration_wizard_architecture_review_2026-06-27.md"`
* `"docs/Agent Docs/validation/audio_001_phase_a_calibration_wizard_revalidation_sim_ui_001_2026-06-27.md"`

## Validation boundary

Validate Phase B only:

* real Pi calibration telemetry server
* PC telemetry client
* live telemetry-backed metrics provider
* session and stage correlation
* synchronized capture summaries
* live Calibration Wizard mode
* cancellation, timeout, disconnect, and stale-message handling
* regression safety for normal audio streaming

Do not validate or implement Phase C features:

* parameter sweeps
* recommendation engine
* temporary calibration-value application
* production persistence
* automatic calibration promotion

## Restrictions

* Do not edit production code.
* Do not edit tests.
* Do not repair defects during validation.
* Do not update `"docs/AI Engineering Framework/project_state.json"`.
* Do not run unbounded scripts or repeated full-suite loops.
* Use one validation activity at a time.
* Add explicit timeouts to commands that may block.
* Stop and document any test that causes abnormal memory growth, repeated reconnect loops, or orphaned processes.

## Environment verification

Before testing:

1. Confirm the PC project virtual environment.
2. Confirm the Pi host and active project path.
3. Record the telemetry transport type, host, and configured port.
4. Confirm no stale calibration telemetry server or client process is running.
5. Confirm the normal microphone streamer can start and stop before calibration testing.

Use the project interpreter for PC commands:

```bash
./.venv/bin/python
```

## Required validation

### 1. Unit and regression baseline

Run once:

```bash
timeout 120s ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Confirm the expected 117 tests pass, or document any difference precisely.

Do not repeatedly rerun the full suite.

### 2. Real application launch

Launch:

```bash
./.venv/bin/python pc/client.py
```

Verify:

* application starts normally
* Calibration tab is present
* simulation mode still works
* live telemetry mode is available
* existing tabs and controls remain accessible
* no startup exception or runaway polling occurs

### 3. Pi telemetry server startup

Start the Pi-side calibration telemetry service through the intended production integration path.

Verify:

* the service binds to the configured interface and port
* only the intended host can connect, according to implementation design
* startup does not disrupt the normal UDP microphone streamer
* repeated start does not create duplicate servers
* stop terminates the server deterministically

Record:

* process ID
* listening socket
* startup and shutdown output
* any log messages

### 4. Live telemetry connection

Select live telemetry mode in the Calibration Wizard.

Verify:

* the UI clearly displays `LIVE TELEMETRY MODE`
* the simulation warning is not shown
* connection state is visible
* the PC client connects to the real Pi
* session-open acknowledgement succeeds
* the session ID matches on both sides

Do not allow silent fallback to simulation mode.

### 5. Live preview

During preview, verify that real values update for:

* raw RMS
* processed RMS
* peak
* gate state or gate ratio
* AGC gain
* telemetry connection status

Confirm:

* values respond when the operator is silent
* values respond when the operator speaks
* UI updates remain responsive
* Tkinter updates remain on the main thread
* telemetry polling does not continue after preview ends

### 6. Synchronized stage capture

Complete:

1. Silence stage
2. Normal speech stage at approximately two feet
3. Loud speech stage
4. Optional phrase stage, if enabled

For every stage, record:

* PC session ID
* stage ID
* stage type
* start and end timestamps
* Pi sequence start and end
* chunks captured
* chunks dropped or missing
* raw RMS summary
* processed RMS summary
* peak
* clipping
* gate-active ratio
* AGC gain statistics
* capture success or failure

Verify:

* stage completion requires a valid Pi summary
* a timer alone cannot mark the stage successful
* returned session and stage IDs match the active stage
* sequence ranges are present and logically ordered
* metrics differ meaningfully between silence and speech
* results are labeled as live telemetry, not simulated

### 7. Cancellation safety

Test cancellation during:

* live preview
* prepare countdown
* active capture
* stage-summary wait

Verify:

* current session is invalidated
* Pi stage state is cleared
* delayed telemetry cannot update the cancelled wizard
* polling stops
* no orphaned threads, sockets, or processes remain
* a new calibration session can start successfully afterward

### 8. Disconnect and timeout behavior

During an active live stage:

* stop or interrupt the Pi telemetry server
* observe the PC response
* restore the server and retry

Verify:

* the active stage fails clearly
* `Next` remains disabled
* no simulated fallback occurs
* the UI remains responsive
* polling and retries are bounded
* reconnect does not reuse the stale session
* the new session receives a new session ID

### 9. Stale and mismatched telemetry

Where practical, inject or reproduce:

* old session ID
* old stage ID
* malformed payload
* unsupported schema version
* incomplete stage summary

Verify each is rejected and does not alter the current wizard state.

Do not modify production code to perform this test; use existing protocol test utilities or a short bounded external client.

### 10. Normal audio regression

With calibration idle:

* start the normal Pi microphone streamer
* verify UDP audio reaches the PC
* start and stop listening
* verify existing audio controls still work
* stop the streamer
* confirm process termination

Then repeat after one completed and one cancelled calibration session.

Verify calibration mode does not leave the normal audio pipeline in a degraded state.

### 11. Resource and lifecycle checks

After each live test group, inspect for:

* lingering Python calibration processes
* open telemetry sockets
* repeated reconnect threads
* increasing queue or telemetry history size
* abnormal memory growth

Use bounded observations only.

Record process and memory evidence if any issue appears.

## Pass criteria

Phase B passes only if:

* the real PC connects to the real Pi telemetry server
* live preview displays real microphone metrics
* all required stages produce valid synchronized summaries
* session, stage, and sequence correlation is correct
* cancellation rejects stale telemetry
* disconnect and timeout paths fail safely
* no silent simulation fallback occurs
* normal microphone streaming remains functional
* no runaway polling, memory growth, or orphaned processes are observed
* the full unit suite remains green

## Required report

Produce a Validation Report compliant with `"docs/AI Engineering Framework/Report_Standards.md"` and save it in `"docs/Agent Docs/validation/"`.

Include:

* exact commands used
* environment and interpreter
* PC and Pi process evidence
* telemetry protocol and port
* live-mode GUI observations
* session/stage/sequence evidence
* stage metrics table
* cancellation results
* disconnect and timeout results
* stale-message rejection results
* normal audio regression results
* resource and lifecycle observations
* pass/fail matrix
* remaining defects ranked by severity
* recommended next agent
* lifecycle-routing justification
* checkpoint recommendation

If Phase B passes with no blocking defect, recommend the agent appropriate for Phase C planning or implementation according to the approved architecture.
