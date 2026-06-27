You are the Runtime Implementation Agent.

Goal:

Correct the Phase A Calibration Wizard presentation gap identified as `SIM-UI-001` in the independent validation report.

Read `"docs/AI Engineering Framework/project_state.json"` first.

Follow the applicable standards in `"docs/AI Engineering Framework/"`.

Use these artifacts as the authoritative handoff:

* `"docs/Agent Docs/implementation/audio_001_phase_a_calibration_wizard_implementation_2026-06-27.md"`
* `"docs/Agent Docs/validation/audio_001_phase_a_calibration_wizard_validation_2026-06-27.md"`
* `"docs/audio_001_phase_a_calibration_wizard_revalidation_sim_ui_001_2026-06-27.md"`

## Proven defect

The Phase A wizard uses deterministic simulated metrics, but visible wizard surfaces do not clearly identify those values as simulated, non-production data.

This is a presentation and safety-labeling defect with a proven cause.

## Allowed scope

Modify only the Phase A Calibration Wizard UI and directly related tests, primarily:

* `pc/gui/calibration_wizard_panel.py`
* `pc/services/calibration_session_controller.py`, only if view-state support is required
* `pc/services/calibration_metrics_provider.py`, only if provider metadata is required
* relevant Phase A tests

Do not modify Pi code, audio processing, runtime thresholds, telemetry, persistence, UDP protocols, or unrelated GUI controls.

## Required changes

1. Add a persistent, clearly visible banner or status label in the Calibration tab stating:

   `SIMULATION MODE — Results are test data and are not production microphone calibration values.`

2. Ensure simulated status remains visible during:

   * preview
   * all measurement stages
   * results/compare view
   * advanced diagnostics display

3. Clearly label displayed metrics and results as simulated.

4. Ensure any recommendation, completion, or results text cannot be interpreted as validated production calibration.

5. Structure the implementation so Phase B can replace or hide the simulation warning when a real telemetry-backed provider is active.

6. Prefer provider capability metadata, such as a mode or source label, over hard-coding simulation assumptions throughout unrelated UI logic.

## Tests

Add or update tests to verify:

* simulated provider exposes an explicit simulation/source designation
* the view state communicates simulation mode to the panel
* the warning remains present through the complete workflow
* results are labeled simulated
* failed and cancelled states do not remove the warning while the simulated provider remains active
* existing state-machine and regression tests continue to pass

## Validation

Run:

```text
python3 -m unittest \
  tests.test_calibration_metrics_provider \
  tests.test_calibration_session_controller \
  tests.test_operator_console_streamer_reliability \
  tests.test_pi_streamer_manager
```

Also run any GUI-panel test added for the warning behavior.

Attempt:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

Record dependency failures separately from implementation failures.

Do not claim real GUI launch validation unless the application launches through its normal entry point in the intended project environment.

## Restrictions

* Do not implement Phase B.
* Do not add real Pi telemetry.
* Do not persist calibration settings.
* Do not change calibration values.
* Do not update `"docs/AI Engineering Framework/project_state.json"`.
* Do not fix unrelated dependency or environment problems in this task.

## Output

Produce an Implementation Record compliant with `"docs/AI Engineering Framework/Report_Standards.md"` and save it in `"docs/Agent Docs/implementation/"`.

Include:

* files modified
* simulation-mode presentation design
* provider/view-state changes
* tests added or updated
* commands and results
* remaining environment limitations
* recommended next agent
* recommended revalidation objective
