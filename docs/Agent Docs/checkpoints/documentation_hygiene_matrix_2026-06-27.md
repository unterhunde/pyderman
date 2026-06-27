# Documentation Hygiene Matrix (Non-Destructive)

Date: 2026-06-27  
Owner: Documentation Steward and Project Hygiene Agent  
Scope: Historical artifacts and legacy references with stale links.

## Rules Applied

- Preserve historical records; do not rewrite conclusions.
- Mark legacy references explicitly.
- Fix navigation links when intent is unambiguous.
- Do not move, delete, or rename artifacts in this pass.

## Classification Legend

- **Legacy-Intentional:** Historical reference retained on purpose.
- **Legacy-Broken-Link:** Broken pointer where target intent is clear.
- **Obsolete-Duplicate:** Superseded artifact retained for history but not active.

## Artifact-by-Artifact Matrix

| Artifact | Issue | Classification | Action in this pass | Status | Recommended follow-up |
|---|---|---|---|---|---|
| `"docs/Agent Docs/architecture/audio_001_microphone_calibration_wizard_architecture_review_2026-06-27.md"` | Broken related-doc path to non-existent prompt copy | Legacy-Broken-Link | Repointed to `"docs/System_Architecture_and_Interface_Control_Document.md"` | Done | None |
| `"docs/Agent Docs/implementation/ssh_false_negative_reliability_fix_2026-06-26.md"` | Incorrect self-reference path under `docs/implementation/...` | Legacy-Broken-Link | Corrected to `"docs/Agent Docs/implementation/ssh_false_negative_reliability_fix_2026-06-26.md"` and added legacy artifact note | Done | None |
| `"docs/prompts/agents/second push to reliability/Prompt_Header.md"` | Legacy references to missing `docs/json/system_manifest.json` | Legacy-Broken-Link | Updated source/related docs to active authoritative docs and added explicit legacy note | Done | Consider promoting this prompt header guidance into a single maintained prompt standard location |
| `"docs/System_Architecture_and_Interface_Control_Document.md"` | Mentions non-present `docs/old-json/`, `docs/Agent Docs/old-diagnostics/`, `pibot.env` | Legacy-Intentional | Previously marked as legacy and clarified `pibot.env` default-label semantics | Retained | Optional: centralize all legacy-path notes in one appendix |
| `"docs/System_Diagnostic_and_Troubleshooting_Guide.md"` | Mentions non-present `docs/json/`, `docs/old-json/`, old diagram paths, `pibot.env` | Legacy-Intentional | Previously marked as legacy and clarified optional env-file semantics | Retained | Optional: replace old-path references with explicit “Historical Example (not present)” blocks |
| `"docs/Agent Docs/implementation/streamer_control_reliability_2026-06-26.md"` | Legacy references in historical context | Legacy-Intentional | Already contains legacy reference note; no destructive rewrite applied | Retained | Optional: add explicit “Superseded by later checkpoint/validation” cross-links |
| `"docs/prompts/agents/..."` (multiple dated campaign prompts) | Potential overlap/duplication across campaign folders | Obsolete-Duplicate | Inventory only; no move/delete in this pass | Open | Manual prompt consolidation plan (keep raw prompts + add index/active set) |

## Stale/Legacy Buckets (Repository-Level)

1. **Historical path labels retained by design**
   - `"docs/old-json/"`
   - `"docs/json/"`
   - `"docs/Agent Docs/old-diagnostics/"`
   - `"docs/old - diagnostics/*.mmd"`

2. **Optional env-file label references**
   - `pibot.env` appears as a default label; file may be absent in repository snapshots.

3. **Prompt hygiene candidates**
   - Dated prompt campaign folders under `"docs/prompts/agents/"` appear to contain reusable + obsolete variants.

## Recommended Next Hygiene Pass (No Deletions)

1. Create a single prompt index under `"docs/prompts/"` with:
   - Active prompt entry points
   - Historical archive pointers
   - “Do not use for new work” markers for obsolete variants
2. Add a compact “Legacy Path Reference Index” section in one canonical doc.
3. Add supersession links in older implementation records to latest implementation/validation/checkpoint artifacts.

## Outcome

This pass fixed clear broken links, preserved legacy context, and produced a deterministic cleanup matrix without changing runtime behavior or repository layout.
