You are the System Architect.

Goal:

Design an interactive microphone calibration interface for PiBot that allows the operator to perform repeatable silence, normal-speech, and loud-speech measurements without relying on conversational timing instructions from an AI agent.

Read `"docs/AI Engineering Framework/project_state.json"` first.

Follow the applicable requirements in:

* `"docs/AI Engineering Framework/Development_Lifecycle.md"`
* `"docs/AI Engineering Framework/Agent_Orchestration_Guide.md"`
* `"docs/AI Engineering Framework/Prompt_Standards.md"`
* `"docs/AI Engineering Framework/Report_Standards.md"`
* `"docs/AI Engineering Framework/Documentation_Standards.md"`

Use these reports as primary evidence:

* `"docs/Agent Docs/diagnostics/audio_001_mic_agc_calibration_diagnostic_2026-06-27.md"`
* `"docs/Agent Docs/diagnostics/audio_001_live_room_followup_validation_2026-06-27.md"`

## Problem

The current agent-guided calibration workflow is unreliable because the operator cannot consistently determine when each measurement stage begins and ends.

The latest live-room validation also found:

* excessive gating during speech
* poor transcript fidelity
* uncertain interaction between microphone SNR, gate settings, AGC settings, and PC segmentation
* no proven final production calibration
* no evidence yet that the microphone hardware itself is defective

## Required outcome

Design a calibration wizard integrated with the existing PC Tkinter application.

The wizard must guide the operator through a repeatable sequence and collect synchronized measurements from the real Pi audio pipeline.

## Required operator workflow

The design should include at minimum:

1. Device and connection verification
2. Microphone input preview
3. Silence measurement
4. Normal speech measurement at approximately two feet
5. Loud speech measurement
6. Optional phrase transcription test
7. Results comparison
8. Recommended settings
9. Apply, retest, revert, and save controls

Each stage must provide:

* a clear visual state
* written instructions
* a visible countdown
* explicit start and stop cues
* a progress indicator
* an option to repeat the stage
* confirmation that data was captured successfully

## Required live displays

Evaluate the inclusion of:

* current raw RMS
* processed RMS
* peak level
* clipping indicator
* noise-gate state
* current AGC gain
* speech-detection state
* UDP packet continuity
* waveform or recent-level history
* current transcription output

Do not require every metric to be shown simultaneously if that would make the interface confusing. Separate operator-facing information from advanced diagnostic details where appropriate.

## Calibration behavior

The architecture must define how the wizard will:

* capture labeled silence, normal-speech, and loud-speech windows
* reset AGC or diagnostic state between stages
* ensure raw and processed metrics refer to the same audio chunks
* distinguish temporary test values from production configuration
* run controlled parameter trials
* compare results with the current baseline
* prevent accidental persistence of poor settings
* restore the previous configuration after cancellation or failed validation

## Configuration candidates

The wizard should be capable of evaluating or recommending values for:

* `NOISE_GATE_RMS`
* `TARGET_RMS`
* `MAX_GAIN`
* `AGC_ATTACK`
* `AGC_RELEASE`
* PC speech or volume threshold
* silence timeout, when relevant

The architecture must distinguish between:

* measured values
* experimental candidates
* validated production values

## Hardware assessment

Include a hardware-quality assessment step based on measurable evidence.

The wizard should help determine whether poor results are caused by:

* low microphone signal
* excessive environmental noise
* incorrect microphone orientation
* dead or inactive channel
* invalid channel configuration
* unstable stream initialization
* gate or AGC configuration
* PC-side segmentation
* transcript-model behavior

Do not classify the microphone as defective unless controlled measurements demonstrate that configuration and environment cannot produce acceptable signal quality.

## Architecture questions to answer

1. Should calibration logic run primarily on the PC, Pi, or be divided between them?
2. What runtime metrics must the Pi expose?
3. Should the existing UDP audio protocol be extended, or should diagnostic metrics use a separate control channel?
4. How will temporary calibration values be applied safely?
5. How will previous settings be restored?
6. Where should validated calibration values be persisted?
7. How will the wizard avoid conflicts with the active microphone streamer and Whisper listener?
8. Which existing modules should be reused?
9. Which new modules, classes, or interfaces are required?
10. What tests and live validation are required before production use?

## Scope constraints

* Do not implement the feature in this task.
* Do not modify production code.
* Do not permanently change current audio settings.
* Preserve the existing PC/Pi separation.
* Reuse existing audio receiver, streamer, configuration, and GUI services where practical.
* Avoid creating a second competing audio pipeline.

## Required output

Produce an Architecture Review compliant with `"docs/AI Engineering Framework/Report_Standards.md"`.

The review must include:

* proposed user workflow
* proposed GUI layout
* state machine
* PC and Pi responsibilities
* data and control flows
* affected existing modules
* proposed new modules
* temporary-setting and rollback design
* configuration persistence design
* failure handling
* hardware-assessment criteria
* implementation phases
* validation requirements
* recommended next agent
* recommended next objective

Save the Architecture Review in `"docs/Agent Docs/architecture/"`.

If that directory does not exist, create it without moving or renaming existing engineering records.

Do not update `"docs/AI Engineering Framework/project_state.json"` during this architecture task.
