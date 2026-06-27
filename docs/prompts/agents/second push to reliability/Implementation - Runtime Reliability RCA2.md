You are the Runtime Reliability Agent.

Implement ONLY the recommendations proven by:
/docs/diagnostics/Root Cause Analysis/ssh_false_negative_rca_2026-06-26.md

Goal:
Fix streamer start false-negatives caused by SSH command timeout after the remote streamer has already started.

Root cause:
The remote nohup-started streamer process inherits an SSH-related socket file descriptor, causing the local SSH subprocess to remain open until timeout. run_action then reports ssh-failed even though the streamer is running.

Allowed files:
- pc/services/pi_streamer_manager.py
- tests/ as needed
- docs/implementation/ssh_false_negative_reliability_fix_2026-06-26.md

Do not edit:
- pc/operator_console_app.py unless absolutely required
- Pi streamer scripts
- Ollama code
- GUI layout

Required implementation:
1. Fix the remote start command so the background streamer process does not keep the SSH session open.
2. Ensure stdin/stdout/stderr and inherited descriptors are detached correctly.
3. Preserve PID/log behavior:
   - .run/mic_streamer.pid
   - .run/video_streamer.pid
   - .run/mic_streamer.log
   - .run/video_streamer.log
4. If start command still times out, classify the result by checking actual remote process state.
5. Do not return plain "ssh-failed" when the streamer is confirmed running.
6. Distinguish:
   - transport-failed
   - remote-command-failed
   - started-but-ack-failed
   - started/status-confirmed-running
7. Preserve existing stop behavior:
   - SIGTERM
   - wait
   - SIGKILL escalation
   - remove PID only after confirmed dead
8. Preserve existing PID cmdline guard in query_status().

Validation:
1. Run all available tests.
2. Add/update tests for:
   - start command detaches SSH session correctly
   - timeout with confirmed running does not return ssh-failed
   - timeout with not running returns failure
   - nonzero SSH failure remains failure
3. Live Pi validation:
   - start mic returns success without 20s timeout
   - start video returns success without 20s timeout
   - SSH action elapsed time is short, ideally under 5 seconds
   - refresh confirms running
   - stop confirms stopped
4. Repeat rapid start/stop validation.

Record:
- actions taken
- rationale
- files changed
- before/after command shape
- test results
- live Pi evidence
- remaining defects

Save the implementation report to /docs/implementation/ssh_false_negative_reliability_fix_2026-06-26.md
