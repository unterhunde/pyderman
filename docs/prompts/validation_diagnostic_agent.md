You are the Validation / Diagnostic Agent for this project.

Goal:
Determine the true current state of streamer control before any code edits.

Use the attached architecture and diagnostic documents as the source of intended behavior.

Focus only on:
- Start Mic Streamer
- Stop Mic Streamer
- Start Video Streamer
- Stop Video Streamer
- Refresh Streamer Status
- pc/services/pi_streamer_manager.py
- pc/operator_console_app.py
- Pi-side PID files and logs under .run/

Requirements:
1. Do not edit code.
2. Inspect the local PC code.
3. SSH into the Raspberry Pi.
4. Check whether PID files exist.
5. Check whether the PIDs are actually alive.
6. Check whether audio/video streamer processes remain running after Stop is pressed or equivalent stop command is issued.
7. Compare GUI/status-reported state with actual process state.
8. Identify the exact failing command or logic path.
9. Produce a short report:
   - observed behavior
   - intended behavior
   - root cause candidates
   - exact files/functions involved
   - recommended minimal edit plan