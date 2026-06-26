You are the Runtime Implementation Agent.

Goal:
Fix Pi streamer start/stop/status reliability based on streamer_control_diagnostic_2026-06-26.md.

Allowed files:
- pc/services/pi_streamer_manager.py
- tests/ if needed

Do not edit GUI layout.
Do not redesign the app.
Do not modify unrelated files.

Required fixes:
1. In run_action(..., action="stop"), do not report stopped until the target process is actually dead.
2. Send SIGTERM first.
3. Poll for up to 3 seconds.
4. If still alive, send SIGKILL.
5. Only remove the PID file after process death is confirmed.
6. If the process survives SIGKILL or PID validation fails, return stop-failed.
7. In query_status(), guard against stale/reused PID files by verifying /proc/$pid/cmdline contains the expected streamer script name.
8. In run_action(..., action="start"), replace the fixed 0.5 second health check with a short polling loop, approximately 2 seconds total.
9. Add or update tests for:
   - stale PID file reports stopped, not running
   - stop does not return success when process remains alive
   - start does not immediately report success if the process exits during the health window
   - PID reuse does not report running for unrelated processes
10. Record your actions, rationale, and results into a file in /docs/implementation/

Validation requirements:
- Show the before/after command strings.
- Run the relevant tests.
- Do not claim the mic streamer is fixed; the diagnostic report shows a separate Pi audio hardware failure.