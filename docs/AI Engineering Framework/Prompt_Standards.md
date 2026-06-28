# Prompt Standards

## Purpose

This document defines the standards for writing prompts used by AI agents in the PiBot repository.

The goals are to:

* reduce ambiguous agent behavior
* prevent unintended code or directory changes
* preserve continuity between agent sessions
* keep prompts concise and reusable
* separate task instructions from report-format requirements
* ensure agents operate from current project evidence

Report structures are defined separately in:

`docs/AI Engineering Framework/Report_Standards.md`

Documentation governance is defined in:

`docs/AI Engineering Framework/Documentation_Standards.md`

---

## 1. Starting Context

Every agent should read:

`docs/AI Engineering Framework/project_state.json`

before beginning work.

Use it to identify:

* current project phase
* latest checkpoint
* latest validation
* latest implementation record
* latest Root Cause Analysis
* known issues
* recommended next objective

Task prompts should reference only the additional artifacts needed for the specific task.

Do not instruct an agent to read the entire repository or all documentation unless a repository-wide audit is explicitly required.

---

## 2. One Primary Responsibility Per Prompt

Each prompt should assign one primary role and one primary objective.

Preferred:

```text
You are the Root Cause Analysis Agent.

Goal:
Determine why streamer start actions intermittently report failure after the Pi process starts.
```

Avoid combining unrelated responsibilities:

```text
Diagnose the issue, fix it, redesign the GUI, update all documentation, and validate everything.
```

Separate investigation, implementation, validation, and documentation into distinct tasks whenever practical.

---

## 3. Required Prompt Structure

A task prompt should normally contain:

1. Agent role
2. Goal
3. Current or known context
4. References
5. Allowed scope
6. Prohibited actions
7. Required tasks
8. Validation requirements
9. Required output
10. Report contract and destination

Not every prompt needs every section, but omissions should be intentional.

---

## 4. Agent Role

Start prompts with a precise role.

Examples:

* System Architect
* Runtime Implementation Agent
* Validation / Test Agent
* Root Cause Analysis Agent
* Runtime Reliability Agent
* Documentation Steward and Project Hygiene Agent
* Performance Analysis Agent

The role should match the type of uncertainty being resolved.

| Question                                        | Appropriate role             |
| ----------------------------------------------- | ---------------------------- |
| What should the system look like?               | System Architect             |
| What is the system actually doing?              | Validation / Test Agent      |
| Why is it failing?                              | Root Cause Analysis Agent    |
| How should the proven defect be fixed?          | Runtime Implementation Agent |
| How can working behavior be made deterministic? | Runtime Reliability Agent    |
| Does the documentation match reality?           | Documentation Steward        |
| Where is the bottleneck?                        | Performance Analysis Agent   |

---

## 5. Goal Statements

The goal should describe one measurable outcome.

Preferred:

```text
Goal:
Determine the exact cause of the SSH start-command timeout without modifying runtime behavior.
```

Avoid:

```text
Goal:
Improve SSH reliability.
```

A good goal states:

* what system or behavior is involved
* what result is expected
* whether the task is investigation, implementation, validation, or documentation

---

## 6. References

Reference exact repository-relative paths.

Preferred:

```text
Use the evidence in "docs/Agent Docs/root cause analysis/ssh_false_negative_rca_2026-06-26.md".
```

Do not use vague references such as:

```text
Use the latest report.
```

unless `project_state.json` identifies it unambiguously.

Only reference documents relevant to the task.

Do not list files merely because they exist.

---

## 7. File and Directory Paths

Keep destination paths inline with the instruction.

Preferred:

```text
Save the validation report in "docs/Agent Docs/validation/".
```

Avoid:

```text
Save the validation report in:
"docs/Agent Docs/validation/"
```

The multiline colon form may be interpreted as an unresolved parameter and cause the agent to ask which directory to use.

Paths containing spaces must be quoted.

Use repository-relative paths unless an absolute runtime path is operationally required.

---

## 8. Allowed Scope

State exactly which files, directories, or subsystems the agent may modify.

Example:

```text
Allowed files:
- pc/services/pi_streamer_manager.py
- tests/test_pi_streamer_manager.py
- "docs/Agent Docs/implementation/"
```

For narrow fixes, use an explicit allowlist.

For investigations, state whether temporary instrumentation is permitted.

Example:

```text
Temporary instrumentation is allowed only in the listed files and must be removed or clearly isolated before completion.
```

---

## 9. Prohibited Actions

State what the agent must not do when unintended expansion would be risky.

Examples:

```text
Do not redesign the GUI.
Do not modify Pi streamer scripts.
Do not refactor unrelated modules.
Do not move or delete files.
Do not implement recommendations during this RCA.
```

Avoid excessive prohibitions that merely restate the role.

Include restrictions that protect known-good behavior or repository structure.

---

## 10. Evidence Before Implementation

Do not ask an implementation agent to fix a defect whose cause has not been established.

Use this decision rule:

```text
Cause proven:
Proceed to targeted implementation.

Cause unproven but reproducible:
Run diagnostics or Root Cause Analysis.

Intermittent or timing-dependent:
Instrument and run Root Cause Analysis before implementation.
```

Implementation prompts should reference the evidence proving the root cause.

Preferred:

```text
Implement only the recommendations proven by "docs/Agent Docs/root cause analysis/ssh_false_negative_rca_2026-06-26.md".
```

---

## 11. Preserve Known-Good Behavior

Implementation prompts should identify behavior that must remain intact.

Example:

```text
Preserve:
- existing streamer stop semantics
- PID cmdline validation
- GUI stale-result suppression
- Ollama thread-safety behavior
- all currently passing tests
```

This is especially important when working in shared orchestration or runtime modules.

---

## 12. Required Tasks

Use numbered tasks when ordering matters.

Each task should describe observable work.

Preferred:

```text
1. Reproduce the reported failure.
2. Capture SSH return code, stdout, stderr, and elapsed time.
3. Verify the Pi process state immediately after failure.
4. Classify the failure mechanism.
```

Avoid vague tasks such as:

```text
Investigate thoroughly.
Make it robust.
Clean up the code.
```

---

## 13. Validation Requirements

Every implementation prompt should define how success will be demonstrated.

Validation may include:

* targeted unit tests
* regression suite
* syntax or static checks
* live PC/Pi execution
* process and PID verification
* network packet evidence
* GUI state confirmation
* repeated-cycle reliability tests
* comparison against prior validation

Do not accept statements such as “should work” as validation.

Preferred:

```text
Repeat 10 live start/stop cycles for mic and video and verify the final GUI state matches the confirmed Pi process state.
```

---

## 14. Report Contracts

Do not repeat complete report formats inside each prompt.

Reference the applicable contract in:

`docs/AI Engineering Framework/Report_Standards.md`

Examples:

```text
Produce a Validation Report compliant with "docs/AI Engineering Framework/Report_Standards.md" and save it in "docs/Agent Docs/validation/".
```

```text
Produce an Implementation Record compliant with "docs/AI Engineering Framework/Report_Standards.md" and save it in "docs/Agent Docs/implementation/".
```

The task prompt defines what work must be performed.

The report standard defines how the resulting artifact must be structured.

---

## 15. Report Destinations

Use the established engineering-record locations:

| Report type           | Destination                            |
| --------------------- | -------------------------------------- |
| Validation Report     | `docs/Agent Docs/validation/`          |
| Diagnostic Report     | `docs/Agent Docs/diagnostics/`         |
| Root Cause Analysis   | `docs/Agent Docs/root cause analysis/` |
| Implementation Record | `docs/Agent Docs/implementation/`      |
| Checkpoint Report     | `docs/Agent Docs/checkpoints/`         |

Do not ask the agent to choose a destination when one is already established.

---

## 16. Temporary Instrumentation

For diagnostics and RCA tasks:

* permit only the minimum instrumentation needed
* require timestamps and relevant identifiers
* identify temporary changes clearly
* do not allow instrumentation to alter behavior materially
* require removal or isolation before completion

Useful fields may include:

* timestamp
* thread name and identifier
* action token or generation
* process ID
* command
* elapsed time
* return code
* stdout and stderr
* state before and after the event

Do not require every possible field when it is unrelated to the failure.

---

## 17. Facts, Assumptions, and Recommendations

Prompts should require agents to separate:

* verified facts
* assumptions
* inferences
* recommendations

RCA prompts must not permit recommendations to be described as proven fixes.

Implementation prompts must not describe tests as passed unless they were executed.

Validation prompts must not edit code unless explicitly authorized.

---

## 18. Handling Defects Found During Validation

A validation task should normally remain read-only.

Preferred instruction:

```text
Do not edit code. If a defect is found, document the failure, evidence, severity, and recommended next agent.
```

Only permit immediate edits when the task explicitly includes implementation authority.

This keeps validation evidence independent from implementation work.

---

## 19. Prompt Reuse

Store reusable prompts under:

`docs/prompts/`

Organize them by function when practical:

```text
docs/prompts/
├── architecture/
├── diagnostics/
├── documentation/
├── implementation/
├── reliability/
├── validation/
└── templates/
```

Reusable prompts should use placeholders for changing values.

Example:

```text
Implement only the recommendations proven by "<RCA_PATH>".
```

Do not copy obsolete file paths into new prompts.

---

## 20. Prompt Size and Repetition

Prompts should contain enough detail to control scope but should not duplicate:

* the always-on Engineering Directive
* report templates
* documentation metadata rules
* project state already available in `project_state.json`
* generic agent responsibilities already defined elsewhere

Include only task-specific context, constraints, evidence, and validation.

When a prompt becomes long, determine whether repeated material belongs in:

* `Documentation_Standards.md`
* `Report_Standards.md`
* this document
* an agent definition
* `project_state.json`

---

## 21. Standard Prompt Template

```text
You are the <AGENT ROLE>.

Goal:
<ONE PRIMARY, MEASURABLE OBJECTIVE>

Read "docs/AI Engineering Framework/project_state.json" first.

Reference:
- "<RELEVANT ARTIFACT>"
- "<RELEVANT SOURCE FILE>"

Allowed scope:
- <FILE OR DIRECTORY>
- <FILE OR DIRECTORY>

Do not:
- <PROHIBITED ACTION>
- <PROHIBITED ACTION>

Required tasks:
1. <TASK>
2. <TASK>
3. <TASK>

Validation:
1. <VALIDATION STEP>
2. <VALIDATION STEP>

Produce a <REPORT TYPE> compliant with "docs/AI Engineering Framework/Report_Standards.md" and save it in "<DESTINATION DIRECTORY>".

Required completion summary:
- files inspected
- files modified
- tests or validation performed
- remaining issues
- recommended next agent
```

Remove sections that do not apply rather than leaving empty placeholders.

---

## 22. Investigation Prompt Template

```text
You are the Root Cause Analysis Agent.

Goal:
Determine the verified cause of <PROBLEM>.

Read "docs/AI Engineering Framework/project_state.json" first.

Reference:
- "<VALIDATION OR DIAGNOSTIC REPORT>"

This is an investigation only.

Do not modify production behavior.
Do not implement a permanent fix.
Do not refactor unrelated code.

Focus on:
- <FILES OR SUBSYSTEMS>

Collect:
- <REQUIRED EVIDENCE>

Determine:
- <QUESTIONS TO ANSWER>

Produce a Root Cause Analysis compliant with "docs/AI Engineering Framework/Report_Standards.md" and save it in "docs/Agent Docs/root cause analysis/".
```

---

## 23. Implementation Prompt Template

```text
You are the Runtime Implementation Agent.

Goal:
Implement only the changes proven necessary by "<RCA OR APPROVED PLAN>".

Read "docs/AI Engineering Framework/project_state.json" first.

Allowed files:
- <FILE>
- <FILE>
- tests/ as needed

Preserve:
- <KNOWN-GOOD BEHAVIOR>
- all passing tests

Do not:
- broaden the scope
- refactor unrelated modules
- add unrequested features

Required changes:
1. <CHANGE>
2. <CHANGE>

Validation:
1. Run targeted tests.
2. Run applicable regression tests.
3. Perform live validation when required.

Produce an Implementation Record compliant with "docs/AI Engineering Framework/Report_Standards.md" and save it in "docs/Agent Docs/implementation/".
```

---

## 24. Validation Prompt Template

```text
You are the Validation / Test Agent.

Goal:
Validate <IMPLEMENTATION OR CHECKPOINT> from GUI controls through real runtime behavior.

Read "docs/AI Engineering Framework/project_state.json" first.

Do not edit code.

Validate:
1. <OBJECTIVE>
2. <OBJECTIVE>
3. <OBJECTIVE>

Collect:
- command output
- GUI observations
- process/PID evidence
- network or runtime evidence
- regression results

Produce a Validation Report compliant with "docs/AI Engineering Framework/Report_Standards.md" and save it in "docs/Agent Docs/validation/".
```

---

## 25. Completion Criteria

A prompt is sufficiently defined when the agent can determine:

* what role it has
* what objective it must achieve
* what evidence it should use
* what files it may modify
* what it must not change
* how success will be validated
* what report it must produce
* where the report must be saved

If any of these are materially ambiguous, revise the prompt before execution.
## 26. Resource-Bounded Execution

Agents must prefer narrow, sequential test execution over broad repeated test runs.

Commands that may block must use timeouts. Polling loops, queues, telemetry histories, and retries must be bounded. Agents must terminate confirmed orphaned processes after failed or interrupted runs.

Full-suite, full-GUI, model-loading, and live end-to-end tests should run only after targeted tests pass and only once per relevant implementation state.