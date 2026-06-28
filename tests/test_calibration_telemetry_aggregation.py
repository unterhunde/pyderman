"""Unit tests for calibration telemetry aggregation helpers."""

from __future__ import annotations

import unittest

from pc.services.calibration_telemetry_aggregation import (
    TelemetryValidationError,
    validate_live_metrics_payload,
    validate_stage_summary,
)
from pi.audio.calibration_telemetry import _StageAccumulator


def _make_valid_summary(
    *,
    session_id: str = "sess-1",
    stage_id: str = "silence-1",
    stage_type: str = "silence",
    chunks: int = 8,
    seq_start: int = 100,
    seq_end: int = 107,
) -> dict:
    return {
        "session_id": session_id,
        "stage_id": stage_id,
        "stage_type": stage_type,
        "start_timestamp_ms": 1000,
        "end_timestamp_ms": 5000,
        "audio_sequence_start": seq_start,
        "audio_sequence_end": seq_end,
        "chunks_captured": chunks,
        "chunks_missing": 0,
        "chunks_dropped": 0,
        "raw_rms": 0.02,
        "processed_rms": 0.015,
        "peak": 0.12,
        "clipping_ratio": 0.0,
        "gate_active_ratio": 0.9,
        "agc_gain": 1.1,
        "active_channel": 0,
        "telemetry_complete": True,
    }


class TestValidateStageSummary(unittest.TestCase):
    def _validate(self, summary: dict, **kwargs) -> object:
        return validate_stage_summary(
            summary,
            expected_session_id=kwargs.get("session_id", "sess-1"),
            expected_stage_id=kwargs.get("stage_id", "silence-1"),
            expected_stage_type=kwargs.get("stage_type", "silence"),
        )

    def test_valid_summary_returns_complete(self):
        result = self._validate(_make_valid_summary())
        self.assertTrue(result.complete)
        self.assertEqual(result.reason, "")

    def test_missing_field_returns_incomplete(self):
        summary = _make_valid_summary()
        del summary["raw_rms"]
        result = self._validate(summary)
        self.assertFalse(result.complete)
        self.assertIn("raw_rms", result.reason)

    def test_session_mismatch_returns_incomplete(self):
        summary = _make_valid_summary(session_id="wrong-sess")
        result = self._validate(summary)
        self.assertFalse(result.complete)
        self.assertIn("session mismatch", result.reason)

    def test_stage_id_mismatch_returns_incomplete(self):
        summary = _make_valid_summary(stage_id="wrong-stage")
        result = self._validate(summary)
        self.assertFalse(result.complete)
        self.assertIn("stage mismatch", result.reason)

    def test_stage_type_mismatch_returns_incomplete(self):
        summary = _make_valid_summary(stage_type="loud")
        result = self._validate(summary)
        self.assertFalse(result.complete)
        self.assertIn("stage type mismatch", result.reason)

    def test_none_sequence_range_returns_incomplete(self):
        summary = _make_valid_summary()
        summary["audio_sequence_start"] = None
        result = self._validate(summary)
        self.assertFalse(result.complete)
        self.assertIn("sequence range", result.reason)

    def test_inverted_sequence_range_returns_incomplete(self):
        summary = _make_valid_summary(seq_start=200, seq_end=100)
        result = self._validate(summary)
        self.assertFalse(result.complete)
        self.assertIn("sequence range", result.reason)

    def test_zero_chunks_returns_incomplete(self):
        summary = _make_valid_summary(chunks=0)
        result = self._validate(summary)
        self.assertFalse(result.complete)
        self.assertIn("chunks captured", result.reason)

    def test_telemetry_complete_false_returns_incomplete(self):
        summary = _make_valid_summary()
        summary["telemetry_complete"] = False
        result = self._validate(summary)
        self.assertFalse(result.complete)
        self.assertIn("incomplete", result.reason)


class TestValidateLiveMetricsPayload(unittest.TestCase):
    def _make_valid_payload(self) -> dict:
        return {
            "raw_rms": 0.03,
            "processed_rms": 0.025,
            "peak": 0.2,
            "clipping_ratio": 0.0,
            "gate_active_ratio": 0.3,
            "agc_gain": 1.1,
            "active_channel": 0,
            "audio_sequence_start": 50,
            "audio_sequence_end": 50,
            "chunks_captured": 1,
            "chunks_missing": 0,
            "chunks_dropped": 0,
        }

    def test_valid_payload_does_not_raise(self):
        validate_live_metrics_payload(self._make_valid_payload())

    def test_missing_field_raises(self):
        payload = self._make_valid_payload()
        del payload["raw_rms"]
        with self.assertRaises(TelemetryValidationError):
            validate_live_metrics_payload(payload)

    def test_missing_multiple_fields_listed_in_error(self):
        payload = self._make_valid_payload()
        del payload["raw_rms"]
        del payload["peak"]
        with self.assertRaises(TelemetryValidationError) as ctx:
            validate_live_metrics_payload(payload)
        msg = str(ctx.exception)
        self.assertIn("raw_rms", msg)
        self.assertIn("peak", msg)


class TestStageAccumulator(unittest.TestCase):
    """Tests for the Pi-side stage accumulator (pure in-memory, no sockets)."""

    def _make_accumulator(self, session_id: str = "s1", stage_id: str = "silence-1", stage_type: str = "silence"):
        return _StageAccumulator(
            session_id=session_id,
            stage_id=stage_id,
            stage_type=stage_type,
            start_timestamp_ms=1000,
        )

    def test_empty_accumulator_is_incomplete(self):
        acc = self._make_accumulator()
        summary = acc.summary(end_timestamp_ms=5000)
        self.assertFalse(summary["telemetry_complete"])
        self.assertEqual(summary["chunks_captured"], 0)

    def test_single_chunk_produces_complete_summary(self):
        acc = self._make_accumulator()
        acc.add_chunk(
            sequence_number=100,
            raw_rms=0.05,
            processed_rms=0.04,
            peak=0.3,
            clipping_ratio=0.0,
            gate_active=True,
            agc_gain=1.2,
            active_channel=0,
        )
        summary = acc.summary(end_timestamp_ms=5000)
        self.assertTrue(summary["telemetry_complete"])
        self.assertEqual(summary["chunks_captured"], 1)
        self.assertEqual(summary["audio_sequence_start"], 100)
        self.assertEqual(summary["audio_sequence_end"], 100)

    def test_multiple_chunks_aggregate_correctly(self):
        acc = self._make_accumulator()
        for seq in range(100, 108):
            acc.add_chunk(
                sequence_number=seq,
                raw_rms=0.02,
                processed_rms=0.015,
                peak=0.1,
                clipping_ratio=0.0,
                gate_active=False,
                agc_gain=1.0,
                active_channel=0,
            )
        summary = acc.summary(end_timestamp_ms=5000)
        self.assertEqual(summary["chunks_captured"], 8)
        self.assertEqual(summary["chunks_missing"], 0)
        self.assertEqual(summary["audio_sequence_start"], 100)
        self.assertEqual(summary["audio_sequence_end"], 107)
        self.assertAlmostEqual(summary["raw_rms"], 0.02, places=5)
        self.assertEqual(summary["gate_active_ratio"], 0.0)

    def test_missing_chunks_detected(self):
        acc = self._make_accumulator()
        acc.add_chunk(sequence_number=100, raw_rms=0.01, processed_rms=0.01, peak=0.05,
                      clipping_ratio=0.0, gate_active=False, agc_gain=1.0, active_channel=0)
        # skip 101
        acc.add_chunk(sequence_number=102, raw_rms=0.01, processed_rms=0.01, peak=0.05,
                      clipping_ratio=0.0, gate_active=False, agc_gain=1.0, active_channel=0)
        summary = acc.summary(end_timestamp_ms=5000)
        self.assertEqual(summary["chunks_captured"], 2)
        self.assertEqual(summary["chunks_missing"], 1)

    def test_dropped_chunks_accumulate(self):
        acc = self._make_accumulator()
        acc.add_chunk(sequence_number=100, raw_rms=0.01, processed_rms=0.01, peak=0.05,
                      clipping_ratio=0.0, gate_active=False, agc_gain=1.0, active_channel=0)
        acc.add_drop(3)
        summary = acc.summary(end_timestamp_ms=5000)
        self.assertEqual(summary["chunks_dropped"], 3)

    def test_peak_is_maximum_not_mean(self):
        acc = self._make_accumulator()
        acc.add_chunk(sequence_number=100, raw_rms=0.01, processed_rms=0.01, peak=0.1,
                      clipping_ratio=0.0, gate_active=False, agc_gain=1.0, active_channel=0)
        acc.add_chunk(sequence_number=101, raw_rms=0.01, processed_rms=0.01, peak=0.9,
                      clipping_ratio=0.0, gate_active=False, agc_gain=1.0, active_channel=0)
        summary = acc.summary(end_timestamp_ms=5000)
        self.assertAlmostEqual(summary["peak"], 0.9, places=5)

    def test_gate_active_ratio_computation(self):
        acc = self._make_accumulator()
        for i, gate in enumerate([True, True, False, False]):
            acc.add_chunk(sequence_number=100 + i, raw_rms=0.01, processed_rms=0.01, peak=0.05,
                          clipping_ratio=0.0, gate_active=gate, agc_gain=1.0, active_channel=0)
        summary = acc.summary(end_timestamp_ms=5000)
        self.assertAlmostEqual(summary["gate_active_ratio"], 0.5, places=5)

    def test_summary_includes_session_and_stage_ids(self):
        acc = self._make_accumulator(session_id="my-session", stage_id="normal-2", stage_type="normal")
        summary = acc.summary(end_timestamp_ms=5000)
        self.assertEqual(summary["session_id"], "my-session")
        self.assertEqual(summary["stage_id"], "normal-2")
        self.assertEqual(summary["stage_type"], "normal")

    def test_negative_drop_count_clamped_to_zero(self):
        acc = self._make_accumulator()
        acc.add_drop(-5)
        summary = acc.summary(end_timestamp_ms=5000)
        self.assertEqual(summary["chunks_dropped"], 0)


if __name__ == "__main__":
    unittest.main()
