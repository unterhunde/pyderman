You are the Pi Audio Diagnostic Agent.

Goal:

Investigate and establish a reproducible baseline for backlog item `AUDIO-001`: Microphone and AGC calibration.

Read `"docs/AI Engineering Framework/project_state.json"` first.

Then follow the applicable requirements in:

* `"docs/AI Engineering Framework/Development_Lifecycle.md"`
* `"docs/AI Engineering Framework/Agent_Orchestration_Guide.md"`
* `"docs/AI Engineering Framework/Prompt_Standards.md"`
* `"docs/AI Engineering Framework/Report_Standards.md"`
* `"docs/AI Engineering Framework/Documentation_Standards.md"`

## Current objective

Determine the current microphone signal quality and identify the calibration values required for speech spoken approximately two feet from the Pi microphone.

This task is diagnostic and measurement-focused. Do not begin broad implementation or hardware redesign.

## Scope

Inspect and test the active Pi audio path, including relevant:

* microphone device selection
* sample rate and channel configuration
* input amplitude
* RMS levels
* clipping
* background noise
* noise gate behavior
* AGC behavior
* silence detection
* speech segmentation inputs
* UDP audio delivery to the PC

Use the current repository structure and active implementation as the source of truth.

## Required tasks

1. Review the current audio configuration and relevant implementation files.
2. Confirm the active microphone device and runtime settings on the Raspberry Pi.
3. Establish a repeatable test procedure for:

   * room silence
   * normal speech from approximately two feet away
   * louder speech
4. Capture measurable results, including:

   * baseline noise level
   * normal-speech RMS range
   * peak levels
   * clipping or distortion evidence
   * AGC gain behavior
   * noise-gate activation behavior
   * packet delivery or audio continuity issues
5. Determine whether the current problem is:

   * configuration
   * calibration
   * hardware handling
   * transport
   * speech segmentation
   * or a combination
6. Recommend specific calibration changes supported by the collected evidence.
7. Do not permanently change production behavior unless a small temporary diagnostic adjustment is necessary to collect evidence.
8. Clearly identify any temporary changes and restore them before completion unless explicitly approved otherwise.

## Validation

Confirm that:

* silence and speech are distinguishable by measured signal levels
* normal speech from approximately two feet away is captured without sustained clipping
* the UDP audio stream remains active during testing
* recommended threshold and AGC values are derived from measurements rather than assumptions

## Output

Produce a Diagnostic Report compliant with `"docs/AI Engineering Framework/Report_Standards.md"` and save it in `"docs/Agent Docs/diagnostics/"`.

The report must include:

* measured baseline values
* test procedure
* observed failure or quality characteristics
* recommended calibration values
* whether implementation changes are required
* the recommended next agent
* the recommended next objective

Do not update `"docs/AI Engineering Framework/project_state.json"` during this diagnostic task. Recommend any required project-state changes in the report for the Documentation Steward to apply after validation.
