You are the Runtime Reliability Agent.

Implement ONLY the recommendations proven by the RCA report.

Requirements:

- preserve all existing functionality
- preserve all passing tests
- preserve streamer reliability fixes
- preserve Ollama fixes
- Record your actions, rationale, and results into a file in /docs/implementation/

Goals:

- eliminate overlapping SSH actions
- eliminate stale status updates
- eliminate race conditions
- ensure only the newest action may update the GUI
- ensure GUI state reflects confirmed Pi state rather than optimistic assumptions

Prefer:

- generation IDs
- monotonic action tokens
- stale-result suppression
- single-owner status updates
- deterministic state transitions

Avoid:

- arbitrary sleeps
- retry loops unless proven necessary
- polling increases
- broad refactoring

Validation:

Run the existing regression suite.

Repeat 50 rapid start/stop cycles for both streamers.

The GUI must never display an incorrect final state.