# Prompt Header

**Title:** PiBot Documentation Maintenance Directive  
**Purpose:** Define mandatory documentation maintenance requirements for all implementation and documentation changes.  
**Last Updated:** 2026-06-26  
**Source Prompt:** User request to create `Prompt_Header.md` and `prompt_header.json` in `/docs/`  
**Source Documents Used:** `docs/AI Engineering Framework/project_state.json`, `docs/System_Architecture_and_Interface_Control_Document.md`, `docs/System_Diagnostic_and_Troubleshooting_Guide.md`  
**Source Implementation Analyzed:** Repository documentation tree under `docs/`  
**Related Documents:** `docs/AI Engineering Framework/project_state.json`, `docs/System_Architecture_and_Interface_Control_Document.md`, `docs/System_Diagnostic_and_Troubleshooting_Guide.md`  
**Assumptions:** `prompts/` may not exist in this workspace snapshot.  

**Legacy reference note:** Earlier prompt-header versions referenced `docs/json/system_manifest.json`.
That path is not present in this snapshot and is retained as a historical label only.

Documentation is part of the implementation. Any modification to behavior, interfaces, architecture, configuration, protocols, threading, networking, or runtime characteristics is incomplete until all affected documentation has been updated and cross-referenced.

# PiBot Documentation Maintenance Directive

This repository is under active development. Treat all documentation as living engineering documentation.

Before making code changes or generating new documentation:

1. Read and understand all existing documentation in the `docs/` directory and all relevant files in the `prompts/` directory.
2. Treat `docs/AI Engineering Framework/project_state.json` as the authoritative project-state index, and treat current implementation/runtime evidence as authoritative when documentation differs.
3. Validate documentation against the current implementation rather than assuming it is correct.
4. If implementation differs from documentation, update the documentation to match the implementation.
5. Preserve existing document structure and expand it instead of replacing it whenever practical.
6. Maintain cross-references between all documentation.
7. When creating a new document:

   * Add references to related documents.
   * Update any documentation indexes if present.
   * Reference the prompt used to generate the document.
8. If code changes modify architecture, interfaces, configuration, threading, networking, data flow, diagnostics, or runtime behavior, update all affected documentation before considering the task complete.
9. Never leave documentation in a partially updated state.
10. When finished, provide a summary listing:

    * Code files modified
    * Documentation updated
    * New documentation created
    * Any documentation that should be reviewed manually

## Documentation Generation Rules

Every generated document should include:

* Title
* Purpose
* Last Updated date
* Source prompt
* Source documents used
* Source implementation analyzed
* Related documents
* Assumptions
* Revision history

Whenever possible, generate diagrams, tables, indexes, and cross-references that make the documentation easier to maintain.

Do not duplicate information unnecessarily. Reference existing documents when appropriate and extend them instead of creating conflicting documentation.

## Revision History

| Date       | Change |
|------------|--------|
| 2026-06-26 | Initial creation of Prompt Header directive document. |
