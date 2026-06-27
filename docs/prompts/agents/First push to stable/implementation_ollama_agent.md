You are the Runtime Implementation Agent.

Goal:
Fix the Ollama worker thread-safety bug found in e2e_runtime_validation_2026-06-26.md.

Allowed files:
- pc/operator_console_app.py
- pc/services/ollama_service.py
- tests/ if needed

Do not edit Pi streamer code.
Do not edit video code.
Do not redesign the GUI.

Problem:
OllamaService runs in a worker thread and calls self.url_getter(), which currently reads Tk variable server_var.get() outside the Tk main thread. This raises:
RuntimeError: main thread is not in main loop

Required behavior:
1. Tk variables must only be read on the GUI thread.
2. OllamaService must receive a thread-safe URL source.
3. The server URL should be copied from server_var into a normal Python string/state owned by OperatorConsoleApp on the GUI thread.
4. The worker thread may read only that thread-safe string/state, not the Tk variable.
5. Preserve user ability to edit the Ollama server URL in the GUI.
6. Add/update tests proving OllamaService no longer touches Tk variables from the worker thread.
7. Re-run the relevant Whisper-to-Ollama or Ollama-service tests.
8. Record your actions, rationale, and results into a file in /docs/implementation/

Validation:
- Launch GUI.
- Connect.
- Start Listening or inject test transcript.
- Confirm final transcript is submitted.
- Confirm Ollama HTTP POST is attempted.
- Confirm assistant output receives model tokens or a real HTTP/Ollama error, not a Tk thread RuntimeError.