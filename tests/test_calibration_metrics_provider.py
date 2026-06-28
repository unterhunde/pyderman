from __future__ import annotations

import unittest

from pc.services.calibration_metrics_provider import (
    MeasurementStage,
    SimulatedCalibrationMetricsProvider,
    StageMetrics,
)


class TestSimulatedCalibrationMetricsProvider(unittest.TestCase):
    def test_metadata_exposes_simulation_source_designation(self):
        provider = SimulatedCalibrationMetricsProvider()
        metadata = provider.metadata()
        self.assertEqual(metadata.mode, "simulation")
        self.assertTrue(metadata.is_simulated)
        self.assertIn("SIMULATION MODE", metadata.simulation_warning)
        self.assertIn("not production microphone calibration values", metadata.simulation_warning)
        self.assertEqual(metadata.source_label, "deterministic-simulated-provider")

    def test_contract_returns_stage_metrics_fields(self):
        provider = SimulatedCalibrationMetricsProvider()
        metrics = provider.capture(MeasurementStage.NORMAL, attempt=1, capture_seconds=4)
        self.assertIsInstance(metrics, StageMetrics)
        self.assertIsInstance(metrics.raw_rms, float)
        self.assertIsInstance(metrics.processed_rms, float)
        self.assertIsInstance(metrics.peak, float)
        self.assertIsInstance(metrics.clipping, float)
        self.assertIsInstance(metrics.gate_ratio, float)
        self.assertIsInstance(metrics.agc_gain, float)
        self.assertIsInstance(metrics.capture_success, bool)

    def test_deterministic_for_same_input(self):
        provider = SimulatedCalibrationMetricsProvider()
        first = provider.capture(MeasurementStage.LOUD, attempt=2, capture_seconds=4)
        second = provider.capture(MeasurementStage.LOUD, attempt=2, capture_seconds=4)
        # Timestamps use real wall-clock time and legitimately differ between calls;
        # verify determinism of all audio metric and control fields.
        self.assertEqual(first.raw_rms, second.raw_rms)
        self.assertEqual(first.processed_rms, second.processed_rms)
        self.assertEqual(first.peak, second.peak)
        self.assertEqual(first.clipping, second.clipping)
        self.assertEqual(first.gate_ratio, second.gate_ratio)
        self.assertEqual(first.agc_gain, second.agc_gain)
        self.assertEqual(first.capture_success, second.capture_success)
        self.assertEqual(first.chunks_captured, second.chunks_captured)
        self.assertEqual(first.chunks_missing, second.chunks_missing)
        self.assertEqual(first.chunks_dropped, second.chunks_dropped)
        self.assertEqual(first.stage_id, second.stage_id)
        self.assertEqual(first.stage_type, second.stage_type)
        self.assertEqual(first.telemetry_complete, second.telemetry_complete)


if __name__ == "__main__":
    unittest.main()
