You are the Documentation Steward and Project Hygiene Agent.

Goal:
Prepare PiBot for a stable checkpoint commit by updating documentation, comments, and project structure records after the latest successful end-to-end validation.

Do not add features.
Do not refactor runtime logic.
Do not change behavior unless you find a documentation-only mismatch or dead/obsolete artifact that must be clearly documented first.

Reference:
- /docs/Agent Docs/diagnostics/diagnostics results/e2e_runtime_validation_ssh_false_negative_2026-06-26_22-27-00.md
- /docs/Agent Docs/implementation/ssh_false_negative_reliability_fix_2026-06-26.md
- /docs/Agent Docs/implementation/
- /docs/Agent Docs/old-diagnostics/
- System Architecture and Interface Control Document
- System Diagnostic & Troubleshooting Guide
- docs/old-json/system_manifest.json, if present

Tasks:
1. Update architecture and diagnostic documentation so it reflects the current stable runtime.
2. Update any project-state, manifest, agent-registry, or task-tracking files that help information persist between agent sessions.
3. Add concise code comments only where they explain non-obvious reliability decisions:
   - SSH spawner / descriptor detachment
   - PID cmdline guard
   - confirmed-state GUI status ownership
   - Ollama thread-safe URL cache
4. Do not comment obvious code.
5. Review directory structure for misplaced diagnostics, implementation records, prompts, or stale generated files.
6. Recommend any directory cleanup, but do not move files unless clearly safe.
7. Create or update a checkpoint summary document under /docs/Agent Docs/checkpoints/
8. The checkpoint summary must include:
   - what is now validated
   - known remaining low-severity issues
   - what should be worked on next
   - what should not be touched before commit
   - exact validation report used as evidence

Known remaining issues to document, not fix:
- Pi camera may sometimes fall back to synthetic source due to device busy.
- Raw UDP video may drop incomplete frames during startup bursts.
- Transcript fidelity needs future calibration.
- Pi microphone/AGC/hardware handling needs future refinement.

Required output:
- files inspected
- files changed
- documentation updates made
- code comments added
- directory cleanup recommendations
- checkpoint commit recommendation