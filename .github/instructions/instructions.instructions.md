---
description: "Always-on documentation maintenance directive for all tasks in this workspace"
applyTo: "**"
---

<!-- Tip: Use /create-instructions in chat to generate content with agent assistance -->

---

description: "Repository-wide engineering and documentation standards."
applyTo: "**"
-------------

# PiBot Engineering Directive

This repository is under active development. Treat documentation as part of the implementation.

## General Rules

* Do not assume documentation is correct. Validate it against the current implementation.
* Keep architecture, implementation, diagnostics, validation, and project-state documentation synchronized with implementation changes.
* Preserve existing document structure whenever practical. Extend documentation rather than replacing it.
* Prefer updating existing documents over creating new ones.
* Maintain cross-references between related documents instead of duplicating information.
* Treat historical documentation as reference only; do not restore or promote legacy artifacts without explicit instruction.
* Use the current repository structure as the source of truth.

## Documentation Requirements

When documentation is created or substantially updated, include:

* Title
* Purpose
* Last Updated
* Source Prompt
* Source Documents Used
* Source Implementation Analyzed
* Related Documents
* Assumptions
* Revision History

When helpful, prefer tables, diagrams, indexes, and cross-references over duplicated prose.

## Completion Criteria

A task is not complete until any affected documentation has been updated or the reason it was intentionally left unchanged has been documented.

When finished, report:

* Code files modified
* Documentation modified
* New documentation created
* Manual follow-up recommendations
