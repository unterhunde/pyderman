# Runtime Reliability RCA Fixes — Implementation Record

Date: 2026-06-26

## Scope

Implemented only the RCA-proven control-path fixes for streamer action/status reliability, focused on:

- `pc/operator_console_app.py`
- `tests/test_operator_console_streamer_reliability.py` (new)

No changes were made to streamer process reliability logic in `pc/services/pi_streamer_manager.py`, preserving prior streamer fixes.
No changes were made to Ollama service logic, preserving prior Ollama fixes.

## Implemented recommendations from RCA

1. **Generation IDs / monotonic action tokens**
   - Added per-streamer monotonic action tokens: `self._streamer_action_tokens`.
   - Added per-streamer monotonic refresh tokens: `self._streamer_refresh_tokens`.

2. **Stale-result suppression**
   - Action worker discards stale action results when token is not current.
   - Refresh UI updates are applied only when both refresh token and owner action token are still current.

3. **Single-owner status updates**
   - Action path now posts transitional state only (`Starting...` / `Stopping...` / `Checking...`).
   - Final streamer label state is now owned by confirmed `query_status` refresh results.

4. **Deterministic state transitions / newest-action wins**
   - Replaced per-click action thread spawning with one per-streamer action worker loop and pending-action slot.
   - Newer actions supersede older pending outcomes.
   - Overlapping per-streamer action execution is eliminated.

5. **Eliminate stale status updates**
   - Replaced per-refresh thread spawning with one per-streamer refresh worker loop plus token gating.
   - Out-of-order refresh results are dropped.

## Design rationale

- RCA identified multi-writer async races and missing freshness checks as the root cause.
- Token-gated callback application solves out-of-order callback hazards without broad refactor.
- Confirmed-state-only final updates remove optimistic GUI success/failure assumptions.
- Per-streamer single-worker loops remove overlapping action execution while preserving responsiveness.

## Validation performed

### Baseline/full suite execution

Command:

```bash
python3 -m unittest discover -s tests -q
```

Result:
- Suite runs, but two pre-existing environment dependency errors remain:
  - `ModuleNotFoundError: No module named 'scipy'`
  - `ModuleNotFoundError: No module named 'whisper'`

### Post-change targeted regression execution

Command:

```bash
python3 -m unittest -q tests.test_pi_streamer_manager tests.test_ollama_service tests.test_operator_console_streamer_reliability
```

Result:
- `Ran 19 tests ... OK`

### 50 rapid start/stop cycle validation (both streamers)

Covered by:
- `tests.test_operator_console_streamer_reliability.TestOperatorConsoleStreamerReliability.test_rapid_50_cycle_start_stop_for_both_streamers`

What was validated:
- 50 rapid start/stop cycles for mic and video.
- Final GUI label state always matched confirmed manager state (`stopped`).
- No incorrect final state observed.

## Functional preservation notes

- Existing `PiStreamerManager` behavior and tests are preserved.
- Existing Ollama tests are preserved and pass in available environment.
- No arbitrary sleeps, retry loops, polling increases, or broad refactors were introduced.
