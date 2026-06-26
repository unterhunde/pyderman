from __future__ import annotations

import io
import logging
import queue
import threading
import time
import unittest

import numpy as np

from pc.services.prompt_submission import PromptSubmission
from pc.services.whisper_service import WhisperService


class _Config:
    def __init__(self, threshold: float = 0.045, silence_timeout: float = 1.2) -> None:
        self.threshold = threshold
        self.silence_timeout = silence_timeout
        self.listening = True

    def is_listening_enabled(self) -> bool:
        return self.listening

    def get_silence_timeout(self) -> float:
        return self.silence_timeout

    def get_threshold(self) -> float:
        return self.threshold


class _TestWhisperService(WhisperService):
    def __init__(self, *args, responses: list[str], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._responses = responses

    def _transcribe(self, audio: np.ndarray) -> str:
        if self._responses:
            return self._responses.pop(0)
        return ""


class WhisperServiceTests(unittest.TestCase):
    def _run_phrase(self, responses: list[str], voiced_chunks: int, silent_chunks_after: int = 60):
        partials: list[str] = []
        finals: list[str] = []
        statuses: list[str] = []
        audio_queue: queue.Queue[tuple[np.ndarray, float]] = queue.Queue()
        ollama_queue: queue.Queue[PromptSubmission] = queue.Queue()
        stop_event = threading.Event()

        log_stream = io.StringIO()
        logger = logging.getLogger(f"whisper-test-{time.time_ns()}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.propagate = False
        handler = logging.StreamHandler(log_stream)
        logger.addHandler(handler)

        service = _TestWhisperService(
            audio_queue,
            ollama_queue,
            _Config(),
            stop_event,
            partials.append,
            finals.append,
            statuses.append,
            logger,
            sample_rate=16000,
            responses=responses,
        )
        service.start()

        voice = np.ones(342, dtype=np.float32)
        silence = np.zeros(342, dtype=np.float32)

        for _ in range(15):
            audio_queue.put((silence, 0.001))
        for _ in range(voiced_chunks):
            audio_queue.put((voice, 0.07))
        for _ in range(silent_chunks_after):
            audio_queue.put((silence, 0.001))

        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and ollama_queue.empty():
            time.sleep(0.02)

        stop_event.set()
        service.join(timeout=2.0)

        return partials, finals, list(ollama_queue.queue), statuses, log_stream.getvalue()

    def test_short_phrase_with_partial_is_finalized_and_queued(self) -> None:
        partials, finals, submissions, _statuses, logs = self._run_phrase(
            responses=["turn left", "turn left"],
            voiced_chunks=12,
        )

        self.assertIn("turn left", partials)
        self.assertEqual(finals, ["turn left"])
        self.assertEqual(submissions, [PromptSubmission(phrase_id=1, text="turn left")])
        self.assertIn("Speech detected | phrase=1", logs)
        self.assertIn("Partial transcript updated | phrase=1", logs)
        self.assertIn("Speech end detected | phrase=1", logs)
        self.assertIn("Final transcript generated | phrase=1", logs)
        self.assertIn("Submission queued for LLM | phrase=1", logs)

    def test_preview_fallback_submits_when_final_transcription_is_empty(self) -> None:
        _partials, finals, submissions, _statuses, logs = self._run_phrase(
            responses=["status report", ""],
            voiced_chunks=16,
        )

        self.assertEqual(finals, ["status report"])
        self.assertEqual(submissions, [PromptSubmission(phrase_id=1, text="status report")])
        self.assertIn("Final transcript fallback applied | phrase=1 source=preview", logs)

    def test_phrase_can_start_without_initial_silence_calibration(self) -> None:
        partials: list[str] = []
        finals: list[str] = []
        statuses: list[str] = []
        audio_queue: queue.Queue[tuple[np.ndarray, float]] = queue.Queue()
        ollama_queue: queue.Queue[PromptSubmission] = queue.Queue()
        stop_event = threading.Event()

        logger = logging.getLogger(f"whisper-test-{time.time_ns()}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.propagate = False
        logger.addHandler(logging.StreamHandler(io.StringIO()))

        service = _TestWhisperService(
            audio_queue,
            ollama_queue,
            _Config(),
            stop_event,
            partials.append,
            finals.append,
            statuses.append,
            logger,
            sample_rate=16000,
            responses=["hello robot", "hello robot"],
        )
        service.start()

        voice = np.ones(342, dtype=np.float32)
        silence = np.zeros(342, dtype=np.float32)

        for _ in range(18):
            audio_queue.put((voice, 0.07))
        for _ in range(60):
            audio_queue.put((silence, 0.001))

        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and ollama_queue.empty():
            time.sleep(0.02)

        stop_event.set()
        service.join(timeout=2.0)

        self.assertIn("hello robot", partials)
        self.assertEqual(finals, ["hello robot"])
        self.assertEqual(list(ollama_queue.queue), [PromptSubmission(phrase_id=1, text="hello robot")])


if __name__ == "__main__":
    unittest.main()
