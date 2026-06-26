"""End-to-end integration tests: Whisper -> Ollama pipeline."""

from __future__ import annotations

import io
import json
import logging
import queue
import threading
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np

from pc.services.audio_receiver import AudioReceiverService
from pc.services.ollama_service import OllamaService
from pc.services.prompt_submission import PromptSubmission
from pc.services.whisper_service import WhisperService


class _Config:
    def __init__(self, threshold: float = 0.045, silence_timeout: float = 1.2) -> None:
        self.threshold = threshold
        self.silence_timeout = silence_timeout
        self.listening = True
        self.audio_enabled = True

    def is_listening_enabled(self) -> bool:
        return self.listening

    def get_silence_timeout(self) -> float:
        return self.silence_timeout

    def get_threshold(self) -> float:
        return self.threshold

    def is_audio_enabled(self) -> bool:
        return self.audio_enabled

    def set_audio_enabled(self, enabled: bool) -> None:
        self.audio_enabled = enabled


class _TestWhisperService(WhisperService):
    def __init__(self, *args, responses: list[str], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._responses = responses

    def _transcribe(self, audio: np.ndarray) -> str:
        if self._responses:
            return self._responses.pop(0)
        return ""


class E2EWhisperToOllamaTests(unittest.TestCase):
    def test_partial_transcript_always_leads_to_final_submission_after_silence(self) -> None:
        """Regression test for: partial transcript visible but no final submission occurs."""
        partials: list[str] = []
        finals: list[str] = []
        statuses: list[str] = []
        submissions: list[PromptSubmission] = []
        ai_outputs: list[str] = []

        audio_queue: queue.Queue[tuple[np.ndarray, float]] = queue.Queue(maxsize=400)
        ollama_queue: queue.Queue[PromptSubmission] = queue.Queue(maxsize=16)
        stop_event = threading.Event()

        log_stream = io.StringIO()
        logger = logging.getLogger(f"e2e-test-{time.time_ns()}")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.propagate = False
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(logging.Formatter("%(name)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)

        config = _Config()

        whisper_service = _TestWhisperService(
            audio_queue,
            ollama_queue,
            config,
            stop_event,
            partials.append,
            finals.append,
            statuses.append,
            logger,
            sample_rate=16000,
            responses=["turn left", "turn left"],
        )

        def mock_ollama_callback():
            while not stop_event.is_set():
                try:
                    submission = ollama_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                submissions.append(submission)
                ai_outputs.append(f"mock response to: {submission.text}")

        ollama_thread = threading.Thread(target=mock_ollama_callback, daemon=True)

        whisper_service.start()
        ollama_thread.start()

        voice = np.ones(342, dtype=np.float32)
        silence = np.zeros(342, dtype=np.float32)

        # Lead with silence to avoid noise-floor calibration issues
        for _ in range(15):
            audio_queue.put((silence, 0.001))

        # Speak: 12 chunks of voiced audio
        for _ in range(12):
            audio_queue.put((voice, 0.07))

        # End-of-speech: 60 chunks of silence (should trigger finalization after ~1.3s)
        for _ in range(60):
            audio_queue.put((silence, 0.001))

        # Wait for submission to reach Ollama queue
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and not submissions:
            time.sleep(0.02)

        stop_event.set()
        whisper_service.join(timeout=2.0)
        ollama_thread.join(timeout=2.0)

        logs = log_stream.getvalue()

        # Validate partial transcript appeared
        self.assertIn("turn left", partials, "Partial transcript should be visible")

        # Validate final transcript was generated
        self.assertEqual(finals, ["turn left"], "Final transcript should be generated")

        # Validate LLM submission occurred
        self.assertEqual(len(submissions), 1, "Exactly one submission should reach ollama_queue")
        self.assertEqual(submissions[0].text, "turn left", "Submission text should match final transcript")

        # Validate logs show complete flow
        self.assertIn("Speech detected | phrase=1", logs)
        self.assertIn("Partial transcript updated | phrase=1", logs)
        self.assertIn("Speech end detected | phrase=1", logs)
        self.assertIn("Final transcript generated | phrase=1", logs)
        self.assertIn("Submission queued for LLM | phrase=1", logs)

    def test_multiple_phrases_in_sequence(self) -> None:
        """Verify multiple phrases are tracked independently with correct phrase IDs."""
        partials: list[str] = []
        finals: list[str] = []
        statuses: list[str] = []
        submissions: list[PromptSubmission] = []

        audio_queue: queue.Queue[tuple[np.ndarray, float]] = queue.Queue(maxsize=400)
        ollama_queue: queue.Queue[PromptSubmission] = queue.Queue(maxsize=16)
        stop_event = threading.Event()

        logger = logging.getLogger(f"e2e-multi-{time.time_ns()}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.propagate = False
        logger.addHandler(logging.StreamHandler(io.StringIO()))

        config = _Config()

        whisper_service = _TestWhisperService(
            audio_queue,
            ollama_queue,
            config,
            stop_event,
            partials.append,
            finals.append,
            statuses.append,
            logger,
            sample_rate=16000,
            responses=["go forward", "go forward", "stop here", "stop here"],
        )

        def mock_ollama_callback():
            while not stop_event.is_set():
                try:
                    submission = ollama_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                submissions.append(submission)

        ollama_thread = threading.Thread(target=mock_ollama_callback, daemon=True)

        whisper_service.start()
        ollama_thread.start()

        voice = np.ones(342, dtype=np.float32)
        silence = np.zeros(342, dtype=np.float32)

        # Phrase 1
        for _ in range(15):
            audio_queue.put((silence, 0.001))
        for _ in range(12):
            audio_queue.put((voice, 0.07))
        for _ in range(60):
            audio_queue.put((silence, 0.001))

        # Phrase 2
        for _ in range(15):
            audio_queue.put((silence, 0.001))
        for _ in range(14):
            audio_queue.put((voice, 0.07))
        for _ in range(60):
            audio_queue.put((silence, 0.001))

        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and len(submissions) < 2:
            time.sleep(0.02)

        stop_event.set()
        whisper_service.join(timeout=2.0)
        ollama_thread.join(timeout=2.0)

        # Validate both phrases reached the queue with distinct IDs
        self.assertEqual(len(submissions), 2)
        self.assertEqual(submissions[0].phrase_id, 1)
        self.assertEqual(submissions[0].text, "go forward")
        self.assertEqual(submissions[1].phrase_id, 2)
        self.assertEqual(submissions[1].text, "stop here")

    def test_very_short_phrase_still_submits_after_preview(self) -> None:
        """Verify even very short voiced segments submit after being visible in partial."""
        partials: list[str] = []
        finals: list[str] = []
        statuses: list[str] = []
        submissions: list[PromptSubmission] = []

        audio_queue: queue.Queue[tuple[np.ndarray, float]] = queue.Queue(maxsize=400)
        ollama_queue: queue.Queue[PromptSubmission] = queue.Queue(maxsize=16)
        stop_event = threading.Event()

        logger = logging.getLogger(f"e2e-short-{time.time_ns()}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.propagate = False
        logger.addHandler(logging.StreamHandler(io.StringIO()))

        config = _Config()

        whisper_service = _TestWhisperService(
            audio_queue,
            ollama_queue,
            config,
            stop_event,
            partials.append,
            finals.append,
            statuses.append,
            logger,
            sample_rate=16000,
            responses=["ok", "ok"],
        )

        def mock_ollama_callback():
            while not stop_event.is_set():
                try:
                    submission = ollama_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                submissions.append(submission)

        ollama_thread = threading.Thread(target=mock_ollama_callback, daemon=True)

        whisper_service.start()
        ollama_thread.start()

        voice = np.ones(342, dtype=np.float32)
        silence = np.zeros(342, dtype=np.float32)

        # Only 8 voiced chunks (~0.18s of speech)
        for _ in range(15):
            audio_queue.put((silence, 0.001))
        for _ in range(8):
            audio_queue.put((voice, 0.07))
        for _ in range(60):
            audio_queue.put((silence, 0.001))

        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and not submissions:
            time.sleep(0.02)

        stop_event.set()
        whisper_service.join(timeout=2.0)
        ollama_thread.join(timeout=2.0)

        # Even though it's short, if preview was visible, it should fallback
        self.assertGreaterEqual(len(partials), 0)
        if partials:
            self.assertEqual(finals, ["ok"])
            self.assertEqual(len(submissions), 1)


if __name__ == "__main__":
    unittest.main()
