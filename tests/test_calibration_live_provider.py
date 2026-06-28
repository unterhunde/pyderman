"""Unit tests for the live telemetry calibration metrics provider.

All tests use in-memory stubs; no real sockets or threads are created.
"""

from __future__ import annotations

import unittest
from typing import Any

from pc.services.calibration_metrics_provider import (
    LiveTelemetryCalibrationMetricsProvider,
    MeasurementStage,
    StageMetrics,
    SimulatedCalibrationMetricsProvider,
)


# ---------------------------------------------------------------------------
# Stub client — replaces CalibrationTelemetryClient in-process
# ---------------------------------------------------------------------------

class _StubClient:
    """In-memory stub for CalibrationTelemetryClient."""

    def __init__(self) -> None:
        self.connection_state = "disconnected"
        self._connect_raises: Exception | None = None
        self._request_responses: dict[str, Any] = {}  # action -> response payload or exception
        self._live_telemetry: list[dict[str, Any]] = []
        self.connected: bool = False
        self.disconnected: bool = False
        self.sent_requests: list[dict[str, Any]] = []

    def connect(self, *, timeout_s: float = 3.0) -> None:
        if self._connect_raises is not None:
            raise self._connect_raises
        self.connection_state = "connected"
        self.connected = True

    def disconnect(self) -> None:
        self.connection_state = "disconnected"
        self.disconnected = True

    def send_request(
        self,
        *,
        action: str,
        session_id: str | None,
        payload: dict[str, Any],
        timeout_s: float = 3.0,
    ) -> dict[str, Any]:
        self.sent_requests.append({"action": action, "session_id": session_id, "payload": payload})
        response = self._request_responses.get(action)
        if isinstance(response, Exception):
            raise response
        if response is None:
            return {}
        return response

    def read_live_telemetry(self) -> list[dict[str, Any]]:
        items = list(self._live_telemetry)
        self._live_telemetry.clear()
        return items


def _make_provider(stub: _StubClient | None = None) -> tuple[LiveTelemetryCalibrationMetricsProvider, _StubClient]:
    if stub is None:
        stub = _StubClient()
    stub.connection_state = "connected"
    stub._request_responses["open_session"] = {"session_id": "sess-1"}
    provider = LiveTelemetryCalibrationMetricsProvider(
        pi_host="localhost",
        diagnostics_port=19876,
        client_factory=lambda host, port: stub,
    )
    return provider, stub


# ---------------------------------------------------------------------------
# Tests: metadata
# ---------------------------------------------------------------------------

class TestLiveProviderMetadata(unittest.TestCase):
    def test_metadata_mode_is_live_telemetry(self):
        provider, _ = _make_provider()
        metadata = provider.metadata()
        self.assertEqual(metadata.mode, "live_telemetry")

    def test_metadata_is_not_simulated(self):
        provider, _ = _make_provider()
        metadata = provider.metadata()
        self.assertFalse(metadata.is_simulated)

    def test_metadata_simulation_warning_is_empty(self):
        provider, _ = _make_provider()
        metadata = provider.metadata()
        self.assertEqual(metadata.simulation_warning, "")

    def test_metadata_source_label_includes_host_and_port(self):
        provider, _ = _make_provider()
        metadata = provider.metadata()
        self.assertIn("localhost", metadata.source_label)
        self.assertIn("19876", metadata.source_label)


# ---------------------------------------------------------------------------
# Tests: session lifecycle
# ---------------------------------------------------------------------------

class TestLiveProviderSession(unittest.TestCase):
    def test_start_session_connects_and_sends_open_session(self):
        provider, stub = _make_provider()
        provider.start_session(session_id="sess-1", generation=1)
        self.assertTrue(stub.connected)
        actions = [r["action"] for r in stub.sent_requests]
        self.assertIn("open_session", actions)

    def test_end_session_with_cancel_sends_cancel_session(self):
        provider, stub = _make_provider()
        stub._request_responses["cancel_session"] = {"cancelled": True}
        provider.start_session(session_id="sess-1", generation=1)
        provider.end_session(session_id="sess-1", cancelled=True)
        actions = [r["action"] for r in stub.sent_requests]
        self.assertIn("cancel_session", actions)
        self.assertTrue(stub.disconnected)

    def test_end_session_with_close_sends_close_session(self):
        provider, stub = _make_provider()
        stub._request_responses["close_session"] = {"closed_session_id": "sess-1"}
        provider.start_session(session_id="sess-1", generation=1)
        provider.end_session(session_id="sess-1", cancelled=False)
        actions = [r["action"] for r in stub.sent_requests]
        self.assertIn("close_session", actions)
        self.assertTrue(stub.disconnected)

    def test_end_session_mismatched_session_id_is_no_op(self):
        provider, stub = _make_provider()
        provider.start_session(session_id="sess-1", generation=1)
        stub.sent_requests.clear()
        provider.end_session(session_id="wrong-sess", cancelled=True)
        self.assertEqual(stub.sent_requests, [])

    def test_start_stage_sends_open_stage(self):
        provider, stub = _make_provider()
        stub._request_responses["open_stage"] = {"stage_id": "silence-1", "opened": True}
        provider.start_session(session_id="sess-1", generation=1)
        provider.start_stage(session_id="sess-1", stage_id="silence-1", stage=MeasurementStage.SILENCE)
        actions = [r["action"] for r in stub.sent_requests]
        self.assertIn("open_stage", actions)


# ---------------------------------------------------------------------------
# Tests: finish_stage / stage aggregation
# ---------------------------------------------------------------------------

def _make_stage_summary(
    *,
    session_id: str = "sess-1",
    stage_id: str = "silence-1",
    stage_type: str = "silence",
) -> dict:
    return {
        "stage_summary": {
            "session_id": session_id,
            "stage_id": stage_id,
            "stage_type": stage_type,
            "start_timestamp_ms": 1000,
            "end_timestamp_ms": 5000,
            "audio_sequence_start": 100,
            "audio_sequence_end": 107,
            "chunks_captured": 8,
            "chunks_missing": 0,
            "chunks_dropped": 0,
            "raw_rms": 0.03,
            "processed_rms": 0.025,
            "peak": 0.2,
            "clipping_ratio": 0.0,
            "gate_active_ratio": 0.8,
            "agc_gain": 1.1,
            "active_channel": 0,
            "telemetry_complete": True,
        }
    }


class TestLiveProviderFinishStage(unittest.TestCase):
    def _setup(self, stage_summary: dict | None = None) -> tuple[LiveTelemetryCalibrationMetricsProvider, _StubClient]:
        provider, stub = _make_provider()
        summary = stage_summary or _make_stage_summary()
        stub._request_responses["open_stage"] = {"stage_id": "silence-1", "opened": True}
        stub._request_responses["close_stage"] = summary
        provider.start_session(session_id="sess-1", generation=1)
        provider.start_stage(session_id="sess-1", stage_id="silence-1", stage=MeasurementStage.SILENCE)
        return provider, stub

    def test_valid_summary_returns_capture_success(self):
        provider, _ = self._setup()
        metrics = provider.finish_stage(
            session_id="sess-1", stage_id="silence-1",
            stage=MeasurementStage.SILENCE, timeout_seconds=5.0,
        )
        self.assertIsInstance(metrics, StageMetrics)
        self.assertTrue(metrics.capture_success)
        self.assertTrue(metrics.telemetry_complete)

    def test_field_mapping_is_correct(self):
        provider, _ = self._setup()
        metrics = provider.finish_stage(
            session_id="sess-1", stage_id="silence-1",
            stage=MeasurementStage.SILENCE, timeout_seconds=5.0,
        )
        self.assertAlmostEqual(metrics.raw_rms, 0.03, places=5)
        self.assertAlmostEqual(metrics.processed_rms, 0.025, places=5)
        self.assertAlmostEqual(metrics.peak, 0.2, places=5)
        self.assertAlmostEqual(metrics.gate_ratio, 0.8, places=5)
        self.assertEqual(metrics.chunks_captured, 8)
        self.assertEqual(metrics.audio_sequence_start, 100)
        self.assertEqual(metrics.audio_sequence_end, 107)

    def test_stale_session_returns_failure(self):
        provider, _ = self._setup()
        metrics = provider.finish_stage(
            session_id="wrong-sess", stage_id="silence-1",
            stage=MeasurementStage.SILENCE, timeout_seconds=5.0,
        )
        self.assertFalse(metrics.capture_success)

    def test_missing_stage_summary_in_response_returns_failure(self):
        provider, stub = _make_provider()
        stub._request_responses["open_stage"] = {"stage_id": "silence-1", "opened": True}
        stub._request_responses["close_stage"] = {}  # no stage_summary key
        provider.start_session(session_id="sess-1", generation=1)
        provider.start_stage(session_id="sess-1", stage_id="silence-1", stage=MeasurementStage.SILENCE)
        metrics = provider.finish_stage(
            session_id="sess-1", stage_id="silence-1",
            stage=MeasurementStage.SILENCE, timeout_seconds=5.0,
        )
        self.assertFalse(metrics.capture_success)
        self.assertIn("missing stage summary", metrics.failure_reason)

    def test_session_mismatch_in_summary_returns_failure(self):
        wrong_summary = _make_stage_summary(session_id="different-session")
        provider, _ = self._setup(stage_summary=wrong_summary)
        metrics = provider.finish_stage(
            session_id="sess-1", stage_id="silence-1",
            stage=MeasurementStage.SILENCE, timeout_seconds=5.0,
        )
        self.assertFalse(metrics.capture_success)
        self.assertIn("session mismatch", metrics.failure_reason)

    def test_zero_chunks_in_summary_returns_failure(self):
        summary = _make_stage_summary()
        summary["stage_summary"]["chunks_captured"] = 0
        summary["stage_summary"]["telemetry_complete"] = False
        provider, _ = self._setup(stage_summary=summary)
        metrics = provider.finish_stage(
            session_id="sess-1", stage_id="silence-1",
            stage=MeasurementStage.SILENCE, timeout_seconds=5.0,
        )
        self.assertFalse(metrics.capture_success)


# ---------------------------------------------------------------------------
# Tests: live polling / stale session rejection
# ---------------------------------------------------------------------------

class TestLiveProviderPolling(unittest.TestCase):
    def _make_live_telemetry_message(self, session_id: str = "sess-1") -> dict:
        return {
            "session_id": session_id,
            "payload": {
                "raw_rms": 0.04,
                "processed_rms": 0.03,
                "peak": 0.25,
                "clipping_ratio": 0.0,
                "gate_active_ratio": 0.4,
                "agc_gain": 1.15,
                "active_channel": 0,
                "audio_sequence_start": 200,
                "audio_sequence_end": 200,
                "chunks_captured": 1,
                "chunks_missing": 0,
                "chunks_dropped": 0,
            },
        }

    def test_poll_returns_none_before_session_start(self):
        provider, _ = _make_provider()
        result = provider.poll_live_metrics(session_id="sess-1")
        self.assertIsNone(result)

    def test_poll_returns_none_for_stale_session(self):
        provider, stub = _make_provider()
        provider.start_session(session_id="sess-1", generation=1)
        stub._live_telemetry.append(self._make_live_telemetry_message("sess-1"))
        result = provider.poll_live_metrics(session_id="stale-session")
        self.assertIsNone(result)

    def test_poll_returns_metrics_when_telemetry_available(self):
        provider, stub = _make_provider()
        provider.start_session(session_id="sess-1", generation=1)
        stub._live_telemetry.append(self._make_live_telemetry_message("sess-1"))
        result = provider.poll_live_metrics(session_id="sess-1")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, StageMetrics)
        self.assertAlmostEqual(result.raw_rms, 0.04, places=5)

    def test_poll_rejects_telemetry_for_different_session(self):
        provider, stub = _make_provider()
        provider.start_session(session_id="sess-1", generation=1)
        stub._live_telemetry.append(self._make_live_telemetry_message("other-session"))
        result = provider.poll_live_metrics(session_id="sess-1")
        # no valid telemetry for sess-1, returns None (no cached metrics yet)
        self.assertIsNone(result)

    def test_poll_skips_malformed_payload(self):
        provider, stub = _make_provider()
        provider.start_session(session_id="sess-1", generation=1)
        stub._live_telemetry.append({
            "session_id": "sess-1",
            "payload": {"raw_rms": 0.01},  # missing most fields
        })
        # Should not raise; returns None (no valid cached metrics)
        result = provider.poll_live_metrics(session_id="sess-1")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Tests: simulation vs live behavioral distinction
# ---------------------------------------------------------------------------

class TestProviderDistinction(unittest.TestCase):
    def test_simulation_is_simulated(self):
        self.assertTrue(SimulatedCalibrationMetricsProvider().metadata().is_simulated)

    def test_live_is_not_simulated(self):
        provider, _ = _make_provider()
        self.assertFalse(provider.metadata().is_simulated)

    def test_simulation_has_warning(self):
        metadata = SimulatedCalibrationMetricsProvider().metadata()
        self.assertIn("SIMULATION MODE", metadata.simulation_warning)

    def test_live_has_no_warning(self):
        provider, _ = _make_provider()
        self.assertEqual(provider.metadata().simulation_warning, "")

    def test_simulation_mode_label(self):
        self.assertEqual(SimulatedCalibrationMetricsProvider().metadata().mode, "simulation")

    def test_live_mode_label(self):
        provider, _ = _make_provider()
        self.assertEqual(provider.metadata().mode, "live_telemetry")


if __name__ == "__main__":
    unittest.main()
