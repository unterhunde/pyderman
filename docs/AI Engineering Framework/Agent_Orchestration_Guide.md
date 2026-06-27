# PiBot Agent Orchestration Guide

## Purpose

This document defines how AI agents are selected, sequenced, scoped, and handed off during PiBot development.

It establishes:

* which agent should handle each type of work
* what evidence each agent must receive
* what each agent is allowed to change
* what artifact each agent must produce
* how the next agent is selected
* who owns project-state and checkpoint updates

Related framework documents:

* `docs/AI Engineering Framework/project_state.json`
* `docs/AI Engineering Framework/Development_Lifecycle.md`
* `docs/AI Engineering Framework/Prompt_Standards.md`
* `docs/AI Engineering Framework/Report_Standards.md`
* `docs/AI Engineering Framework/Documentation_Standards.md`

---

## 1. Core Orchestration Rule

Select agents according to the question that must be answered.

| Question                                                      | Agent                                                      |
| ------------------------------------------------------------- | ---------------------------------------------------------- |
| What should the system or change look like?                   | System Architect                                           |
| What is the system actually doing?                            | Validation / Diagnostic Agent                              |
| Why is the observed failure occurring?                        | Root Cause Analysis Agent                                  |
| How should a proven change be implemented?                    | Runtime Implementation Agent                               |
| How can working behavior be made deterministic and resilient? | Runtime Reliability Agent                                  |
| Where is the performance or quality bottleneck?               | Performance Analysis Agent                                 |
| Does the documentation accurately reflect the system?         | Documentation Steward                                      |
| Is the current build ready for a checkpoint?                  | Validation / Test Agent, followed by Documentation Steward |

Agents are selected by the type of uncertainty being resolved, not merely by the subsystem involved.

---

## 2. Starting Rule for Every Agent

Before beginning work, every agent must read:

`docs/AI Engineering Framework/project_state.json`

The agent should use it to identify:

* current project phase
* latest checkpoint
* latest validation
* latest implementation record
* latest Root Cause Analysis
* current known issues
* recommended next objective
* commit readiness

The task prompt should then provide only the additional references required for that specific task.

---

## 3. Agent Roles

## 3.1 System Architect

### Primary question

What should the system, subsystem, interface, or proposed change look like?

### Use when

* adding a new feature or subsystem
* changing protocols or interfaces
* changing process or thread ownership
* restructuring major modules
* changing deployment topology
* resolving architectural inconsistency
* defining implementation boundaries

### Required inputs

* `project_state.json`
* current SAICD
* current implementation
* relevant requirements
* latest validation or RCA when applicable

### Allowed work

* inspect the repository
* define architecture and interfaces
* define affected modules
* establish implementation boundaries
* identify risks
* define validation requirements
* update architectural documentation when explicitly authorized

### Must not

* perform broad implementation by default
* claim runtime behavior without validation
* redefine stable interfaces without documenting impact

### Required output

Architecture Review compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Typical next agent

Runtime Implementation Agent

---

## 3.2 Validation / Diagnostic Agent

### Primary question

What is the system actually doing?

### Use when

* verifying reported behavior
* validating an implementation
* collecting runtime evidence
* comparing GUI state with actual process state
* inspecting network, thread, queue, or process behavior
* determining whether a defect exists

### Required inputs

* `project_state.json`
* implementation or feature under test
* relevant acceptance criteria
* prior validation when performing regression

### Allowed work

* execute tests
* launch the application
* use SSH
* inspect logs
* inspect process and PID state
* inspect UDP, HTTP, and other runtime interfaces
* collect GUI observations
* create validation artifacts

### Must not

* edit production code during independent validation
* repair failures while collecting validation evidence
* report GUI state as truth without checking actual runtime state when verification is possible

### Required output

Validation Report or Diagnostic Report compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Typical next agent

* Runtime Implementation Agent when the cause is already proven
* Root Cause Analysis Agent when the cause is unknown
* Documentation Steward when validation passes
* System Architect when the design cannot meet the requirement

---

## 3.3 Root Cause Analysis Agent

### Primary question

Why is the observed failure occurring?

### Use when

* a defect is confirmed but the cause is unknown
* behavior is intermittent
* timing or concurrency is involved
* multiple plausible causes remain
* a previous implementation attempt failed
* symptoms and root cause may differ

### Required inputs

* `project_state.json`
* validation or diagnostic report
* relevant source files
* logs and runtime evidence

### Allowed work

* inspect implementation
* reproduce the issue
* add temporary instrumentation when authorized
* build event timelines
* classify failure modes
* reject unsupported hypotheses
* identify affected files and functions
* recommend a targeted fix

### Must not

* implement the permanent fix
* refactor unrelated code
* present a hypothesis as proven
* broaden scope beyond the reported failure

### Required output

Root Cause Analysis compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Typical next agent

Runtime Implementation Agent or Runtime Reliability Agent

---

## 3.4 Runtime Implementation Agent

### Primary question

How should the approved or proven change be implemented safely?

### Use when

* an RCA proves the defect
* an architecture plan is approved
* a defect has an unambiguous implementation path
* a narrowly scoped feature is ready to build

### Required inputs

* `project_state.json`
* approved Architecture Review, RCA, or implementation plan
* explicit allowed-file scope
* known-good behavior to preserve
* validation requirements

### Allowed work

* modify approved production files
* add or update tests
* update directly affected implementation documentation
* record design decisions

### Must not

* broaden the scope
* redesign unrelated systems
* add unrequested features
* modify stable behavior without explicit justification
* claim end-to-end success without independent validation

### Required output

Implementation Record compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Typical next agent

Validation / Test Agent

---

## 3.5 Runtime Reliability Agent

### Primary question

How can already working behavior be made deterministic, recoverable, and resilient?

### Use when

* races or stale updates occur
* process cleanup is unreliable
* status reporting is inconsistent
* timeouts or retries need refinement
* sockets, descriptors, or PIDs are mishandled
* resource ownership is unclear
* graceful shutdown or recovery is incomplete

### Required inputs

* `project_state.json`
* successful functional validation
* reliability defect evidence
* RCA when the cause is not already proven

### Allowed work

* modify lifecycle and synchronization logic
* add stale-result suppression
* improve process ownership
* improve timeout classification
* improve cleanup and recovery
* add repeated-cycle reliability tests

### Must not

* redesign functional behavior
* add unrelated features
* mask failures without reconciling actual system state
* use arbitrary sleeps in place of proven synchronization

### Required output

Implementation Record compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Typical next agent

Validation / Test Agent

---

## 3.6 Performance Analysis Agent

### Primary question

Where is the measurable performance or quality bottleneck?

### Use when

* functionality works but quality is inadequate
* latency is high
* packet loss needs analysis
* CPU or memory use is excessive
* audio or video quality needs tuning
* transcription accuracy needs benchmarking
* queue pressure or backpressure must be measured

### Required inputs

* `project_state.json`
* stable functional baseline
* reproducible test inputs
* target metrics
* relevant configuration and hardware details

### Allowed work

* define benchmarks
* collect metrics
* compare configurations
* identify bottlenecks
* recommend controlled changes
* implement tuning only when explicitly authorized

### Must not

* change multiple uncontrolled variables at once
* optimize without a measured baseline
* describe subjective improvement as proven without metrics

### Required output

Performance Report compliant with:

`docs/AI Engineering Framework/Report_Standards.md`

### Typical next agent

* Runtime Implementation Agent for approved changes
* Runtime Reliability Agent for resilience problems
* Validation / Test Agent after tuning

---

## 3.7 Documentation Steward and Project Hygiene Agent

### Primary question

Does the documentation and project state accurately reflect the validated implementation?

### Use when

* validation passes
* a checkpoint is being prepared
* architecture or runtime behavior changed
* directory structure changed
* references are stale
* engineering records need cross-linking
* project-state information needs updating

### Required inputs

* `project_state.json`
* latest checkpoint
* latest validation
* latest implementation record
* latest RCA when applicable
* current source tree
* authoritative documentation

### Allowed work

* update SAICD
* update troubleshooting documentation
* update cross-references
* create checkpoint summaries
* update `project_state.json`
* add concise non-obvious code comments when explicitly authorized
* identify stale or duplicated artifacts
* recommend cleanup

### Must not

* add features
* refactor runtime behavior
* rewrite historical engineering records to describe later events
* move or delete files without explicit authorization
* mark unvalidated behavior as working

### Required output

* updated authoritative documentation
* Checkpoint Report when applicable
* synchronized `project_state.json`
* documentation completion summary

### Typical next step

Commit or begin the next project phase

---

## 4. Agent Selection Decision Table

| Current situation                                  | Next agent                    |
| -------------------------------------------------- | ----------------------------- |
| New feature request                                | System Architect              |
| Major structural change                            | System Architect              |
| Reported defect not yet verified                   | Validation / Diagnostic Agent |
| Implementation completed                           | Validation / Test Agent       |
| Validation fails and cause is clear                | Runtime Implementation Agent  |
| Validation fails and cause is unclear              | Root Cause Analysis Agent     |
| Failure is intermittent or timing-sensitive        | Root Cause Analysis Agent     |
| Functional behavior works but is unreliable        | Runtime Reliability Agent     |
| Runtime is stable but quality is poor              | Performance Analysis Agent    |
| Validation passes and records are stale            | Documentation Steward         |
| Documentation synchronized and checkpoint approved | Commit                        |
| Design cannot satisfy requirement                  | System Architect              |

---

## 5. Standard Agent Sequence

## 5.1 New Feature

```text
System Architect
    ->
Runtime Implementation Agent
    ->
Validation / Test Agent
    ->
Documentation Steward
    ->
Checkpoint
    ->
Commit
```

Use RCA only when validation reveals an unexplained defect.

---

## 5.2 Reproducible Defect With Known Cause

```text
Runtime Implementation Agent
    ->
Validation / Test Agent
    ->
Documentation Steward
    ->
Checkpoint or Commit
```

---

## 5.3 Reproducible Defect With Unknown Cause

```text
Validation / Diagnostic Agent
    ->
Root Cause Analysis Agent
    ->
Runtime Implementation Agent
    ->
Validation / Test Agent
    ->
Documentation Steward
```

---

## 5.4 Intermittent Reliability Defect

```text
Validation / Diagnostic Agent
    ->
Root Cause Analysis Agent
    ->
Runtime Reliability Agent
    ->
Repeated-Cycle Validation
    ->
Documentation Steward
```

---

## 5.5 Performance or Quality Improvement

```text
Performance Analysis Agent
    ->
System Architect, if interfaces must change
    ->
Runtime Implementation Agent
    ->
Validation / Test Agent
    ->
Documentation Steward
```

---

## 5.6 Stable Checkpoint

```text
Validation / Test Agent
    ->
Documentation Steward
    ->
Checkpoint Report
    ->
Update project_state.json
    ->
Commit
```

---

## 6. Handoff Contract

Every agent report should provide enough information for the next agent to begin without reconstructing the entire session.

A handoff should identify:

* completed objective
* evidence collected
* files inspected
* files modified
* tests or validation performed
* unresolved issues
* recommended next agent
* recommended next objective
* applicable report or plan
* checkpoint readiness

Reports should recommend exactly one next agent whenever practical.

---

## 7. Recommended Next Agent Rules

The next-agent recommendation should be based on evidence.

### Recommend System Architect when

* interfaces or ownership must change
* the design cannot support the requirement
* multiple implementation approaches require architectural selection

### Recommend Validation / Test Agent when

* implementation is complete
* a change requires independent proof
* regression risk exists

### Recommend Root Cause Analysis Agent when

* the failure mechanism is unknown
* behavior is intermittent
* multiple hypotheses remain

### Recommend Runtime Implementation Agent when

* the cause is proven
* the approved design is ready for implementation
* the required change is narrowly defined

### Recommend Runtime Reliability Agent when

* core behavior works
* the remaining problem concerns determinism, cleanup, races, recovery, or lifecycle

### Recommend Performance Analysis Agent when

* functionality works
* the remaining problem concerns measurable quality, latency, throughput, resource use, or signal fidelity

### Recommend Documentation Steward when

* validation passes
* records are stale
* checkpoint preparation is appropriate
* project state needs synchronization

---

## 8. Scope Ownership

Agents must not compete for ownership of the same responsibility.

| Responsibility                                  | Owner                               |
| ----------------------------------------------- | ----------------------------------- |
| Architecture and interface definitions          | System Architect                    |
| Runtime observation and pass/fail determination | Validation / Test Agent             |
| Root-cause determination                        | Root Cause Analysis Agent           |
| Functional code changes                         | Runtime Implementation Agent        |
| Concurrency and lifecycle hardening             | Runtime Reliability Agent           |
| Performance baselines and bottlenecks           | Performance Analysis Agent          |
| SAICD and troubleshooting synchronization       | Documentation Steward               |
| Checkpoint creation                             | Documentation Steward               |
| `project_state.json` checkpoint updates         | Documentation Steward               |
| Commit decision evidence                        | Validation / Test Agent             |
| Final commit action                             | User or explicitly authorized agent |

---

## 9. Project State Ownership

The Documentation Steward is the default owner of:

`docs/AI Engineering Framework/project_state.json`

Other agents may recommend changes but should not update the file unless explicitly authorized.

Update it when:

* the project phase changes
* a new checkpoint is created
* latest artifact links change
* issue status changes
* commit readiness changes
* the recommended next agent changes

Do not update project state based solely on unvalidated implementation claims.

---

## 10. Conflict Resolution

When agent outputs conflict, use this priority:

1. Current implementation and direct runtime evidence
2. Latest independent validation
3. Latest proven RCA
4. Approved Architecture Review
5. Latest implementation record
6. Authoritative documentation
7. Historical records

Conflicts must be documented rather than silently resolved.

If resolving the conflict requires changing architecture, route to the System Architect.

If resolving it requires proving behavior, route to Validation.

---

## 11. Parallel Work

Parallel agents may be used only when their scopes do not overlap.

Safe examples:

* documentation reference audit while an independent validation run executes
* PC performance analysis separate from Pi hardware inspection
* test development in a distinct subsystem with fixed interfaces

Avoid parallel work when agents may modify:

* the same files
* the same runtime process
* the same documentation source of truth
* `project_state.json`
* shared architecture or interface definitions

When in doubt, serialize the work.

---

## 12. Escalation Rules

Escalate to the user when:

* destructive file operations are proposed
* architecture changes exceed approved scope
* hardware replacement or physical intervention is required
* credentials or security-sensitive configuration is needed
* two authoritative artifacts conflict and evidence cannot resolve them
* a Medium or higher defect is being accepted for checkpoint
* the requested action would invalidate a stable checkpoint

Do not ask the user to choose a directory when an established destination exists.

---

## 13. Agent Prompt Requirements

Prompts must follow:

`docs/AI Engineering Framework/Prompt_Standards.md`

Every task prompt should make clear:

* agent role
* objective
* references
* allowed scope
* prohibited actions
* required tasks
* validation
* report type
* inline report destination

Report output must comply with:

`docs/AI Engineering Framework/Report_Standards.md`

---

## 14. Orchestration Completion Criteria

Agent orchestration is effective when:

* each task has one primary owner
* agents receive the evidence needed for their role
* investigation is separated from implementation
* validation remains independent
* reports provide deterministic handoffs
* project state reflects only validated progress
* the next agent and objective are explicit
* stable work ends in documentation synchronization and checkpointing

---

## 15. Quick Routing Checklist

Before starting the next task, ask:

1. Is this a new feature or architecture change?

   * Use the System Architect.

2. Has the reported behavior been verified?

   * If no, use Validation / Diagnostics.

3. Is the failure cause proven?

   * If no, use RCA.
   * If yes, use Implementation.

4. Does the feature work but behave inconsistently?

   * Use Runtime Reliability.

5. Does it work correctly but need quality or performance tuning?

   * Use Performance Analysis.

6. Has implementation passed validation?

   * Use Documentation Steward.

7. Are documentation, checkpoint, and project state current?

   * Commit or begin the next lifecycle phase.
