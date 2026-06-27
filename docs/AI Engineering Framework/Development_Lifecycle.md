# Development Lifecycle

## Purpose

This document defines the standard engineering lifecycle for PiBot development.

It establishes:

* how work progresses from an idea or defect to a validated checkpoint
* which type of agent should perform each phase
* what evidence is required before moving forward
* when implementation, investigation, validation, documentation, and checkpoint activities occur
* how project state persists between agent sessions

Related framework documents:

* `docs/AI Engineering Framework/project_state.json`
* `docs/AI Engineering Framework/Prompt_Standards.md`
* `docs/AI Engineering Framework/Report_Standards.md`
* `docs/AI Engineering Framework/Documentation_Standards.md`

---

## 1. Core Principle

Work must advance based on evidence, not assumptions.

The lifecycle separates:

* deciding what should change
* determining what is actually happening
* determining why a failure occurs
* implementing an approved change
* proving the result
* synchronizing project records
* creating a stable checkpoint

An agent should not combine lifecycle phases unless the task explicitly authorizes it.

---

## 2. Standard Lifecycle

```text
Request or Observation
        |
        v
Classification
        |
        +--------------------+
        |                    |
        v                    v
New Feature              Existing Behavior
        |                    |
        v                    v
Architecture Review      Validation / Diagnostics
        |                    |
        v                    v
Approved Plan          Cause Proven?
        |               |         |
        v              Yes        No
Implementation          |          |
        |                v          v
        |          Implementation   RCA
        |                |          |
        +----------------+----------+
                         |
                         v
                    Validation
                         |
                 +-------+-------+
                 |               |
                Pass            Fail
                 |               |
                 v               v
          Regression Review   Failure Classification
                 |               |
                 v               +--> RCA or Implementation
           Documentation
                 |
                 v
             Checkpoint
                 |
                 v
       Update project_state.json
                 |
                 v
               Commit
```

---

## 3. Phase 0 — Read Current Project State

### Objective

Establish the current project phase and locate the latest authoritative artifacts.

### Required action

Read:

`docs/AI Engineering Framework/project_state.json`

Use it to identify:

* current phase
* latest checkpoint
* latest validation report
* latest implementation record
* latest RCA
* known issues
* recommended next objective
* commit readiness

### Exit criteria

The agent understands:

* what work is currently active
* what evidence already exists
* which artifacts are authoritative
* whether the requested task matches the current project phase

---

## 4. Phase 1 — Classify the Work

Before selecting an agent or writing a task prompt, classify the request.

### New feature

Use when the requested behavior does not currently exist.

Typical next phase:

* Architecture Review
* Implementation Plan
* Implementation

### Known defect with proven cause

Use when evidence already identifies the exact failure mechanism.

Typical next phase:

* Targeted Implementation

### Reproducible defect with unknown cause

Use when the failure can be consistently reproduced but its cause is not proven.

Typical next phase:

* Diagnostics
* Root Cause Analysis

### Intermittent or timing-dependent defect

Use when behavior varies between runs, depends on concurrency, or cannot be reliably reproduced.

Typical next phase:

* Instrumentation
* Root Cause Analysis

### Validation request

Use when implementation is complete and behavior must be proven.

Typical next phase:

* Validation / Regression Validation

### Documentation or repository-state mismatch

Use when implementation is stable but records are stale, incomplete, or inconsistent.

Typical next phase:

* Documentation Synchronization
* Checkpoint

---

## 5. Phase 2 — Architecture Review

### Purpose

Define or approve structural changes before implementation.

### Use when

* adding a new subsystem
* changing protocols or interfaces
* changing ownership boundaries
* changing process or thread architecture
* restructuring major directories or modules
* introducing a new external dependency
* changing deployment topology

### Responsible agent

System Architect

### Required inputs

* `project_state.json`
* current SAICD
* current implementation
* relevant validation or diagnostic reports
* feature requirements or problem statement

### Required output

Architecture Review compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Exit criteria

* proposed behavior is clearly defined
* interfaces and ownership are identified
* affected files or modules are listed
* risks are documented
* implementation scope is approved
* validation requirements are defined

### Prohibited behavior

The architect should not perform broad implementation unless explicitly authorized.

---

## 6. Phase 3 — Diagnostics

### Purpose

Determine what the system is actually doing.

### Use when

* reported behavior has not been independently verified
* implementation and documentation may disagree
* a failure needs reproduction
* logs, process state, traffic, or GUI behavior must be inspected

### Responsible agent

Validation / Diagnostic Agent

### Required activities

As applicable:

* reproduce the issue
* inspect logs
* inspect process and PID state
* inspect network traffic
* inspect GUI behavior
* inspect queues, threads, or timers
* compare intended and observed behavior
* identify the exact failing path

### Required output

Diagnostic Report or Validation Report compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Exit criteria

* observed behavior is documented
* evidence is preserved
* defect severity is assigned
* the next phase is identified

### Decision

If the cause is proven, proceed to Implementation.

If the cause is not proven, proceed to Root Cause Analysis.

---

## 7. Phase 4 — Root Cause Analysis

### Purpose

Determine why a defect occurs.

### Use when

* diagnostics confirm a defect but not its cause
* behavior is intermittent
* timing, concurrency, process lifecycle, or networking is involved
* multiple plausible causes remain
* a prior fix failed or created regressions

### Responsible agent

Root Cause Analysis Agent

### Required approach

* investigate only
* collect targeted evidence
* construct an event timeline when timing matters
* classify the failure mechanism
* reject unsupported hypotheses
* distinguish cause from symptom
* recommend a fix only after the mechanism is proven

Temporary instrumentation may be used when explicitly authorized.

### Required output

Root Cause Analysis compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Exit criteria

* one root cause or a clearly bounded set of causes is supported by evidence
* rejected hypotheses are documented
* affected files and functions are identified
* recommended implementation and validation are defined

### Prohibited behavior

Do not implement the permanent fix during RCA unless explicitly authorized.

---

## 8. Phase 5 — Implementation

### Purpose

Make the smallest safe change required to achieve an approved goal or correct a proven defect.

### Responsible agent

Runtime Implementation Agent or appropriate subsystem implementation agent

### Required inputs

One of:

* approved Architecture Review
* proven RCA
* validated defect with an unambiguous fix
* approved implementation plan

### Required rules

* modify only approved files
* preserve known-good behavior
* avoid unrelated refactoring
* add or update tests
* document important design decisions
* do not claim success without validation
* preserve architecture and interface contracts unless the plan explicitly changes them

### Required output

Implementation Record compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Exit criteria

* required changes are complete
* syntax or static checks pass
* targeted tests pass
* known failures are documented
* implementation is ready for independent validation

---

## 9. Phase 6 — Validation

### Purpose

Prove that the implementation satisfies its requirements in the real operating environment.

### Responsible agent

Validation / Test Agent

### Validation levels

#### Targeted validation

Tests only the changed behavior.

#### Regression validation

Confirms previously working behavior still works.

#### End-to-end validation

Tests the complete user-visible and runtime path.

For PiBot, this may include:

* GUI actions
* PC worker threads
* SSH control
* Pi processes
* PID ownership
* UDP audio/video traffic
* Whisper transcription
* Ollama submission and response
* YOLO inference
* cleanup and shutdown

### Required rules

* validation should normally be read-only
* do not fix failures during the validation run
* capture commands, observations, and evidence
* verify actual system state rather than relying only on GUI labels
* distinguish functional failure from expected degradation

### Required output

Validation Report compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Pass exit criteria

* all required objectives pass
* previous fixes remain valid
* remaining defects are classified
* checkpoint recommendation is provided

### Fail exit criteria

* failure evidence is documented
* severity is assigned
* next phase is identified:

  * Implementation when cause is proven
  * RCA when cause is unknown
  * Architecture Review when the design is inadequate

---

## 10. Phase 7 — Reliability Hardening

### Purpose

Make already working behavior deterministic, recoverable, and resilient.

### Use when

* final state is correct but transient behavior is misleading
* races or stale updates occur
* process cleanup is unreliable
* retries, timeouts, or recovery need refinement
* resource ownership or lifecycle is ambiguous
* hardware or network failures require graceful handling

### Responsible agent

Runtime Reliability Agent

### Required inputs

* successful functional validation
* documented reliability defect
* RCA when the cause is not already proven

### Typical concerns

* thread safety
* stale-result suppression
* generation or action tokens
* process lifecycle
* descriptor ownership
* timeouts
* retries
* socket cleanup
* PID validation
* graceful shutdown
* recovery after partial failure

### Required output

Implementation Record followed by Validation Report.

### Exit criteria

* reliability defect is fixed
* known-good behavior remains intact
* repeated-cycle tests pass
* real process state matches reported state
* no new regression is introduced

---

## 11. Phase 8 — Performance and Quality Tuning

### Purpose

Improve measurable quality after functional stability is established.

### Use when

* the system works but quality is insufficient
* latency, CPU use, memory use, packet loss, audio quality, or transcription quality needs improvement
* tuning requires benchmarks rather than defect repair

### Responsible agent

Performance Analysis Agent or subsystem specialist

### Required approach

1. Define baseline metrics.
2. Use reproducible inputs.
3. Measure current behavior.
4. Change one controlled variable at a time.
5. Compare results.
6. Preserve functional regression coverage.

### PiBot examples

* microphone calibration
* AGC and noise-gate tuning
* transcript fidelity
* phrase segmentation
* video frame-loss tolerance
* jitter and packet-loss metrics
* camera acquisition reliability
* queue and inference latency

### Required output

Performance Report compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

---

## 12. Phase 9 — Documentation Synchronization

### Purpose

Synchronize authoritative documentation and persistent project records with the validated implementation.

### Responsible agent

Documentation Steward and Project Hygiene Agent

### Required inputs

* latest implementation record
* latest validation report
* latest RCA, when applicable
* current source tree
* existing authoritative documentation

### Required activities

* update the SAICD when architecture or interfaces changed
* update the troubleshooting guide when failure modes or recovery changed
* verify directory and file references
* update cross-references
* record known limitations
* review non-obvious code comments
* identify stale or duplicate records
* prepare checkpoint documentation
* update `project_state.json` at checkpoint time

### Standards

Follow:

* `Documentation_Standards.md`
* `Report_Standards.md`

### Exit criteria

* affected authoritative documents match the validated implementation
* engineering records are cross-referenced
* historical artifacts remain clearly marked
* no partially updated documentation set remains
* unresolved documentation issues are listed

---

## 13. Phase 10 — Checkpoint

### Purpose

Capture a stable, evidence-backed project state before beginning the next development phase.

### Responsible agent

Documentation Steward, with validation evidence supplied by the Validation / Test Agent

### Required checkpoint contents

* validated capabilities
* architecture changes
* reliability improvements
* technical debt
* known limitations
* remaining work
* recommended next phase
* evidence references
* commit recommendation

### Required output

Checkpoint Report compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Commit-ready criteria

A checkpoint may be recommended for commit when:

* required validation passes
* no unresolved Critical or High defects remain
* Medium defects are explicitly accepted or deferred
* authoritative documentation is synchronized
* `project_state.json` is current
* the working tree contains no unexplained generated or temporary files
* checkpoint evidence is recorded

---

## 14. Phase 11 — Update Project State

After a checkpoint or material phase transition, update:

`docs/AI Engineering Framework/project_state.json`

### Update when

* a checkpoint is created
* project phase changes
* latest artifact references change
* commit readiness changes
* a known issue is added, closed, or reprioritized
* the recommended next agent changes

### Do not store

* raw logs
* full timelines
* long test output
* duplicated implementation detail
* speculative future designs

Detailed evidence belongs in engineering reports.

---

## 15. Phase 12 — Commit

### Purpose

Create a stable repository boundary after validation and documentation synchronization.

### Before commit

Verify:

* validation recommendation is Commit
* checkpoint report exists
* `project_state.json` is current
* documentation is synchronized
* tests and validation evidence are recorded
* temporary instrumentation is removed
* no unexpected file changes remain
* known limitations are documented

### Commit message

Use a message that describes the validated milestone, not individual editing activity.

Preferred:

```text
Stable runtime checkpoint after streamer and SSH reliability fixes
```

Avoid:

```text
updates
fix stuff
final changes
```

---

## 16. Failure Routing

Use the following routing rules when a phase fails.

| Situation                                   | Next phase                     |
| ------------------------------------------- | ------------------------------ |
| Validation fails and cause is proven        | Implementation                 |
| Validation fails and cause is unknown       | RCA                            |
| Failure is intermittent or timing-dependent | RCA                            |
| Fix works but final state is inconsistent   | Reliability Hardening          |
| Architecture cannot support the requirement | Architecture Review            |
| Behavior works but quality is poor          | Performance and Quality Tuning |
| Documentation disagrees with implementation | Documentation Synchronization  |
| All required validation passes              | Checkpoint                     |

---

## 17. Severity and Lifecycle Impact

### Critical

* safety or data-loss risk
* project cannot operate
* uncontrolled process behavior
* severe security exposure

Action: stop checkpoint and address immediately.

### High

* core requirement fails
* major subsystem unavailable
* no acceptable workaround

Action: do not checkpoint unless explicitly accepted.

### Medium

* degraded behavior
* misleading operator state
* intermittent reliability problem
* workaround exists

Action: fix before checkpoint or document explicit deferral.

### Low

* non-blocking warning
* expected transport degradation
* quality or usability limitation
* future refinement

Action: document and schedule in a later phase.

---

## 18. Lifecycle Records

Each phase should produce or update the appropriate artifact.

| Phase               | Artifact                                  |
| ------------------- | ----------------------------------------- |
| Architecture Review | Architecture Review                       |
| Diagnostics         | Diagnostic or Validation Report           |
| RCA                 | Root Cause Analysis                       |
| Implementation      | Implementation Record                     |
| Validation          | Validation Report                         |
| Reliability         | Implementation Record + Validation Report |
| Performance         | Performance Report                        |
| Documentation       | Updated authoritative documents           |
| Checkpoint          | Checkpoint Report                         |
| Phase transition    | `project_state.json`                      |

All report artifacts must comply with:

`docs/AI Engineering Framework/Report_Standards.md`

---

## 19. Lifecycle Discipline

The following practices are prohibited unless explicitly authorized:

* implementing before the cause or design is sufficiently understood
* combining RCA and permanent implementation in one task
* editing code during independent validation
* claiming a fix works without executed validation
* broad refactoring during a narrow defect correction
* updating project state based on unvalidated work
* treating planned behavior as implemented behavior
* using historical reports as current project truth
* creating checkpoints without evidence

---

## 20. Completion Definition

A unit of work is complete when:

* the objective has been implemented or conclusively investigated
* required tests or validation have been executed
* results are recorded in the correct engineering artifact
* affected authoritative documentation is synchronized
* remaining issues are classified
* the next lifecycle phase is identified
* `project_state.json` is updated when required
* the repository is either ready for commit or explicitly marked not ready
