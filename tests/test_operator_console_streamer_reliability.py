from __future__ import annotations

import importlib
import logging
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch


def _load_operator_console_class():
    stubs: dict[str, types.ModuleType] = {}

    audio_receiver = types.ModuleType("pc.services.audio_receiver")
    audio_receiver.AudioReceiverService = type("AudioReceiverService", (), {})
    stubs["pc.services.audio_receiver"] = audio_receiver

    ollama_service = types.ModuleType("pc.services.ollama_service")
    ollama_service.OllamaService = type("OllamaService", (), {})
    stubs["pc.services.ollama_service"] = ollama_service

    whisper_service = types.ModuleType("pc.services.whisper_service")
    whisper_service.WhisperService = type("WhisperService", (), {})
    stubs["pc.services.whisper_service"] = whisper_service

    startup_checks = types.ModuleType("pc.services.startup_checks")
    startup_checks.StartupChecks = type("StartupChecks", (), {})
    stubs["pc.services.startup_checks"] = startup_checks

    prompt_submission = types.ModuleType("pc.services.prompt_submission")
    prompt_submission.PromptSubmission = type("PromptSubmission", (), {})
    stubs["pc.services.prompt_submission"] = prompt_submission

    receiver_widget = types.ModuleType("pc.video.receiver_widget")
    receiver_widget.UDPVideoReceiver = type("UDPVideoReceiver", (), {})
    stubs["pc.video.receiver_widget"] = receiver_widget

    sys.modules.pop("pc.operator_console_app", None)
    with patch.dict(sys.modules, stubs):
        module = importlib.import_module("pc.operator_console_app")
    return module.OperatorConsoleApp


OperatorConsoleApp = _load_operator_console_class()


class _FakeLabel:
    def __init__(self) -> None:
        self.text = "Unknown"
        self.style = "Warn.TLabel"

    def configure(self, **kwargs) -> None:
        if "text" in kwargs:
            self.text = kwargs["text"]
        if "style" in kwargs:
            self.style = kwargs["style"]


class _FakeStreamerManager:
    def __init__(self) -> None:
        self.state = {"mic": "stopped", "video": "stopped"}
        self.action_delay: dict[tuple[str, str], float] = {}
        self.query_delays: dict[tuple[str, int], float] = {}
        self._query_count = {"mic": 0, "video": 0}
        self._lock = threading.Lock()
        self._active_actions = 0
        self.max_concurrent_actions = 0

    def run_action(self, streamer: str, action: str) -> tuple[bool, str]:
        with self._lock:
            self._active_actions += 1
            self.max_concurrent_actions = max(self.max_concurrent_actions, self._active_actions)
        time.sleep(self.action_delay.get((streamer, action), 0.0))
        with self._lock:
            self.state[streamer] = "running" if action == "start" else "stopped"
            self._active_actions -= 1
        return True, "started" if action == "start" else "stopped"

    def query_status(self, streamer: str) -> tuple[bool, str]:
        with self._lock:
            self._query_count[streamer] += 1
            query_index = self._query_count[streamer]
            snapshot = self.state[streamer]
        time.sleep(self.query_delays.get((streamer, query_index), 0.0))
        return snapshot == "running", snapshot


def _make_harness() -> tuple[OperatorConsoleApp, _FakeStreamerManager]:
    app = OperatorConsoleApp.__new__(OperatorConsoleApp)
    manager = _FakeStreamerManager()

    app.streamer_manager = manager
    app.logger = logging.getLogger("test.operator_console_streamer_reliability")
    app._streamer_control_lock = threading.Lock()
    app._streamer_action_tokens = {"mic": 0, "video": 0}
    app._streamer_pending_actions = {"mic": None, "video": None}
    app._streamer_action_worker_running = {"mic": False, "video": False}
    app._streamer_refresh_tokens = {"mic": 0, "video": 0}
    app._streamer_refresh_owner_action_token = {"mic": None, "video": None}
    app._streamer_refresh_worker_running = {"mic": False, "video": False}
    app.mic_streamer_status = _FakeLabel()
    app.video_streamer_status = _FakeLabel()
    app._post_ui = lambda callback, *args, **kwargs: callback(*args, **kwargs)
    return app, manager


def _wait_for_idle(app: OperatorConsoleApp, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with app._streamer_control_lock:
            idle = (
                not app._streamer_action_worker_running["mic"]
                and not app._streamer_action_worker_running["video"]
                and not app._streamer_refresh_worker_running["mic"]
                and not app._streamer_refresh_worker_running["video"]
                and app._streamer_pending_actions["mic"] is None
                and app._streamer_pending_actions["video"] is None
            )
        if idle:
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for streamer workers to become idle")


class TestOperatorConsoleStreamerReliability(unittest.TestCase):
    def test_newest_action_wins_and_actions_do_not_overlap(self):
        app, manager = _make_harness()
        manager.action_delay[("mic", "start")] = 0.06

        app._run_streamer_action("mic", "start")
        time.sleep(0.01)
        app._run_streamer_action("mic", "stop")
        _wait_for_idle(app)

        self.assertEqual(manager.max_concurrent_actions, 1)
        self.assertEqual(manager.state["mic"], "stopped")
        self.assertEqual(app.mic_streamer_status.text, "stopped")
        self.assertEqual(app.mic_streamer_status.style, "Warn.TLabel")

    def test_stale_refresh_result_is_suppressed(self):
        app, manager = _make_harness()
        manager.query_delays[("mic", 1)] = 0.08

        app.refresh_streamer_status("mic")
        time.sleep(0.01)
        app._run_streamer_action("mic", "start")
        _wait_for_idle(app)

        self.assertEqual(manager.state["mic"], "running")
        self.assertEqual(app.mic_streamer_status.text, "running")
        self.assertEqual(app.mic_streamer_status.style, "StatusValue.TLabel")

    def test_rapid_50_cycle_start_stop_for_both_streamers(self):
        app, manager = _make_harness()

        for _ in range(50):
            app._run_streamer_action("mic", "start")
            app._run_streamer_action("mic", "stop")
            app._run_streamer_action("video", "start")
            app._run_streamer_action("video", "stop")

        _wait_for_idle(app, timeout=15.0)

        self.assertEqual(manager.state["mic"], "stopped")
        self.assertEqual(manager.state["video"], "stopped")
        self.assertEqual(app.mic_streamer_status.text, "stopped")
        self.assertEqual(app.video_streamer_status.text, "stopped")
        self.assertEqual(app.mic_streamer_status.style, "Warn.TLabel")
        self.assertEqual(app.video_streamer_status.style, "Warn.TLabel")


if __name__ == "__main__":
    unittest.main()
