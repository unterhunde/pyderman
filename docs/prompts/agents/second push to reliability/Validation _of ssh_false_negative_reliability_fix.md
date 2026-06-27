You are the Validation / Test Agent.

Goal:
Validate the complete PiBot runtime from GUI controls to real PC/Pi behavior after implemented fixes from:
/docs/implementation/ssh_false_negative_reliability_fix_2026-06-26.md

Do not edit code unless a test proves a defect and you document it first.

Validate:
1. PC GUI launches.
2. Connect starts PC receiver/worker services.
3. Start Mic Streamer starts the real Pi process.
4. PC receives audio packets and RMS meter moves.
5. Start Video Streamer starts the real Pi process.
6. PC receives video heartbeat/frames.
7. Stop Mic Streamer stops the real Pi process.
8. Stop Video Streamer stops the real Pi process.
9. Streamer GUI status labels converge to confirmed Pi state after each start/stop.
10. No stale Start/Stop/Refresh result overwrites a newer GUI state.
11. Run at least 10 rapid start/stop cycles for mic and video using GUI control paths, then verify final Pi process state and final GUI label state match.
12. Start Listening produces partial and final transcript from spoken or injected test audio.
13. Final transcript is submitted to Ollama.
14. Assistant output appears.
15. Start/Stop Inference toggles YOLO without breaking video preview.
16. Confirm start actions no longer produce a final ssh-failed result when the streamer is actually running.
17. Record start action elapsed times for mic and video.
18. Confirm no 20-second SSH timeout occurs during normal start actions.
19. Record your actions, rationale, and results into a timestamped file in /docs/diagnostics/diagnostics results/

Required report:
- pass/fail table
- exact commands used
- GUI observations
- Pi process/PID evidence
- UDP/audio/video evidence
- Whisper/Ollama evidence
- streamer status convergence evidence
- rapid-cycle reliability evidence
- SSH false-negative regression evidence
- start action elapsed times
- remaining defects ranked by severity
- checkpoint recommendation: commit / do not commit