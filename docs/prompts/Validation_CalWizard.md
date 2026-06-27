You are the Validation / Test Agent.

Goal:

Independently validate the AUDIO-001 Phase A Calibration Wizard implementation in the live PC Tkinter application.

Read `"docs/AI Engineering Framework/project_state.json"` first.

Follow the applicable requirements in:

* `"docs/AI Engineering Framework/Development_Lifecycle.md"`
* `"docs/AI Engineering Framework/Agent_Orchestration_Guide.md"`
* `"docs/AI Engineering Framework/Prompt_Standards.md"`
* `"docs/AI Engineering Framework/Report_Standards.md"`

Use this implementation record as the primary handoff artifact:

`"docs/Agent Docs/implementation/audio_001_phase_a_calibration_wizard_implementation_2026-06-27.md"`

## Validation boundary

This task validates Phase A only:

* PC-side Tkinter Calibration tab
* operator workflow and cues
* calibration state machine
* countdown and capture transitions
* repeat, next, cancel, close, and optional phrase-stage behavior
* simulated metrics-provider integration
* regression safety for existing GUI controls

Phase A does not include:

* real Pi calibration telemetry
* a Pi calibration control channel
* temporary parameter application
* production calibration persistence
* real microphone scoring
* validated calibration recommendations

Do not report simulated measurements as real microphone or Pi evidence.

## Restrictions

* Do not edit production code.
* Do not edit tests.
* Do not repair defects during validation.
* Do not update `"docs/AI Engineering Framework/project_state.json"`.
* If a defect is found, record the reproduction procedure, evidence, severity, and recommended next agent.

## Required validation

### 1. Application integration

Verify that:

* the existing PiBot application launches
* the `Calibration` tab is present
* opening or using the tab does not prevent access to existing controls
* no startup exception is introduced

### 2. Operator workflow

Exercise the complete wizard workflow:

1. Start wizard
2. Verification stage
3. Preview stage
4. Silence stage
5. Normal-speech stage
6. Loud-speech stage
7. Optional phrase stage
8. Compare/results stage
9. Complete or close

Verify that every measurement stage provides:

* clear stage name
* clear written instructions
* visible prepare cue
* visible start cue
* visible stop cue
* visible countdown
* progress indication
* capture-success indication
* correct button enablement

### 3. State-machine behavior

Verify:

* transitions occur in the expected order
* `Next` is unavailable before successful capture
* invalid user actions do not force invalid transitions
* optional phrase-stage skip routes correctly
* completion reaches the expected terminal state

### 4. Repeat behavior

For silence, normal, and loud stages:

* complete the stage
* invoke Repeat
* confirm only the current stage restarts
* confirm prior completed-stage results are handled as designed
* confirm callbacks from the superseded attempt do not alter the new attempt

### 5. Cancellation and stale-callback suppression

Cancel during:

* prepare countdown
* active capture
* transition between stages

Verify that:

* pending callbacks no longer change state
* the wizard reaches `CANCELLED`
* no later countdown or capture completion overwrites the cancelled state
* the application remains responsive
* the wizard can be started again safely

### 6. Rapid-cycle reliability

Run at least 10 cycles that include a mixture of:

* start then cancel during countdown
* start then cancel during capture
* repeat current stage
* close and reopen the wizard
* complete the abbreviated workflow with phrase stage disabled

For every cycle, record:

* starting state
* actions performed
* final state
* unexpected callback or transition
* GUI responsiveness

The rapid-cycle validation passes only if all cycles finish in the expected state without stale updates, exceptions, or UI hangs.

### 7. Simulated metrics-provider behavior

Verify that:

* simulated results appear in the UI
* required metric fields render correctly
* results are deterministic for equivalent inputs as defined by the provider contract
* failed capture results prevent inappropriate progression
* the UI clearly avoids presenting simulated metrics as production calibration results

### 8. Regression validation

Verify that adding the Calibration tab does not regress applicable existing behavior, including:

* application launch
* existing notebook tabs
* streamer-control widgets
* audio/video controls
* GUI responsiveness

Run the targeted regression tests identified in the implementation record.

### 9. Test execution

Run at minimum:

```text
python3 -m unittest \
  tests.test_calibration_metrics_provider \
  tests.test_calibration_session_controller \
  tests.test_operator_console_streamer_reliability \
  tests.test_pi_streamer_manager
```

Also attempt the full test discovery command:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

Distinguish:

* Phase A failures
* new regressions
* pre-existing environment or dependency failures

Do not automatically classify a failure as pre-existing without comparing it to the implementation record and available baseline evidence.

## Required evidence

Capture:

* exact commands executed
* test counts and results
* GUI launch result
* observed state transitions
* operator-cue observations
* repeat and cancellation results
* rapid-cycle results
* exception or traceback evidence
* regression observations

Screenshots may be used where they clarify GUI state, but written observations and executed test evidence are still required.

## Required report

Produce a Validation Report compliant with `"docs/AI Engineering Framework/Report_Standards.md"` and save it in `"docs/Agent Docs/validation/"`.

The report must include:

* scope and Phase A boundary
* exact commands used
* pass/fail matrix
* GUI observations
* state-transition evidence
* repeat and cancellation evidence
* rapid-cycle reliability table
* regression results
* dependency-related limitations
* remaining defects ranked by severity
* recommended next agent
* lifecycle routing justification
* checkpoint recommendation:

  * `Commit`
  * `Continue Implementation`
  * `Continue Investigation`
  * `Architecture Review Required`

Recommend Phase B implementation only if Phase A passes and no blocking defect remains.
