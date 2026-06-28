You are the Documentation Steward and Project Hygiene Agent.

## Goal

Prepare PiBot for an AUDIO-001 Phase B checkpoint commit by updating authoritative documentation, project state, artifact references, and checkpoint records after successful live validation.

This is a documentation and project-hygiene task.

Do not add features, fix defects, refactor runtime logic, alter runtime behavior, or begin Phase C.

## Required first steps

Read `"docs/AI Engineering Framework/project_state.json"` first.

Follow the applicable standards in:

* `"docs/AI Engineering Framework/Documentation_Standards.md"`
* `"docs/AI Engineering Framework/Report_Standards.md"`
* `"docs/AI Engineering Framework/Development_Lifecycle.md"`
* `"docs/AI Engineering Framework/Agent_Orchestration_Guide.md"`

Use the current implementation and runtime evidence as authoritative.

## Authoritative handoff artifacts

Use these records as the primary evidence for the checkpoint:

* `"docs/Agent Docs/implementation/audio_001_phase_b_calibration_wizard_implementation_2026-06-27.md"`
* `"docs/Agent Docs/validation/audio_001_phase_b_calibration_wizard_validation_2026-06-27.md"`
* `"docs/Agent Docs/implementation/deploy_001_audio_001_phase_b_pi_deployment_2026-06-27.md"`
* `"docs/Agent Docs/validation/audio_001_phase_b_calibration_wizard_live_revalidation_2026-06-27.md"`

The live revalidation report is the final validation authority for Phase B.

## Scope

### 1. Project-state update

Update `"docs/AI Engineering Framework/project_state.json"` to reflect the validated current state.

Required changes:

* Record AUDIO-001 Phase A as complete and validated.

* Record AUDIO-001 Phase B as complete, deployed, and independently validated.

* Keep `AUDIO-001` open because later calibration phases remain.

* Do not describe the entire microphone and AGC calibration feature as complete.

* Record Phase C as the next calibration phase according to the approved architecture.

* Set the latest implementation artifact to the Phase B deployment or implementation record, according to the existing project-state schema.

* Set the latest validation artifact to:

  `"docs/Agent Docs/validation/audio_001_phase_b_calibration_wizard_live_revalidation_2026-06-27.md"`

* Set the next agent and objective according to the development lifecycle.

* Update checkpoint and commit-readiness fields according to the existing schema.

* Do not invent new top-level schema fields unless required by the existing documentation standards.

Use progress wording equivalent to:

`Calibration Wizard Phases A and B are complete, deployed, and independently validated. Phase C controlled calibration trials and temporary parameter application remain pending.`

### 2. Backlog update

Add the low-severity PID-file defect from the live validation report as a separate backlog item:

* ID: `RUNTIME-001`
* Severity: `low`
* Status: `open`
* Title: `Mic streamer PID file can be lost after a concurrent start attempt`
* Recommended owner: `Runtime Reliability Agent`

Do not fix this defect in this task.

Do not merge it into AUDIO-001.

Do not close AUDIO-001.

### 3. Architecture documentation

Inspect the current System Architecture and Interface Control Document and update it only where Phase B introduced verified architectural facts, including as applicable:

* the separate TCP calibration telemetry/control channel
* telemetry port `5011`
* Pi-side `CalibrationTelemetryServer`
* PC-side telemetry client and live metrics provider
* session and stage correlation
* sequence-aligned stage summaries
* simulation and live telemetry provider modes
* cancellation, stale-session, disconnect, and cleanup behavior
* preservation of the existing UDP audio packet format

Do not rewrite unrelated architecture sections.

Do not document Phase C behavior as implemented.

### 4. Diagnostic documentation

Inspect the current System Diagnostic & Troubleshooting Guide and add only verified Phase B diagnostic procedures, including as applicable:

* checking whether port `5011` is listening on the Pi
* verifying the calibration telemetry server starts with the microphone streamer
* verifying the PC can connect to the Pi telemetry channel
* distinguishing simulation mode from live telemetry mode
* diagnosing session, stage, timeout, disconnect, and stale-session failures
* checking for stale streamer processes and PID files
* verifying UDP audio still reaches PC port `5001`

Do not add speculative troubleshooting steps.

### 5. Code comments

Inspect only the files that already implement these non-obvious reliability mechanisms:

* SSH spawner and descriptor detachment
* PID command-line ownership guard
* confirmed-state GUI status ownership
* Ollama thread-safe URL cache

Add or revise comments only when the reliability decision is not already adequately explained.

Comments must:

* explain why the mechanism exists
* describe the invariant being protected
* remain concise
* not restate obvious code
* not change executable behavior

Do not modify code outside comment-only changes.

If the existing comments are sufficient, make no change and record that conclusion.

### 6. Directory and artifact hygiene

Review `"docs/Agent Docs/"` for:

* misplaced validation records
* misplaced implementation records
* misplaced checkpoint records
* prompts stored outside the intended prompts location
* duplicate generated reports
* temporary files
* stale artifacts that appear superseded

Recommend cleanup separately.

Do not move, delete, rename, or archive files unless the action is clearly safe, reversible, and permitted by the documentation standards.

Completed engineering records are immutable. Do not rewrite historical implementation or validation reports.

### 7. Checkpoint summary

Create a checkpoint summary compliant with `"docs/AI Engineering Framework/Report_Standards.md"` and save it in `"docs/Agent Docs/checkpoints/"`.

The checkpoint summary must include:

* checkpoint scope
* implementation artifacts used
* validation artifact used as final evidence
* Phase A status
* Phase B implementation status
* Pi deployment status
* live validation status
* unit-test result: `117/117 passing`
* live integration result: `63/63 passing`
* UDP audio regression result
* resource and lifecycle result
* known remaining low-severity issues
* `RUNTIME-001`
* remaining AUDIO-001 work
* recommended next agent
* recommended next objective
* files that should not be modified before commit
* commit-readiness assessment
* exact proposed commit boundary

Do not state that AUDIO-001 as a whole is complete.

## Commit boundary

The proposed Phase B checkpoint should include only:

* Phase B production modules
* Phase B test modules
* Pi deployment integration changes
* relevant authoritative documentation updates
* project-state updates
* the Phase B implementation, deployment, validation, and checkpoint records
* comment-only reliability clarification made during this task

Do not include Phase C work or unrelated cleanup.

## Validation

Validate all changed JSON and documentation references.

At minimum:

* parse `"docs/AI Engineering Framework/project_state.json"`
* verify every newly referenced artifact path exists
* verify AUDIO-001 remains open
* verify RUNTIME-001 is present once
* verify the latest validation artifact points to the live revalidation report
* verify the checkpoint summary exists in `"docs/Agent Docs/checkpoints/"`
* inspect the working-tree diff and confirm there are no runtime behavior changes

Do not run the full runtime or integration test suite unless a documentation change unexpectedly affects executable files.

## Restrictions

* Do not implement Phase C.
* Do not fix RUNTIME-001.
* Do not close AUDIO-001.
* Do not modify runtime behavior.
* Do not change calibration values.
* Do not move historical reports without explicit authorization.
* Do not create a git commit.
* Do not push or merge changes.
* Do not update completed implementation or validation reports.

## Required output

Produce a Documentation and Checkpoint Report compliant with `"docs/AI Engineering Framework/Report_Standards.md"` and save it in `"docs/Agent Docs/checkpoints/"`.

Include:

* files inspected
* files changed
* project-state changes
* backlog changes
* architecture updates
* diagnostic-guide updates
* code comments added or intentionally left unchanged
* directory-hygiene findings
* cleanup recommendations
* validation commands and results
* proposed commit contents
* excluded files or work
* commit-readiness recommendation
* recommended next agent and objective

At completion, present the operator with the commit-readiness result and request explicit confirmation before any commit is created.
