# Implementation Record

## Metadata

- **Title:** AUDIO-001 / SIM-UI-001 Phase A Calibration Wizard Simulation-Labeling Fix
- **Purpose:** Correct the proven Phase A presentation safety gap where simulated calibration metrics were not clearly labeled as non-production data.
- **Date:** 2026-06-27
- **Author / Agent:** Runtime Implementation Agent (AI assistant using Copilot CLI runtime in VS Code)
- **Source Prompt:** Runtime Implementation Agent task for SIM-UI-001 remediation (2026-06-27).
- **Related Documents:**
  - `docs/AI Engineering Framework/project_state.json`
  - `docs/AI Engineering Framework/Report_Standards.md`
  - `docs/Agent Docs/implementation/audio_001_phase_a_calibration_wizard_implementation_2026-06-27.md`
  - `docs/Agent Docs/validation/audio_001_phase_a_calibration_wizard_validation_2026-06-27.md`
- **Related Implementation:** `pc/gui/calibration_wizard_panel.py`, `pc/services/calibration_session_controller.py`, `pc/services/calibration_metrics_provider.py`
- **Related Validation:** targeted unit tests listed in this record and prior validation handoff in `docs/Agent Docs/validation/audio_001_phase_a_calibration_wizard_validation_2026-06-27.md`
- **Assumptions:**
  - Phase A remains simulation-only and does not introduce production telemetry or persisted calibration writes.
  - Existing full-suite dependency errors (`scipy`, `whisper`) are environment limitations and out of this implementation scope.

## Goal

Implement SIM-UI-001 remediation so simulated mode is persistently and explicitly visible across all Phase A calibration wizard surfaces and lifecycle states, with provider/view-state metadata supporting a clean Phase B provider swap.

## Files Modified

- `pc/services/calibration_metrics_provider.py`
- `pc/services/calibration_session_controller.py`
- `pc/gui/calibration_wizard_panel.py`
- `tests/test_calibration_metrics_provider.py`
- `tests/test_calibration_session_controller.py`
- `tests/test_calibration_wizard_panel.py` (added)
- `docs/Agent Docs/implementation/audio_001_sim_ui_001_phase_a_calibration_wizard_simulation_label_fix_2026-06-27.md` (this record)

## Behavior Before

- Wizard UI did not provide a persistent explicit simulation warning banner.
- Results and diagnostics surfaces displayed deterministic simulated values without clear simulated/non-production labeling.
- Controller view state did not expose provider source/mode metadata for UI-level simulation-safe presentation.

## Behavior After

- Calibration tab now renders a persistent warning banner:
  - `SIMULATION MODE — Results are test data and are not production microphone calibration values.`
- Simulation status remains visible during:
  - preview
  - all measurement stages
  - compare/results
  - advanced diagnostics
- Results lines are explicitly labeled `(SIMULATED)` when simulation mode is active.
- Diagnostics area shows simulated source label (`Diagnostics source: SIMULATED (...)`).
- Instruction/status/completion wording was tightened to avoid production-calibration interpretation while in simulation mode.
- Controller view state now carries provider metadata fields so Phase B can hide/replace simulation warnings based on provider capability.

## Design Decisions

1. **Provider-capability metadata as source of truth**
   - Added `CalibrationProviderMetadata` and `CalibrationMetricsProvider.metadata()`.
   - `SimulatedCalibrationMetricsProvider.metadata()` now explicitly declares:
     - `mode="simulation"`
     - `source_label="deterministic-simulated-provider"`
     - `is_simulated=True`
     - required safety-warning text
   - This avoids hard-coding simulation assumptions across unrelated UI paths and supports Phase B swap behavior.

2. **Controller publishes simulation-aware view state**
   - Extended `CalibrationWizardViewState` with:
     - `provider_mode`
     - `provider_source_label`
     - `simulation_mode`
     - `simulation_warning`
   - Every published state now includes these fields, including terminal paths (`FAILED`, `CANCELLED`, `COMPLETE`).

3. **Persistent UI warning and simulated labeling**
   - Added persistent top-of-wizard warning label bound to `simulation_warning`.
   - Added diagnostics source label showing simulated source.
   - Added explicit simulated labeling in results summary line formatting via `_format_stage_result_line(..., simulated=...)`.

4. **Safety wording hardening**
   - Updated compare/complete/failure/capture status phrasing in controller to prevent simulated outputs being interpreted as production calibration validation.

## Tests Added or Updated

- **Updated:** `tests/test_calibration_metrics_provider.py`
  - validates explicit simulation/source designation in provider metadata
- **Updated:** `tests/test_calibration_session_controller.py`
  - validates simulation metadata reaches view state
  - validates warning presence persists through full workflow
  - validates warning persists in `FAILED` and `CANCELLED`
- **Added:** `tests/test_calibration_wizard_panel.py`
  - validates results formatting marks simulated output with `(SIMULATED)`

## Validation Results

### Required targeted suites

Command:

```text
python3 -m unittest \
  tests.test_calibration_metrics_provider \
  tests.test_calibration_session_controller \
  tests.test_operator_console_streamer_reliability \
  tests.test_pi_streamer_manager
```

Result:

- `Ran 36 tests ... OK`

### Added GUI-panel behavior test

Command:

```text
python3 -m unittest tests.test_calibration_wizard_panel
```

Result:

- `Ran 2 tests ... OK`

### Full discovery (attempted as requested)

Command:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
```

Result:

- `FAILED (errors=2)` due to environment dependency imports:
  - `ModuleNotFoundError: No module named 'scipy'` (`test_e2e_whisper_to_ollama`)
  - `ModuleNotFoundError: No module named 'whisper'` (`test_whisper_service`)
- No implementation-attributable failures were observed in the scoped Phase A calibration changes.

## Remaining Issues

- Environment-limited full-suite execution remains blocked by missing optional dependencies (`scipy`, `whisper`), unchanged from prior baseline.
- Real full GUI launch validation in intended project environment remains for independent validation pass; this implementation record does not claim that launch validation.

## Recommended Next Agent

- **Validation / Test Agent**

## Recommended Revalidation Objective

- Re-run independent Phase A validation focused on SIM-UI-001 closure:
  - confirm persistent simulation warning visibility across preview, all stages, compare/results, diagnostics
  - confirm results/recommendation/completion text is non-production-safe
  - confirm failed/cancelled states retain warning while simulated provider remains active
  - confirm existing calibration and regression suites remain green under validation environment constraints
