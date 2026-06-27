"""Tests for OllamaService worker behavior."""

from __future__ import annotations

import json
import logging
import queue
import threading
import unittest
from unittest.mock import patch

from pc.services.ollama_service import OllamaService
from pc.services.prompt_submission import PromptSubmission


class _TkLikeStringVar:
    def __init__(self, value: str) -> None:
        self._value = value
        self._main_thread = threading.get_ident()
        self.off_main_get_attempts = 0

    def set(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        if threading.get_ident() != self._main_thread:
            self.off_main_get_attempts += 1
            raise RuntimeError("main thread is not in main loop")
        return self._value


class _StreamingResponse:
    def raise_for_status(self) -> None:
        return None

    def iter_lines(self):
        yield json.dumps({"response": "token-1", "done": False}).encode("utf-8")
        yield json.dumps({"response": "", "done": True}).encode("utf-8")


class OllamaServiceTests(unittest.TestCase):
    def test_worker_uses_threadsafe_url_snapshot_and_not_tk_var(self) -> None:
        """Regression: worker should use copied string state, not Tk StringVar.get()."""
        ollama_queue: queue.Queue[PromptSubmission] = queue.Queue()
        stop_event = threading.Event()
        outputs: list[str] = []
        statuses: list[str] = []
        token_seen = threading.Event()

        tk_var = _TkLikeStringVar("http://localhost:11434/api/generate")
        url_lock = threading.Lock()
        shared_url = tk_var.get()
        tk_var.set("http://localhost:22434/api/generate")
        shared_url = tk_var.get()

        def url_getter() -> str:
            with url_lock:
                return shared_url

        def on_output_append(text: str) -> None:
            outputs.append(text)
            if "token-1" in text:
                token_seen.set()

        with patch("pc.services.ollama_service.requests.post", return_value=_StreamingResponse()) as mock_post:
            service = OllamaService(
                ollama_queue=ollama_queue,
                stop_event=stop_event,
                on_output_reset=lambda: None,
                on_output_append=on_output_append,
                on_status=statuses.append,
                url_getter=url_getter,
                logger=logging.getLogger("test.ollama_service"),
                model_name="tinyllama",
            )
            service.start()
            ollama_queue.put(PromptSubmission(phrase_id=1, text="hello"))

            self.assertTrue(token_seen.wait(timeout=2.0), "Expected streamed Ollama token")
            stop_event.set()
            service.join(timeout=2.0)

            self.assertEqual(tk_var.off_main_get_attempts, 0)
            self.assertEqual(mock_post.call_args.args[0], "http://localhost:22434/api/generate")
            self.assertIn("Ollama responding...", statuses)
            self.assertIn("Listening", statuses)
            self.assertIn("token-1", "".join(outputs))


if __name__ == "__main__":
    unittest.main()
