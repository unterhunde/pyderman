# Documentation Standards

## Purpose

This document defines the repository-wide standards for creating, updating, organizing, and maintaining PiBot engineering documentation.

These standards apply to architecture documents, troubleshooting guides, engineering records, project-state files, prompts, diagrams, indexes, and other persistent project artifacts.

Report-specific structures are defined separately in:

`docs/AI Engineering Framework/Report_Standards.md`

---

## 1. Source of Truth

The current implementation is authoritative when documentation and code disagree.

Documentation must be validated against:

* current source code
* current configuration
* current tests
* current repository structure
* validated runtime evidence

Agents must not preserve inaccurate documentation merely because it already exists.

Historical documents may describe prior behavior, but they must be clearly identified as historical or superseded.

---

## 2. Documentation Locations

Active project documentation is organized as follows:

```text
docs/
├── AI Engineering Framework/
│   ├── Documentation_Standards.md
│   ├── Prompt_Standards.md
│   ├── Report_Standards.md
│   └── project_state.json
│
├── Agent Docs/
│   ├── checkpoints/
│   ├── diagnostics/
│   ├── implementation/
│   ├── root cause analysis/
│   └── validation/
│
├── prompts/
├── System_Architecture_and_Interface_Control_Document.md
└── System_Diagnostic_and_Troubleshooting_Guide.md
```

The current repository structure must be used as the source of truth if this example becomes outdated.

Paths containing spaces must be quoted in shell commands and prompt instructions.

---

## 3. Document Categories

### Authoritative Documents

Authoritative documents describe the current project state and must remain synchronized with the implementation.

Examples:

* `System_Architecture_and_Interface_Control_Document.md`
* `System_Diagnostic_and_Troubleshooting_Guide.md`
* `project_state.json`

### Engineering Records

Engineering records preserve evidence and decisions from a specific task or development stage.

Examples:

* validation reports
* diagnostics
* Root Cause Analysis reports
* implementation records
* checkpoint summaries

Completed engineering records should not be rewritten to describe later events. Create a new record and cross-reference the earlier one.

### Framework Documents

Framework documents define how agents and engineering workflows operate.

Examples:

* documentation standards
* prompt standards
* report standards
* lifecycle or orchestration guidance

### Historical Documents

Historical documents are retained for traceability but are not authoritative.

They must be marked as one of:

* Historical
* Legacy
* Superseded
* Archived

Historical documents must not be promoted back into active use without explicit instruction.

---

## 4. Required Document Metadata

New authoritative documents and substantial engineering documents should include:

* Title
* Purpose
* Last Updated
* Source Prompt
* Source Documents Used
* Source Implementation Analyzed
* Related Documents
* Assumptions
* Revision History

Short operational notes or narrowly scoped artifacts may use the smaller metadata contract defined in `Report_Standards.md`.

Metadata must reflect the actual sources used. Do not list files that were not inspected.

---

## 5. Update Rules

Documentation must be reviewed when a change affects:

* architecture
* interfaces
* configuration
* network protocols
* ports
* processes
* threading or concurrency
* state ownership
* service lifecycle
* startup or shutdown behavior
* diagnostics
* deployment
* directory structure
* agent workflow
* validated runtime behavior

Only update documents materially affected by the change.

Do not rewrite unrelated documents solely to satisfy a general documentation instruction.

---

## 6. Editing Existing Documentation

When updating an existing document:

1. Preserve its purpose and overall structure when practical.
2. Correct inaccurate statements.
3. Update stale paths and cross-references.
4. Add a revision-history entry for material changes.
5. Distinguish current behavior from historical behavior.
6. Remove duplication where a cross-reference is sufficient.
7. Do not replace verified detail with vague summaries.
8. Do not claim a feature is working without validation evidence.

Prefer targeted edits over wholesale regeneration.

---

## 7. Creating New Documentation

Create a new document only when:

* the subject has a distinct purpose
* an existing document cannot accommodate the information cleanly
* a permanent engineering record is required
* the applicable report contract requires a new artifact

Before creating a document:

1. Search for an existing document with the same purpose.
2. Confirm the correct destination directory.
3. Use a descriptive filename.
4. Add cross-references from related documents when useful.
5. Avoid creating multiple documents that compete as the source of truth.

---

## 8. Naming Standards

Use descriptive filenames that communicate purpose.

Preferred:

```text
ssh_false_negative_rca_2026-06-26.md
ollama_thread_safety_fix_2026-06-26.md
checkpoint_runtime_stabilization_2026-06-26.md
```

Avoid:

```text
notes.md
results2.md
new_document.md
final_final.md
```

Engineering records should normally include an ISO date:

```text
YYYY-MM-DD
```

Use lowercase descriptive names for engineering records unless an established naming convention already exists.

Do not rename stable authoritative documents without explicit instruction.

---

## 9. Paths and Cross-References

Use repository-relative paths in documentation.

Preferred:

```text
pc/services/pi_streamer_manager.py
docs/Agent Docs/checkpoints/
```

Avoid machine-specific absolute paths unless they are operationally required or preserved as runtime evidence.

When a path contains spaces, quote it in commands and prompts:

```text
"docs/Agent Docs/checkpoints/"
```

Artifact destinations should remain inline with the instruction.

Preferred:

```text
Save the report in "docs/Agent Docs/validation/".
```

Avoid:

```text
Save the report in:
"docs/Agent Docs/validation/"
```

Cross-references must point to verified repository locations.

---

## 10. Facts, Evidence, and Recommendations

Documentation must distinguish between:

### Verified Fact

Confirmed by code inspection, tests, runtime evidence, or direct observation.

### Assumption

Used when required information is unavailable. Assumptions must be labeled.

### Inference

A conclusion derived from evidence but not directly observed. Inferences must identify their supporting evidence.

### Recommendation

A proposed future action. Recommendations must not be presented as implemented behavior.

Do not describe planned behavior as current behavior.

---

## 11. Code Documentation

Add code comments only when they preserve non-obvious engineering intent.

Appropriate subjects include:

* concurrency invariants
* thread ownership
* stale-result suppression
* token or generation semantics
* process lifecycle guarantees
* protocol assumptions
* descriptor detachment
* defensive PID validation
* unusual hardware constraints
* safety-critical cleanup behavior

Avoid comments that merely restate the code.

Public APIs and complex modules may use docstrings where they improve maintainability.

---

## 12. Diagrams and Tables

Use diagrams and tables when they make relationships easier to understand.

Good candidates include:

* data flow
* process lifecycle
* thread ownership
* state transitions
* network interfaces
* control-to-backend mappings
* failure classification
* configuration references

Diagrams must match the current implementation.

Do not create diagrams solely to satisfy a formatting preference.

---

## 13. Project State

`docs/AI Engineering Framework/project_state.json` is the concise current-state index for agent handoff.

It should identify:

* current project phase
* latest checkpoint
* latest engineering reports
* current known issues
* recommended next agent
* recommended next objective
* checkpoint or commit readiness

Detailed evidence belongs in engineering reports, not in `project_state.json`.

The Documentation Steward owns checkpoint-time updates to `project_state.json`, unless another owner is explicitly assigned.

---

## 14. Report Compliance

Validation reports, implementation records, RCA reports, performance reports, architecture reviews, and checkpoint reports must follow:

`docs/AI Engineering Framework/Report_Standards.md`

Task prompts should reference the applicable report contract rather than repeating its complete structure.

---

## 15. Completion Criteria

Documentation work is complete when:

* affected authoritative documents match the implementation
* new engineering records follow the applicable report contract
* paths and cross-references are valid
* current and historical information are clearly distinguished
* project-state information is synchronized when required
* no partially updated document set remains
* unresolved discrepancies are listed for manual review

The completion summary should identify:

* files inspected
* files modified
* documents created
* broken references corrected
* historical references retained
* unresolved documentation issues
