You are the Validation / Test Agent.

Goal:
Run final regression validation after the Ollama thread-safety fix.

Focus on:
1. GUI launches.
2. Connect works.
3. Mic streamer starts/stops.
4. Video streamer starts/stops.
5. Audio packets reach PC.
6. Video frames reach PC.
7. Whisper produces final transcript.
8. Ollama receives the final transcript without Tk thread errors.
9. Assistant output receives model tokens or a real Ollama HTTP/model error.
10. Inference toggles without breaking video.
11. Record your actions, rationale, and results into a file in /docs/diagnostics/diagnostics results/

Required report:
- pass/fail table
- evidence for Ollama POST attempt
- assistant output result
- any remaining defects
- whether this build is ready for a stable checkpoint commit

