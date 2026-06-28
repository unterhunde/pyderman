You are the Validation / Test Agent.

## Goal

Complete the previously blocked live revalidation of AUDIO-001 Phase B after successful resolution of `DEPLOY-001`.

Validate the real PC-to-Raspberry Pi calibration telemetry path, live Calibration Wizard behavior, synchronized stage capture, failure handling, and normal audio regression.

Read `"docs/AI Engineering Framework/project_state.json"` first.

Follow the applicable standards in `"docs/AI Engineering Framework/"`.

Use these artifacts as the authoritative handoff:

* `"docs/Agent Docs/implementation/audio_001_phase_b_calibration_wizard_implementation_2026-06-27.md"`
* `"docs/Agent Docs/validation/audio_001_phase_b_calibration_wizard_validation_2026-06-27.md"`
* `"docs/Agent Docs/implementation/deploy_001_audio_001_phase_b_pi_deployment_2026-06-27.md"`

## Validation boundary

Validate only the real-Pi cases that were previously blocked:

* Pi telemetry server through the deployed production runtime
* PC live telemetry client connection
* Calibration Wizard live mode
* real preview metrics
* synchronized silence, normal-speech, loud-speech, and optional phrase captures
* cancellation during live activity
* disconnect and timeout handling
* stale-session rejection
* normal UDP microphone streaming before and after calibration
* resource and process cleanup

Do not repeat localhost-only protocol testing unless a live failure requires comparison.

Do not implement or validate Phase C features.

## Restrictions

* Do not edit production code.
* Do not edit tests.
* Do not deploy files.
* Do not update `"docs/AI Engineering Framework/project_state.json"`.
* Do not run unbounded scripts or polling loops.
* Do not repeatedly run the full unit suite.
* Add explicit timeouts to blocking commands.
* Stop and document any abnormal memory growth, reconnect loop, UI hang, or orphaned process.

## Environment checks

Confirm:

* PC interpreter: `./.venv/bin/python`
* Pi host: `192.168.0.38`
* Pi project root: `/home/jorg/pibot`
* Pi production interpreter: `/home/jorg/venv/bin/python3`
* telemetry port: `5011`
* no stale mic streamer or telemetry process is running
* no stale process is bound to port `5011`

## Required validation

### 1. Start the deployed Pi streamer

Start the microphone streamer through the intended production control path.

Verify:

* the streamer process remains running
* the PID file is correct
* port `5011` is listening
* UDP audio packets reach the PC
* no startup exception occurs

Record:

* PID
* listening socket
* packet evidence
* relevant logs

### 2. Real live telemetry connection

Launch the PC application using:

```bash
./.venv/bin/python pc/client.py
```

Open the Calibration tab and select live telemetry mode.

Verify:

* the UI displays `LIVE TELEMETRY MODE`
* the simulation warning is absent
* connection state becomes connected
* the PC connects to Pi port `5011`
* session-open acknowledgement succeeds
* the same session ID is visible or observable on both sides
* no fallback to simulation occurs

### 3. Live preview

During preview, verify that real microphone values update for:

* raw RMS
* processed RMS
* peak
* gate state or gate ratio
* AGC gain
* telemetry connection state

Perform:

* several seconds of silence
* normal speech at approximately two feet
* louder speech

Confirm:

* values change in response to real input
* the GUI remains responsive
* updates stop after leaving preview
* no stale preview callback continues running

### 4. Real synchronized stage captures

Complete:

1. Silence stage
2. Normal-speech stage
3. Loud-speech stage
4. Optional phrase stage, when enabled

For every stage, record:

* session ID
* stage ID
* stage type
* timestamps
* sequence start and end
* chunks captured
* chunks dropped or missing
* raw RMS summary
* processed RMS summary
* peak
* clipping
* gate-active ratio
* AGC gain statistics
* capture result

Verify:

* stage completion depends on a valid Pi stage summary
* session and stage IDs match
* sequence ranges are present and ordered
* the metrics are real, not simulated
* silence and speech produce meaningfully different measurements
* `Next` remains disabled if the summary is missing or invalid

### 5. Cancellation safety

Cancel during:

* live preview
* prepare countdown
* active capture
* waiting for a stage summary

Verify:

* the active session is cancelled
* Pi-side stage state is cleared
* delayed telemetry is rejected
* the GUI remains responsive
* polling stops
* a new live session starts successfully afterward

### 6. Disconnect and timeout handling

During an active stage:

1. Stop the Pi streamer or otherwise interrupt telemetry.
2. Observe the PC behavior.
3. Restart the Pi streamer.
4. Begin a new calibration session.

Verify:

* the stage fails clearly
* `Next` remains disabled
* the UI does not silently switch to simulation
* retry behavior is bounded
* the old session ID is rejected
* the new session receives a new ID
* no reconnect loop or UI hang occurs

### 7. Normal audio regression

Before calibration:

* start the normal mic streamer
* confirm UDP packets reach the PC
* start and stop listening

After one completed live calibration session:

* repeat the same checks

After one cancelled live calibration session:

* repeat the same checks

Verify:

* calibration does not prevent normal streaming
* stop behavior still terminates the Pi process
* port `5011` closes after streamer shutdown
* no stale PID file remains

### 8. Resource and lifecycle checks

After each test group, inspect:

* PC and Pi Python processes
* port `5011`
* telemetry threads
* stale sockets
* queue or history growth
* memory use

Confirm:

* no orphaned processes
* no runaway polling
* no repeated reconnect threads
* no persistent port binding after shutdown
* no abnormal memory growth

## Test-suite confirmation

Run the full unit suite once only:

```bash
timeout 120s ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Record the result. Do not rerun it unless validation changes the working tree, which is not permitted in this task.

## Pass criteria

Phase B passes only if:

* real PC-to-Pi telemetry connects
* live preview displays real microphone data
* all required stage captures produce valid synchronized summaries
* cancellation and disconnect paths fail safely
* stale telemetry cannot alter a new session
* normal UDP audio remains functional
* no silent simulation fallback occurs
* no runaway polling, memory growth, or orphaned process remains
* the unit suite remains green

## Required report

Produce a Validation Report compliant with `"docs/AI Engineering Framework/Report_Standards.md"` and save it in `"docs/Agent Docs/validation/"`.

Include:

* exact commands
* PC and Pi environment
* process and port evidence
* live connection evidence
* stage metrics table
* cancellation results
* disconnect and timeout results
* normal audio regression results
* resource and cleanup evidence
* pass/fail matrix
* remaining defects ranked by severity
* recommended next agent
* lifecycle-routing justification
* checkpoint recommendation

If all live Phase B criteria pass, recommend the next lifecycle step defined by the approved architecture.
