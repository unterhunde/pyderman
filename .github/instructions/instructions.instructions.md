---
description: "Repository-wide PiBot engineering bootstrap directive."
applyTo: "**"
---

<!-- Tip: Use /create-instructions in chat to generate content with agent assistance -->
# Engineering Directive

This repository is under active development. Treat documentation and engineering records as part of the project.

For tasks that affect project behavior, architecture, validation status, documentation, or engineering workflow, read `"docs/AI Engineering Framework/project_state.json"` first. Use it to identify the current phase and relevant engineering artifacts.

## Core Rules

* Treat the current implementation and direct runtime evidence as authoritative when they conflict with documentation.
* Follow the applicable standards in `"docs/AI Engineering Framework/"`.
* Modify only files and documentation materially affected by the assigned task.
* Preserve known-good behavior and avoid unrelated refactoring or repository cleanup.
* Prefer updating the established authoritative document over creating a competing source of truth.
* Do not rewrite completed engineering records to reflect later events; create a new record and cross-reference the earlier one.
* Treat historical and legacy artifacts as reference only unless explicitly instructed otherwise.
* Use the current repository structure and repository-relative paths.
* Do not update `"docs/AI Engineering Framework/project_state.json"` unless the task explicitly authorizes it or the applicable lifecycle phase assigns that responsibility.
