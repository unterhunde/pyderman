# Ollama Worker Thread-Safety Fix — Implementation Record

**Date:** 2026-06-26  
**Scope:** Fix Tk thread-unsafe Ollama URL access (`RuntimeError: main thread is not in main loop`) found in `e2e_runtime_validation_2026-06-26.md`.

## Summary

The crash happened because `OllamaService` runs on a worker thread but received a URL getter that read `server_var.get()` (a Tk variable) off the Tk main thread.

Implemented fix:

1. `OperatorConsoleApp` now owns a thread-safe plain-string Ollama URL cache:
   - `self._ollama_server_url` (Python string)
   - `self._ollama_server_url_lock` (`threading.Lock`)
2. `server_var` writes are mirrored on the GUI thread via `trace_add("write", ...)` into that cache.
3. Worker-facing URL source is now `self._get_ollama_server_url` (lock-protected string read), not `server_var.get()`.
4. Startup checks also use the cached URL snapshot.
5. `OllamaService` now reads `url_getter()` once per submission and reuses the same URL for logging + POST.

## Files Changed

- `pc/operator_console_app.py`
  - Added thread-safe URL cache and accessors:
    - `_on_server_var_changed`
    - `_sync_ollama_server_url_from_var`
    - `_get_ollama_server_url`
  - Wired `server_var.trace_add("write", ...)` for GUI-thread synchronization.
  - Updated `connect()` to pass `_get_ollama_server_url` to `OllamaService`.
  - Updated `run_startup_checks()` to use the cached URL.

- `pc/services/ollama_service.py`
  - Resolved URL once per request (`server_url = self.url_getter()`) and reused it for both log and `requests.post`.

- `tests/test_ollama_service.py` (new)
  - Added regression test with a Tk-like variable that raises if read off-main-thread.
  - Simulates GUI-thread copy into a plain shared string state.
  - Verifies worker successfully streams tokens and performs POST using copied URL.
  - Verifies no off-main-thread `get()` attempts on Tk-like variable.

## Test/Verification Results

Executed:

1. Baseline test discovery:
   - `python3 -m unittest discover -s tests -v`
   - Result: existing environment missing optional deps (`scipy`, `whisper`) for whisper/e2e modules.

2. Relevant regression tests:
   - `python3 -m unittest tests.test_ollama_service -v` → **PASS**
   - `python3 -m unittest tests.test_pi_streamer_manager -v` → **PASS (15 tests)**
   - `python3 -m unittest tests.test_e2e_whisper_to_ollama -v` → import error due to missing `scipy` (environment dependency)

3. Syntax validation:
   - `python3 -m py_compile pc/operator_console_app.py pc/services/ollama_service.py tests/test_ollama_service.py` → **PASS**

## Validation Mapping to Required Behavior

1. Tk variables read only on GUI thread: **Implemented** (`server_var.get()` confined to GUI callbacks/methods).
2. OllamaService receives thread-safe URL source: **Implemented** (`_get_ollama_server_url`).
3. URL copied from `server_var` to normal Python state in app: **Implemented** (`_ollama_server_url`).
4. Worker reads only thread-safe state: **Implemented**.
5. User can still edit URL in GUI: **Preserved** (`Entry` still bound to `server_var`; trace sync updates cache).
6. Tests proving no Tk-variable worker access: **Implemented** (`tests/test_ollama_service.py`).
7. Relevant Ollama/Whisper tests rerun: **Done** (Ollama-service regression test passed; whisper e2e blocked by missing deps).
8. Actions/rationale/results recorded: **This file**.
